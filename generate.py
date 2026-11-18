#!/usr/bin/env python3
"""Generate the REBER site from register.json.

register.json is the single source of truth. This generator emits the
static site beside it: index.html and one page per section (dossiers,
catches, the unexplained file, astronomy). The site is plain HTML with
no JavaScript, a white page and black text. Generation is
deterministic: the same register produces byte-identical pages, so
generated files are committed and never hand-edited.

Usage:
    python3 generate.py [REGISTER.json] [OUTPUT_DIR]
"""

import html
import json
import os
import sys

STYLE = (
    "body{background:#ffffff;color:#000000;"
    "font-family:Georgia,'Times New Roman',serif;"
    "margin:2em auto;max-width:62em;padding:0 1em;line-height:1.5}"
    "h1{font-size:1.9em}h2{margin-top:1.6em}h3{margin-bottom:0.2em}"
    "a{color:#000000}nav{margin-bottom:2em}"
    "nav a{margin-right:1em}"
    ".meta{color:#333333;font-size:0.92em}"
    ".entry{margin-bottom:1.4em}"
    "table{border-collapse:collapse}td,th{padding:0.15em 0.9em 0.15em 0;"
    "text-align:left;vertical-align:top}"
)

INTRO = (
    "REBER is the Received Emissions Bulletin and Exchange Register: a "
    "public journal where listening stations publish their scrubbed "
    "records - emitter dossiers, graded catches, and the unexplained "
    "file - in one shared format, so that an emission one antenna "
    "cannot explain can be checked against what every other antenna "
    "heard."
)

BUDGET_LINE = (
    "The register is text-first and stays small on purpose. Its total "
    "budget is %d megabytes, evidence included, and the budget is "
    "enforced by the scrub verifier every bundle must pass. The "
    "register data itself currently occupies %d bytes."
)


def esc(value):
    return html.escape(str(value), quote=True)


def fmt_freq(hz):
    if hz is None:
        return ""
    if abs(hz) >= 1_000_000:
        text = "%.9f" % (hz / 1_000_000.0)
        return text.rstrip("0").rstrip(".") + " MHz"
    if abs(hz) >= 1_000:
        text = "%.9f" % (hz / 1_000.0)
        return text.rstrip("0").rstrip(".") + " kHz"
    return "%s Hz" % hz


def page(title, body):
    return (
        "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n"
        "<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, "
        "initial-scale=1\">\n"
        "<title>%s</title>\n<style>%s</style>\n</head>\n<body>\n"
        "<nav><a href=\"index.html\">REBER</a>"
        "<a href=\"dossiers.html\">Dossiers</a>"
        "<a href=\"catches.html\">Catches</a>"
        "<a href=\"unexplained.html\">The unexplained file</a>"
        "<a href=\"astronomy.html\">Astronomy</a></nav>\n"
        "%s\n"
        "<p class=\"meta\">Generated from register.json, the register's "
        "single source of truth, in reber-format 1. Generated pages are "
        "never hand-edited.</p>\n"
        "</body>\n</html>\n" % (esc(title), STYLE, body))


def event_summary(event):
    if event.get("summary"):
        return event["summary"]
    data = event.get("data") or {}
    if data.get("callsign"):
        return "Callsign %s." % data["callsign"]
    velocity = data.get("velocity") or {}
    if data.get("alt_ft") is not None or velocity:
        parts = []
        if data.get("alt_ft") is not None:
            parts.append("altitude %s ft" % format(data["alt_ft"], ","))
        if velocity.get("speed_kt") is not None:
            parts.append("speed %.1f kt" % velocity["speed_kt"])
        if velocity.get("heading_deg") is not None:
            parts.append("heading %.1f degrees" % velocity["heading_deg"])
        if parts:
            return "Telemetry: " + ", ".join(parts) + "."
    parts = []
    if data.get("shape"):
        parts.append("emission of %s shape" % data["shape"])
    if data.get("band"):
        parts.append("in the %s band" % data["band"])
    if data.get("snr_db") is not None:
        parts.append("at %.1f dB SNR" % data["snr_db"])
    if parts:
        return "Unknown " + ", ".join(parts) + "."
    return "Filed without a summary."


def event_row(event):
    cells = [
        esc(event.get("time_utc") or ""),
        esc(fmt_freq(event.get("freq_hz"))),
        esc(event.get("grade") or ""),
        esc(event.get("desk") or ""),
        esc(event.get("emitter") or ""),
        esc(event_summary(event)),
    ]
    if event.get("flash"):
        cells[2] = "FLASH - " + cells[2]
    return "<tr>" + "".join("<td>%s</td>" % c for c in cells) + "</tr>"


def events_table(events):
    rows = "\n".join(event_row(e) for e in events)
    return ("<table>\n<tr><th>Time (UTC)</th><th>Frequency</th>"
            "<th>Grade</th><th>Desk</th><th>Emitter</th>"
            "<th>Record</th></tr>\n%s\n</table>" % rows)


def by_section(register, section):
    return [e for e in register["events"]
            if section in e.get("sections", [])]


def render_index(register, register_bytes):
    stations = {s["station_id"]: s for s in register["stations"]}
    catches = by_section(register, "events")
    unexplained = by_section(register, "unexplained")
    latest = sorted(catches, key=lambda e: (e.get("time_utc") or "",
                                            e.get("id") or ""),
                    reverse=True)[:10]
    out = ["<h1>REBER</h1>",
           "<p>%s</p>" % esc(INTRO),
           "<p>%s</p>" % esc(BUDGET_LINE % (
               register["budget_bytes"] // 1_000_000, register_bytes)),
           "<h2>Stations</h2>"]
    for sid in sorted(stations):
        station = stations[sid]
        mine_d = [d for d in register["dossiers"]
                  if d["station_id"] == sid]
        mine_e = [e for e in register["events"]
                  if e["station_id"] == sid]
        mine_u = [e for e in mine_e if "unexplained" in e["sections"]]
        out.append("<h3>%s</h3>" % esc(station.get("display") or sid))
        out.append("<p>%s</p>" % esc(station.get("receiver") or ""))
        out.append(
            "<p class=\"meta\">%d watches on record, %d dossiers, "
            "%d published events, %d entries in the unexplained file.</p>"
            % (len(station.get("watches", [])), len(mine_d),
               len(mine_e), len(mine_u)))
        for watch in station.get("watches", []):
            out.append(
                "<p class=\"meta\">Watch %s: %s to %s. %s</p>"
                % (esc(watch.get("watch_id") or ""),
                   esc(watch.get("start_utc") or ""),
                   esc(watch.get("end_utc") or ""),
                   esc(watch.get("note") or "")))
    out.append("<h2>Latest catches</h2>")
    out.append(events_table(latest) if latest
               else "<p>No catches published yet.</p>")
    out.append(
        "<p>The full record stands in the sections above: %d dossiers, "
        "%d graded catches, %d entries in the unexplained file, and "
        "the astronomy account of predicted satellite passes and their "
        "outcomes.</p>"
        % (len(register["dossiers"]), len(catches), len(unexplained)))
    return page("REBER - Received Emissions Bulletin and Exchange Register",
                "\n".join(out))


def render_dossiers(register):
    out = ["<h1>Dossiers</h1>",
           "<p>One dossier per emitter, kept by the station that heard "
           "it: what the emitter is, its standing in the record, and "
           "when it was heard. Standings are statements about the "
           "record, never about the world beyond it.</p>"]
    for dossier in register["dossiers"]:
        out.append("<div class=\"entry\">")
        out.append("<h3>%s</h3>" % esc(dossier["key"]))
        out.append(
            "<p class=\"meta\">Kind: %s. Standing: %s. First heard %s, "
            "last heard %s, across %d published events in %s.</p>"
            % (esc(dossier.get("kind") or ""),
               esc(dossier.get("standing") or ""),
               esc(dossier.get("first_heard_utc") or ""),
               esc(dossier.get("last_heard_utc") or ""),
               dossier.get("events_count") or 0,
               esc(", ".join(dossier.get("watches", [])))))
        out.append("<p>%s</p>" % esc(dossier.get("summary") or ""))
        out.append("</div>")
    if not register["dossiers"]:
        out.append("<p>No dossiers published yet.</p>")
    return page("REBER - Dossiers", "\n".join(out))


def render_catches(register):
    catches = by_section(register, "events")
    # Newest first, then a stable pass lifts FLASH items to the head.
    catches.sort(key=lambda e: (e.get("time_utc") or "",
                                e.get("id") or ""), reverse=True)
    catches.sort(key=lambda e: 0 if e.get("flash") else 1)
    out = ["<h1>Catches</h1>",
           "<p>The graded events worth a reader's time, FLASH items at "
           "the head. Grades are the publishing station's own: "
           "CONFIRMED for a decoded or otherwise settled record, "
           "PROBABLE for a strong but partial one, UNRESOLVED for an "
           "honest unknown.</p>"]
    out.append(events_table(catches) if catches
               else "<p>No catches published yet.</p>")
    return page("REBER - Catches", "\n".join(out))


def render_unexplained(register):
    entries = by_section(register, "unexplained")
    entries.sort(key=lambda e: (e.get("time_utc") or "",
                                e.get("id") or ""), reverse=True)
    out = ["<h1>The unexplained file</h1>",
           "<p>Every emission the publishing stations heard and could "
           "not explain, in full. An entry here is a statement about "
           "the record: the emission was measured, characterised as "
           "far as the station's desks could take it, and left honestly "
           "open. Comparison by frequency across stations is the "
           "file's purpose.</p>"]
    out.append(events_table(entries) if entries
               else "<p>The unexplained file is empty.</p>")
    return page("REBER - The unexplained file", "\n".join(out))


def render_astronomy(register):
    passes = by_section(register, "astronomy")
    passes.sort(key=lambda e: (e.get("aos_utc") or "",
                               e.get("id") or ""))
    out = ["<h1>Astronomy</h1>",
           "<p>The astronomy account: satellite passes predicted by "
           "the publishing stations, and what came of each. Pass times "
           "are UTC. Station-relative pass geometry is withheld under "
           "the scrub rules and is listed in each bundle's withheld "
           "manifest.</p>"]
    if not passes:
        out.append("<p>No passes published yet.</p>")
    for event in passes:
        data = event.get("data") or {}
        out.append("<div class=\"entry\">")
        out.append("<h3>%s</h3>" % esc(data.get("sat")
                                       or event.get("emitter") or ""))
        out.append(
            "<p class=\"meta\">Pass from %s to %s UTC. Outcome: %s. "
            "Grade: %s.</p>"
            % (esc(event.get("aos_utc") or ""),
               esc(event.get("los_utc") or ""),
               esc(event.get("outcome") or ""),
               esc(event.get("grade") or "")))
        out.append("<p>%s</p>" % esc(event_summary(event)))
        out.append("</div>")
    return page("REBER - Astronomy", "\n".join(out))


def main(argv):
    here = os.path.dirname(os.path.abspath(__file__))
    register_path = argv[1] if len(argv) > 1 else os.path.join(
        here, "register.json")
    out_dir = argv[2] if len(argv) > 2 else here
    with open(register_path, "rb") as fh:
        raw = fh.read()
    register = json.loads(raw.decode("utf-8"))
    pages = {
        "index.html": render_index(register, len(raw)),
        "dossiers.html": render_dossiers(register),
        "catches.html": render_catches(register),
        "unexplained.html": render_unexplained(register),
        "astronomy.html": render_astronomy(register),
    }
    for name in sorted(pages):
        with open(os.path.join(out_dir, name), "w", encoding="utf-8",
                  newline="\n") as fh:
            fh.write(pages[name])
    print("GENERATED %d pages from %s" % (len(pages), register_path))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
