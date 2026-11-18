# REBER

REBER is the Received Emissions Bulletin and Exchange Register: a public journal where listening stations publish their scrubbed records in one shared format, so that an emission one antenna cannot explain can be checked against what every other antenna heard.

## What gets published

The record, not the raw take. Emitter dossiers with their habits and standings. Graded catches worth a reader's time, with FLASH items at the head. The unexplained file in full, because it is the journal's reason to exist. The astronomy account: satellite passes predicted, and what came of each. Evidence travels only as small excerpts under the budget below - short audio of machine signals and tones, thumbnail spectrograms, decoded products. Bulk IQ never travels.

Every record is scrubbed before it is published, and the scrub is a program, not a promise. The verifier in scrub.py fails a bundle closed on any of its rules: no coordinates and nothing shaped like them, no bearings or distances measured from the publishing station, all times in UTC, no network addresses or local infrastructure detail, voice audio stays at the publishing station by default. Every bundle carries a manifest of what was withheld and under which rule, so the scrub itself is auditable by any reader who wonders at a gap.

## The space budget

The register is text-first and stays small on purpose. Its total budget is 20 megabytes, evidence included, and the budget is stated here and enforced by the scrub verifier on every bundle. Evidence excerpts are capped per item: images at 150 kilobytes, audio at thirty seconds and 200 kilobytes. register.json is the single source of truth and the pages are generated from it; when the budget presses, excerpts age into their summaries while the text record, which costs almost nothing, is permanent.

## The register

register.json holds the whole register. generate.py turns it into the static site - index.html and one page per section - in plain HTML with no JavaScript. Generation is deterministic, so the generated pages are committed and never hand-edited. Bundles enter the register only through apply.py, which runs the scrub verifier first and refuses a failing bundle whole.

## How another station joins

Publish in the exchange format defined in FORMAT.md, named and versioned reber-format 1. Compose a bundle from your own records, scrub it the way your own station's rules require, and bring it here by pull request with the bundle file included. The bundle passes the same scrub verifier as every other bundle - the rules are the price of admission for everyone, which is what makes the shared file trustworthy - and once verified it is applied to register.json and the site is regenerated in the same change. The unexplained file is the collaboration's heart: per-station sections in one schema, comparable by frequency and time across every station that files.

## Admission and how submissions are handled

A station's first bundle is its application for admission. It is read in full, run through the scrub verifier, and checked against the format by hand. If it passes, the station takes its place in the register with a section of its own, and its later bundles are filed the same way and verified on their own merits. Admission never asks a station to disclose more than the format carries: the register does not request a station's location, and a station section describes the receiving equipment in general terms only, the way the founding station's does.

A submission that fails is sent back with the exact rule it tripped named, so the station can repair the bundle and file again. Nothing is dropped silently, and nothing is published in part. A submission that carries what the scrub exists to keep home - coordinates, bearings, or another station's details - is refused outright rather than repaired here. A station that files records it cannot stand behind loses its standing, and its section is marked accordingly, because the register's only asset is that every entry in it can be trusted.

There is no fee and no form beyond the bundle itself. Admission is granted to records, not to reputations: a first bundle from an unknown station is read exactly as carefully, and exactly as fairly, as the founding station's own.

## Moderation

Moderation is ordinary repository review. Contributions are read like any other change, checked against the format and the scrub, and merged or sent back on their merits. A record that cannot pass the verifier does not publish, whatever its source.

## Namesake

The register is named for the engineer who built a dish in his own backyard in 1937, ran the first systematic radio surveys of the sky, and published his records when no institution would - the lone station whose published log became a field. The acronym is constructed on the surname: Received Emissions Bulletin and Exchange Register.

## License

AGPL-3.0. See LICENSE.
