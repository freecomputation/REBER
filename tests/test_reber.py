#!/usr/bin/env python3
"""Tests for the REBER scrub verifier, bundle application, and site
generation. Run with: python3 -m unittest discover -s tests -v

All fixture data here is fictional demonstration data, invented for
these tests.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import apply as apply_mod  # noqa: E402
import scrub  # noqa: E402


def clean_bundle():
    return {
        "format": "reber-format 1",
        "bundle_id": "station-demo-test-001",
        "generated_utc": "2026-01-05T06:00:00Z",
        "station": {
            "station_id": "station-demo",
            "display": "Demonstration station",
            "receiver": "Wideband SDR receiver, demonstration antenna",
            "source": "simulated",
            "watches": [{
                "watch_id": "watch-demo-1",
                "start_utc": "2026-01-05T00:00:00Z",
                "end_utc": "2026-01-05T04:30:00Z",
            }],
        },
        "dossiers": [{
            "station_id": "station-demo",
            "key": "D00001",
            "kind": "aircraft",
            "summary": "Demonstration aircraft.",
        }],
        "events": [{
            "station_id": "station-demo",
            "id": "ev-demo-1",
            "watch_id": "watch-demo-1",
            "time_utc": "2026-01-05T01:00:00Z",
            "desk": "adsb",
            "kind": "telemetry",
            "grade": "CONFIRMED",
            "freq_hz": 1090000000,
            "emitter": "D00001",
            "sections": ["events"],
            "data": {"icao": "D00001", "callsign": "DEMO123",
                     "alt_ft": 10000},
        }],
        "unexplained": [],
        "astronomy": [],
        "withheld": [{
            "item": "Aircraft position fixes",
            "rule": "no-coordinates",
            "detail": "Removed before the bundle was written.",
        }],
    }


def rules_of(failures):
    return {f.split(":", 1)[0] for f in failures}


class ScrubTests(unittest.TestCase):
    def test_clean_bundle_passes(self):
        self.assertEqual(scrub.verify_bundle(clean_bundle()), [])

    def test_poisoned_bundle_with_coordinates_fails(self):
        bundle = clean_bundle()
        bundle["events"][0]["data"]["lat"] = 12.34
        bundle["events"][0]["data"]["lon"] = -56.78
        failures = scrub.verify_bundle(bundle)
        self.assertIn("no-coordinates", rules_of(failures))

    def test_coordinate_pair_in_free_text_fails(self):
        bundle = clean_bundle()
        bundle["dossiers"][0]["summary"] = (
            "Heard near the fictional point 12.345, -56.789 for hours.")
        failures = scrub.verify_bundle(bundle)
        self.assertIn("no-coordinates", rules_of(failures))

    def test_bearing_key_fails(self):
        bundle = clean_bundle()
        bundle["events"][0]["data"]["bearing"] = 123
        failures = scrub.verify_bundle(bundle)
        self.assertIn("no-bearings-or-distances", rules_of(failures))

    def test_station_relative_distance_text_fails(self):
        bundle = clean_bundle()
        bundle["dossiers"][0]["summary"] = (
            "A demonstration emitter 12 km from the station.")
        failures = scrub.verify_bundle(bundle)
        self.assertIn("no-bearings-or-distances", rules_of(failures))

    def test_missing_withheld_manifest_fails(self):
        bundle = clean_bundle()
        del bundle["withheld"]
        failures = scrub.verify_bundle(bundle)
        self.assertIn("manifest-required", rules_of(failures))

    def test_empty_withheld_manifest_fails(self):
        bundle = clean_bundle()
        bundle["withheld"] = []
        failures = scrub.verify_bundle(bundle)
        self.assertIn("manifest-required", rules_of(failures))

    def test_non_utc_timestamp_fails(self):
        bundle = clean_bundle()
        bundle["events"][0]["time_utc"] = "2026-01-05T01:00:00+05:00"
        failures = scrub.verify_bundle(bundle)
        self.assertIn("utc-only", rules_of(failures))

    def test_oversize_image_evidence_fails(self):
        bundle = clean_bundle()
        bundle["events"][0]["data"]["evidence"] = [{
            "name": "demo.png", "evidence_class": "image",
            "size_bytes": scrub.IMAGE_CAP_BYTES + 1,
        }]
        failures = scrub.verify_bundle(bundle)
        self.assertIn("evidence-caps", rules_of(failures))

    def test_long_audio_evidence_fails(self):
        bundle = clean_bundle()
        bundle["events"][0]["data"]["evidence"] = [{
            "name": "demo.mp3", "evidence_class": "audio",
            "size_bytes": 1000, "duration_s": 45,
        }]
        failures = scrub.verify_bundle(bundle)
        self.assertIn("evidence-caps", rules_of(failures))

    def test_iq_evidence_fails(self):
        bundle = clean_bundle()
        bundle["events"][0]["data"]["evidence"] = [{
            "name": "demo.iq", "evidence_class": "iq", "size_bytes": 10,
        }]
        failures = scrub.verify_bundle(bundle)
        self.assertIn("iq-never-travels", rules_of(failures))

    def test_iq_file_reference_fails(self):
        bundle = clean_bundle()
        bundle["events"][0]["data"]["capture"] = "demo.cu8"
        failures = scrub.verify_bundle(bundle)
        self.assertIn("iq-never-travels", rules_of(failures))

    def test_voice_evidence_fails(self):
        bundle = clean_bundle()
        bundle["events"][0]["data"]["evidence"] = [{
            "name": "demo.mp3", "evidence_class": "voice",
            "size_bytes": 1000, "duration_s": 5,
        }]
        failures = scrub.verify_bundle(bundle)
        self.assertIn("audio-stays-home", rules_of(failures))

    def test_budget_rule_fails_closed(self):
        old = scrub.BUDGET_BYTES
        scrub.BUDGET_BYTES = 10
        try:
            failures = scrub.verify_bundle(clean_bundle(),
                                           bundle_bytes=100)
        finally:
            scrub.BUDGET_BYTES = old
        self.assertIn("budget", rules_of(failures))

    def test_format_document_example_passes(self):
        with open(os.path.join(ROOT, "FORMAT.md"),
                  encoding="utf-8") as fh:
            text = fh.read()
        block = text.split("```json", 1)[1].split("```", 1)[0]
        bundle = json.loads(block)
        self.assertEqual(scrub.verify_bundle(bundle), [])


class ApplyTests(unittest.TestCase):
    def test_apply_is_idempotent(self):
        register = apply_mod.empty_register()
        register = apply_mod.apply_bundle(register, clean_bundle())
        once = json.dumps(register, sort_keys=True)
        register = apply_mod.apply_bundle(register, clean_bundle())
        twice = json.dumps(register, sort_keys=True)
        self.assertEqual(once, twice)
        self.assertEqual(len(register["events"]), 1)
        self.assertEqual(len(register["withheld_log"]), 1)

    def test_dossier_standing_recomputed_from_events(self):
        register = apply_mod.empty_register()
        register = apply_mod.apply_bundle(register, clean_bundle())
        dossier = register["dossiers"][0]
        self.assertEqual(dossier["standing"], "CONFIRMED")
        self.assertEqual(dossier["events_count"], 1)
        self.assertEqual(dossier["first_heard_utc"],
                         "2026-01-05T01:00:00Z")


class GenerateTests(unittest.TestCase):
    def _fixture_register(self):
        register = apply_mod.empty_register()
        return apply_mod.apply_bundle(register, clean_bundle())

    def test_generation_is_byte_identical_across_runs(self):
        register = self._fixture_register()
        with tempfile.TemporaryDirectory() as tmp:
            reg_path = os.path.join(tmp, "register.json")
            with open(reg_path, "w", encoding="utf-8") as fh:
                fh.write(json.dumps(register, indent=1,
                                    sort_keys=True) + "\n")
            outputs = []
            for name in ("run1", "run2"):
                out_dir = os.path.join(tmp, name)
                os.makedirs(out_dir)
                proc = subprocess.run(
                    [sys.executable, os.path.join(ROOT, "generate.py"),
                     reg_path, out_dir],
                    capture_output=True, text=True)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                pages = {}
                for f in sorted(os.listdir(out_dir)):
                    with open(os.path.join(out_dir, f), "rb") as fh:
                        pages[f] = fh.read()
                outputs.append(pages)
            self.assertEqual(outputs[0], outputs[1])
            self.assertIn("index.html", outputs[0])
            self.assertIn(b"REBER", outputs[0]["index.html"])


if __name__ == "__main__":
    unittest.main()
