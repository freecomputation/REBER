#!/usr/bin/env python3
"""Apply a verified REBER bundle to the register.

This is the one code path by which any bundle, from any station, enters
register.json. The bundle is verified with scrub.py first and refused
whole if it trips any rule. Merging is deterministic: the same bundle
applied to the same register produces byte-identical output, and
applying the same bundle twice changes nothing the second time.

Usage:
    python3 apply.py BUNDLE.json [REGISTER.json]

REGISTER.json defaults to register.json beside this script.
"""

import json
import os
import sys

import scrub

GRADE_RANK = {"UNRESOLVED": 0, "PROBABLE": 1, "CONFIRMED": 2}


def empty_register():
    return {
        "format": scrub.FORMAT,
        "budget_bytes": scrub.BUDGET_BYTES,
        "stations": [],
        "dossiers": [],
        "events": [],
        "withheld_log": [],
    }


def _sort_events(events):
    return sorted(events, key=lambda e: (e.get("time_utc") or "",
                                         e.get("id") or ""))


def apply_bundle(register, bundle):
    stations = {s["station_id"]: s for s in register["stations"]}
    station = bundle["station"]
    sid = station["station_id"]
    if sid in stations:
        merged = dict(stations[sid])
        watches = {w["watch_id"]: w for w in merged.get("watches", [])}
        for watch in station.get("watches", []):
            watches[watch["watch_id"]] = watch
        merged["watches"] = [watches[k] for k in sorted(watches)]
        for key, value in station.items():
            if key != "watches":
                merged[key] = value
        stations[sid] = merged
    else:
        entry = dict(station)
        entry["watches"] = sorted(station.get("watches", []),
                                   key=lambda w: w["watch_id"])
        stations[sid] = entry
    register["stations"] = [stations[k] for k in sorted(stations)]

    events = {(e["station_id"], e["id"]): e for e in register["events"]}
    incoming = list(bundle.get("events", []))
    for section in ("unexplained", "astronomy"):
        incoming += list(bundle.get(section, []))
    for event in incoming:
        key = (event["station_id"], event["id"])
        if key in events:
            merged = dict(events[key])
            sections = sorted(set(merged.get("sections", []))
                              | set(event.get("sections", [])))
            merged.update(event)
            merged["sections"] = sections
            events[key] = merged
        else:
            entry = dict(event)
            entry["sections"] = sorted(set(entry.get("sections", [])))
            events[key] = entry
    register["events"] = _sort_events(events.values())

    dossiers = {(d["station_id"], d["key"]): d for d in register["dossiers"]}
    for dossier in bundle.get("dossiers", []):
        key = (dossier["station_id"], dossier["key"])
        if key in dossiers:
            merged = dict(dossiers[key])
            merged.update(dossier)
            dossiers[key] = merged
        else:
            dossiers[key] = dict(dossier)
    # Dossier standings, spans, and counts are recomputed from the
    # register's own events, so a dossier always describes the record
    # the register actually holds.
    linked = {}
    for event in register["events"]:
        if event.get("emitter"):
            linked.setdefault((event["station_id"], event["emitter"]),
                              []).append(event)
    for key, dossier in dossiers.items():
        mine = linked.get(key, [])
        if mine:
            dossier["events_count"] = len(mine)
            dossier["first_heard_utc"] = min(e["time_utc"] for e in mine)
            dossier["last_heard_utc"] = max(e["time_utc"] for e in mine)
            dossier["watches"] = sorted({e["watch_id"] for e in mine})
            dossier["standing"] = max(
                (e.get("grade") or "UNRESOLVED" for e in mine),
                key=lambda g: GRADE_RANK.get(g, 0))
    register["dossiers"] = [dossiers[k] for k in sorted(dossiers)]

    logged = {entry["bundle_id"] for entry in register["withheld_log"]}
    if bundle["bundle_id"] not in logged:
        register["withheld_log"].append({
            "bundle_id": bundle["bundle_id"],
            "station_id": sid,
            "entries": bundle.get("withheld", []),
        })
        register["withheld_log"].sort(key=lambda e: e["bundle_id"])
    return register


def main(argv):
    if len(argv) < 2:
        print("usage: apply.py BUNDLE.json [REGISTER.json]")
        return 2
    bundle_path = argv[1]
    here = os.path.dirname(os.path.abspath(__file__))
    register_path = argv[2] if len(argv) > 2 else os.path.join(
        here, "register.json")
    with open(bundle_path, "rb") as fh:
        raw = fh.read()
    bundle = json.loads(raw.decode("utf-8"))
    register_bytes = 0
    register = empty_register()
    if os.path.exists(register_path):
        with open(register_path, "rb") as fh:
            register_raw = fh.read()
        register_bytes = len(register_raw)
        register = json.loads(register_raw.decode("utf-8"))
    failures = scrub.verify_bundle(bundle, bundle_bytes=len(raw),
                                   register_bytes=register_bytes)
    if failures:
        for failure in failures:
            print("REFUSED " + failure)
        return 1
    register = apply_bundle(register, bundle)
    text = json.dumps(register, indent=1, sort_keys=True) + "\n"
    tmp_path = register_path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.replace(tmp_path, register_path)
    print("APPLIED %s: %d stations, %d dossiers, %d events"
          % (bundle["bundle_id"], len(register["stations"]),
             len(register["dossiers"]), len(register["events"])))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
