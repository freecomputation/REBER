#!/usr/bin/env python3
"""REBER scrub verifier.

Verifies a reber-format 1 bundle against the register's scrub rules and
fails closed: a bundle that trips any rule is rejected whole, and every
failure names the rule it tripped. The verifier is stdlib-only and makes
no network calls.

Usage:
    python3 scrub.py BUNDLE.json [--register REGISTER.json]

Exit status is 0 when the bundle passes and 1 when it fails. Failures are
printed one per line as "FAIL <rule>: <detail>". A passing bundle prints
"PASS <bundle_id>".
"""

import json
import re
import sys
from datetime import datetime

FORMAT = "reber-format 1"

# The register's total budget, stated in README.md and enforced here:
# the whole register, evidence included, stays under this many bytes.
BUDGET_BYTES = 20_000_000

IMAGE_CAP_BYTES = 150_000
AUDIO_CAP_BYTES = 200_000
AUDIO_CAP_SECONDS = 30

# Keys that carry position, bearing, distance, or location meaning. A
# bundle using any of these keys, anywhere, at any depth, is rejected.
# The format defined in FORMAT.md never uses them.
COORDINATE_KEYS = {
    "lat", "latitude", "lon", "lng", "longitude", "coord", "coords",
    "coordinate", "coordinates", "position", "gps", "geo", "geolocation",
    "region", "address", "site", "station_position",
}
BEARING_KEYS = {
    "bearing", "azimuth", "az", "elevation", "elev", "distance",
    "distance_km", "distance_m", "range", "range_km", "ground_track",
    "footprint", "slant_range",
}
NETWORK_KEYS = {"ip", "ip_address", "ipv4", "ipv6", "hostname", "mac_address"}

TIME_KEYS = {"time", "generated", "start", "end", "aos", "los", "t_max"}

ISO_UTC_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|\+00:00)$")
COORD_PAIR_RE = re.compile(
    r"[-+]?\d{1,2}\.\d{3,}\s*[,;]\s*[-+]?\d{1,3}\.\d{3,}")
DMS_RE = re.compile(r"\d{1,3}\s*°\s*\d{1,2}\s*[′']")
RELATIVE_TEXT_RES = [
    re.compile(r"\d+(\.\d+)?\s*(km|kilometres|kilometers|miles|nmi)\s+"
               r"(from|away|north|south|east|west|off)\b", re.IGNORECASE),
    re.compile(r"\bbearing\s*(of|=|:)?\s*\d", re.IGNORECASE),
]
IQ_SUFFIXES = (".iq", ".cu8", ".cs16", ".sigmf-data")


def _is_time_key(key):
    return key in TIME_KEYS or key.endswith("_utc")


def _check_timestamp(value, path, failures):
    if not isinstance(value, str) or not ISO_UTC_RE.match(value):
        failures.append(
            "utc-only: %s is not an ISO 8601 UTC timestamp: %r" % (path, value))
        return
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        failures.append(
            "utc-only: %s does not parse as a UTC timestamp: %r" % (path, value))


def _looks_like_evidence(node):
    return isinstance(node, dict) and (
        "size_bytes" in node or "evidence_class" in node)


def _check_evidence(entry, path, failures, evidence_bytes):
    cls = entry.get("evidence_class") or entry.get("class")
    size = entry.get("size_bytes")
    if cls == "iq":
        failures.append(
            "iq-never-travels: %s declares IQ evidence; IQ never travels"
            % path)
        return
    if cls == "voice":
        failures.append(
            "audio-stays-home: %s declares voice audio; voice audio "
            "stays at the publishing station by default" % path)
        return
    if cls not in ("image", "audio", "machine", "tone", "product"):
        failures.append(
            "evidence-caps: %s has no recognised evidence class: %r"
            % (path, cls))
        return
    if not isinstance(size, int) or size < 0:
        failures.append(
            "evidence-caps: %s does not declare a valid size_bytes" % path)
        return
    evidence_bytes.append(size)
    if cls == "image" and size > IMAGE_CAP_BYTES:
        failures.append(
            "evidence-caps: %s is an image of %d bytes over the %d byte cap"
            % (path, size, IMAGE_CAP_BYTES))
    if cls in ("audio", "machine", "tone"):
        if size > AUDIO_CAP_BYTES:
            failures.append(
                "evidence-caps: %s is audio of %d bytes over the %d byte cap"
                % (path, size, AUDIO_CAP_BYTES))
        duration = entry.get("duration_s")
        if isinstance(duration, (int, float)) and duration > AUDIO_CAP_SECONDS:
            failures.append(
                "evidence-caps: %s is audio of %s seconds over the %d "
                "second cap" % (path, duration, AUDIO_CAP_SECONDS))


def _walk(node, path, failures, evidence_bytes):
    if isinstance(node, dict):
        for key, value in node.items():
            kpath = "%s.%s" % (path, key) if path else key
            low = key.lower()
            if low in COORDINATE_KEYS or low.startswith("lat_") \
                    or low.endswith("_lat") or low.startswith("lon_") \
                    or low.endswith("_lon"):
                failures.append(
                    "no-coordinates: key %r at %s carries position meaning"
                    % (key, kpath))
            elif low in BEARING_KEYS:
                failures.append(
                    "no-bearings-or-distances: key %r at %s carries "
                    "station-relative geometry" % (key, kpath))
            elif low in NETWORK_KEYS:
                failures.append(
                    "no-coordinates: key %r at %s carries network or "
                    "location detail" % (key, kpath))
            if _is_time_key(low):
                _check_timestamp(value, kpath, failures)
            _walk(value, kpath, failures, evidence_bytes)
        if _looks_like_evidence(node):
            _check_evidence(node, path or "$", failures, evidence_bytes)
    elif isinstance(node, list):
        if len(node) == 2 and all(
                isinstance(v, (int, float)) and not isinstance(v, bool)
                for v in node):
            a, b = node
            if -90 <= a <= 90 and -180 <= b <= 180 and (
                    isinstance(a, float) or isinstance(b, float)):
                failures.append(
                    "no-coordinates: numeric pair at %s is shaped like a "
                    "coordinate pair: %r" % (path, node))
        for i, value in enumerate(node):
            _walk(value, "%s[%d]" % (path, i), failures, evidence_bytes)
    elif isinstance(node, str):
        if COORD_PAIR_RE.search(node) or DMS_RE.search(node):
            failures.append(
                "no-coordinates: text at %s is shaped like coordinates: %r"
                % (path, node[:80]))
        for rx in RELATIVE_TEXT_RES:
            if rx.search(node):
                failures.append(
                    "no-bearings-or-distances: text at %s states a "
                    "station-relative distance or bearing: %r"
                    % (path, node[:80]))
                break
        if node.lower().endswith(IQ_SUFFIXES):
            failures.append(
                "iq-never-travels: %s references a bulk IQ file: %r"
                % (path, node))


def verify_bundle(bundle, bundle_bytes=0, register_bytes=0):
    """Return a list of failure strings; empty means the bundle passes."""
    failures = []
    if not isinstance(bundle, dict):
        return ["format: bundle is not a JSON object"]
    if bundle.get("format") != FORMAT:
        failures.append(
            "format: bundle format is %r, expected %r"
            % (bundle.get("format"), FORMAT))
    withheld = bundle.get("withheld")
    if not isinstance(withheld, list) or not withheld:
        failures.append(
            "manifest-required: bundle carries no withheld manifest; "
            "every bundle must list what was withheld and under which rule")
    else:
        for i, entry in enumerate(withheld):
            if not isinstance(entry, dict) \
                    or not str(entry.get("item") or "").strip() \
                    or not str(entry.get("rule") or "").strip():
                failures.append(
                    "manifest-required: withheld entry %d lacks an item "
                    "or a rule" % i)
    evidence_bytes = []
    _walk(bundle, "", failures, evidence_bytes)
    total = bundle_bytes + sum(evidence_bytes) + register_bytes
    if total > BUDGET_BYTES:
        failures.append(
            "budget: projected register total of %d bytes exceeds the "
            "%d byte budget" % (total, BUDGET_BYTES))
    return failures


def main(argv):
    if len(argv) < 2:
        print("usage: scrub.py BUNDLE.json [--register REGISTER.json]")
        return 2
    bundle_path = argv[1]
    register_bytes = 0
    if "--register" in argv:
        reg_path = argv[argv.index("--register") + 1]
        try:
            with open(reg_path, "rb") as fh:
                register_bytes = len(fh.read())
        except OSError:
            register_bytes = 0
    with open(bundle_path, "rb") as fh:
        raw = fh.read()
    try:
        bundle = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        print("FAIL format: bundle does not parse as JSON: %s" % exc)
        return 1
    failures = verify_bundle(bundle, bundle_bytes=len(raw),
                             register_bytes=register_bytes)
    if failures:
        for failure in failures:
            print("FAIL " + failure)
        return 1
    print("PASS %s" % (bundle.get("bundle_id") or bundle_path))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
