# reber-format 1

The dossier exchange format, version 1. A station joins the register by publishing bundles in this format. A bundle is one JSON object carrying one station's record for one or more watches: its dossiers, its graded events, its unexplained file, its astronomy account, and the manifest of what it withheld. Every bundle passes the scrub verifier in scrub.py before it is applied to register.json by apply.py, and the verifier fails closed: a bundle that trips any rule is refused whole.

All timestamps are UTC, written as ISO 8601 strings ending in Z. Frequencies are in hertz. Grades are CONFIRMED, PROBABLE, and UNRESOLVED, and they are statements about the record: CONFIRMED for a decoded or otherwise settled record, PROBABLE for a strong but partial one, UNRESOLVED for an honest unknown.

The format carries no field for a station's position, and the scrub forbids the whole family: no coordinates or anything shaped like them, no bearings or distances measured from the publishing station, no network addresses or local infrastructure detail. Aircraft altitudes, headings, speeds, and callsigns travel freely, as do frequencies, grades, and UTC times.

## The bundle

- format: the string "reber-format 1".
- bundle_id: a unique identifier for the bundle, chosen by the publishing station, used to make application idempotent.
- generated_utc: when the bundle was composed, as a UTC timestamp.
- station: the station section, below.
- scope: an optional plain statement of any record classes the bundle does not carry, and why.
- dossiers: the dossier list, below.
- events: the graded events worth a reader's time, with FLASH items marked.
- unexplained: the unexplained file in full, as event entries whose grade is UNRESOLVED.
- astronomy: the astronomy account, as event entries for predicted satellite passes and their outcomes.
- withheld: the withheld manifest, below. Required, and never empty in practice: every bundle withholds something, and the manifest says what and under which rule.

An event may appear in events and also in unexplained or astronomy; the entries are the same object, keyed by id, and the register keeps one copy of each event tagged with the sections it belongs to.

## The station section

- station_id: the station's stable handle in the register, such as "station-demo". A handle carries no location information.
- display: the station's display name.
- receiver: a plain description of the receiving equipment, such as the receiver class and antenna type.
- source: "real" for a live watch, "simulated" for a simulated one. A simulated record is always stated as such.
- watches: the watches this bundle reports, each with watch_id, start_utc, end_utc, and an optional note.

## Dossiers

One dossier per emitter, keyed by the emitter's own identifier as the station filed it - an aircraft's transponder address, a satellite's name, a named emission's frequency label.

- station_id: the station that keeps the dossier.
- key: the emitter key.
- kind: the emitter kind, such as aircraft, satellite, audio_emission, station, or system.
- standing: the dossier's standing in the record, recomputed from its events when the bundle is applied.
- first_heard_utc and last_heard_utc: the span of the published record for this emitter.
- watches: the watch identifiers in which the emitter appears in the published record.
- events_count: the number of published events linked to the dossier, recomputed on application.
- summary: a plain account of the emitter as the record supports it.

## Events

- station_id and id: the event's identity; ids are unique per station.
- watch_id: the watch that filed the event.
- time_utc: when the event began, UTC. end_utc may carry when it ended.
- desk: the desk that filed it, such as adsb, satellite, sweep, or audiocensus.
- kind: the event kind within its desk, such as telemetry, pass, or observation.
- grade: CONFIRMED, PROBABLE, or UNRESOLVED.
- freq_hz: the event's frequency in hertz, when it has one.
- emitter: the dossier key the event belongs to, when it has one.
- summary: the event's record in plain words, when the desk wrote one.
- flash: true when the event was raised as a FLASH item by the publishing station.
- data: the desk's measured detail, as an object. The fields are the desk's own measurements - signal-to-noise ratio, bandwidth, modulation estimate, altitude, heading, speed - and never position, bearing, or distance from the station.
- evidence: optional, inside data or the event. An evidence entry carries a name, an evidence_class, a size_bytes, and for audio a duration_s. Classes are image, audio, machine, tone, and product. Two classes are prohibited outright: iq, because bulk IQ never travels, and voice, because voice audio stays at the publishing station by default. Images are capped at 150,000 bytes, audio at 200,000 bytes and thirty seconds, and the scrub enforces every cap.

Astronomy entries are events with three further fields: aos_utc and los_utc for the predicted pass window, t_max_utc for the predicted peak, and outcome, such as captured or no lock. Station-relative pass geometry is not a field of this format; stations that compute it withhold it and say so in the manifest.

## The withheld manifest

A list of entries, each with item (what was withheld), rule (the scrub rule under which it was withheld), and detail (a plain explanation a reader can audit). The rule vocabulary is the scrub's own: no-coordinates, no-bearings-or-distances, utc-only, evidence-caps, iq-never-travels, audio-stays-home, manifest-required, budget, and format.

## A worked example

The bundle below is fictional demonstration data, invented for this document. It is shaped exactly like a real bundle and passes the scrub verifier.

```json
{
  "format": "reber-format 1",
  "bundle_id": "station-demo-2026-01-05-001",
  "generated_utc": "2026-01-05T06:00:00Z",
  "station": {
    "station_id": "station-demo",
    "display": "Demonstration station",
    "receiver": "Wideband SDR receiver with a fixed general-coverage antenna",
    "source": "simulated",
    "watches": [
      {
        "watch_id": "watch-demo-1",
        "start_utc": "2026-01-05T00:00:00Z",
        "end_utc": "2026-01-05T04:30:00Z",
        "note": "Demonstration watch."
      }
    ]
  },
  "dossiers": [
    {
      "station_id": "station-demo",
      "key": "D00001",
      "kind": "aircraft",
      "standing": "CONFIRMED",
      "first_heard_utc": "2026-01-05T01:00:00Z",
      "last_heard_utc": "2026-01-05T01:05:00Z",
      "watches": ["watch-demo-1"],
      "events_count": 1,
      "summary": "Demonstration aircraft heard on 1090 MHz ADS-B. Callsign DEMO123. Altitudes from 9,000 ft to 10,000 ft."
    }
  ],
  "events": [
    {
      "station_id": "station-demo",
      "id": "ev-demo-1",
      "watch_id": "watch-demo-1",
      "time_utc": "2026-01-05T01:00:00Z",
      "desk": "adsb",
      "kind": "telemetry",
      "grade": "CONFIRMED",
      "freq_hz": 1090000000,
      "emitter": "D00001",
      "data": {
        "icao": "D00001",
        "callsign": "DEMO123",
        "alt_ft": 10000,
        "velocity": {"speed_kt": 250.5, "heading_deg": 90.0}
      }
    }
  ],
  "unexplained": [
    {
      "station_id": "station-demo",
      "id": "ev-demo-2",
      "watch_id": "watch-demo-1",
      "time_utc": "2026-01-05T02:00:00Z",
      "desk": "sweep",
      "kind": "observation",
      "grade": "UNRESOLVED",
      "freq_hz": 28500000,
      "data": {
        "band": "HF",
        "shape": "unknown",
        "bw_hz": 3515.625,
        "snr_db": 19.4,
        "peak_dbm": -48.2,
        "noise_floor_db": -67.6
      }
    }
  ],
  "astronomy": [
    {
      "station_id": "station-demo",
      "id": "ev-demo-3",
      "watch_id": "watch-demo-1",
      "time_utc": "2026-01-05T03:00:00Z",
      "desk": "satellite",
      "kind": "pass",
      "grade": "UNRESOLVED",
      "freq_hz": 137100000,
      "emitter": "DEMO 1",
      "summary": "predicted pass produced no lock",
      "aos_utc": "2026-01-05T03:00:00Z",
      "los_utc": "2026-01-05T03:09:00Z",
      "t_max_utc": "2026-01-05T03:04:30Z",
      "outcome": "no lock",
      "data": {"sat": "DEMO 1", "norad": "00000", "failure": "no lock"}
    }
  ],
  "withheld": [
    {
      "item": "Aircraft position fixes in ADS-B telemetry",
      "rule": "no-coordinates",
      "detail": "Position data was removed before this bundle was written. Altitudes, headings, speeds, and callsigns are published."
    },
    {
      "item": "Bulk IQ captures",
      "rule": "iq-never-travels",
      "detail": "IQ stays at the station in all cases. This bundle is text only."
    }
  ]
}
```

## Application

A bundle enters register.json only through apply.py, which verifies it with scrub.py first and refuses it whole on any failure. Application is idempotent: events are keyed by station and id, dossiers by station and key, and a bundle_id is recorded in the register's withheld log the first time it is applied. Dossier standings, spans, and counts are recomputed from the register's own events at application time, so a dossier always describes the record the register actually holds.
