# SDS section checker: helper tools

Open items and out-of-scope findings are listed in [BACKLOG.md](BACKLOG.md).

Review aid for Safety Data Sheets (SDS), Sections 4–8 and 10. It is not sign-off: a competent person must verify every finding.

The checklist and the reference sources live in the "SDS Resources by Section" Sheet (Resources and By Section tabs). This repo holds the scripts that feed a run.

## Requirements

- Python 3 with `beautifulsoup4`: `pip install beautifulsoup4`
- `pdftotext` (poppler-utils) for PDFs
- `pandoc` for .docx
- LibreOffice (`soffice`) for .doc, .odt and .rtf
- `curl`

A scanned PDF with no text layer needs OCR first. The extractor stops and says so.

## 1. Extract an SDS: `tools/sds_text.py`

```bash
python3 -I tools/sds_text.py path/to/sds.pdf out/my_sds
```

It writes `out/my_sds/sds.txt` (the full text) and `out/my_sds/sds.json`. The JSON holds:

- Sections 1–16 with their headings and text, and subsections (e.g. 10.1–10.6)
- H, EUH and P codes and UN numbers, for the whole document and per section
- CAS numbers, checksum-validated
- dates found near the start (for the revision date)

It recognises headings such as `SECTION 10: Stability and reactivity`, `10. STABILITY AND REACTIVITY` and `Section 10 - ...`. Check `sections_found` in the JSON: a missing number means the heading wasn't recognised. That could be the SDS itself (a Section 10-A1 finding) or an unusual layout.

## 2. Look up data by CAS: `tools/lookup.py`

```bash
python3 -I tools/lookup.py out/my_sds 7681-52-9 7732-18-5
```

It writes `out/my_sds/lookup_<CAS>.json`, one per CAS, plus the raw pages under `out/my_sds/raw/`. Each result records its URL and retrieval date. When a source fails, the entry says `unreachable` or `not found`. Nothing is filled in from elsewhere.

| Source | What it returns | Status |
|---|---|---|
| ICSC (chemicalsafety.ilo.org) | Chemical dangers, physical dangers, fire and explosion, storage, spillage | Automated |
| NIOSH Pocket Guide (cdc.gov) | Incompatibilities & reactivities | Automated |
| CAMEO Chemicals (noaa.gov) | Reactivity profile, reactive groups, air & water reactions, potentially incompatible absorbents | Automated |
| PubChem | Formula, used for the elemental-composition checks | Automated. PubChem sometimes refuses with "server busy": rerun later |
| GESTIS (dguv.de) | Search link only | Manual: the article text needs an API key, which we don't have |

These sources are always checked by hand:

- **Sites that refuse automated clients:** ECHA CHEM and the C&L Inventory, the ERG (PHMSA) and UNECE (GHS, Manual of Tests and Criteria). Checks that rely on them report "not checked – needs verification".
- **Paid or offline:** Bretherick's (paid) and CRW 4 (desktop tool).

The lookups run at about one request per second. Keep it that way.

## 3. Check a section: `tools/check_s10.py`, `tools/check_s4.py`, `tools/check_s567.py`

```bash
python3 -I tools/check_s10.py out/my_sds/sds.json out/my_sds --declared GB --type substance --out out/my_sds/s10.json
python3 -I tools/check_s4.py  out/my_sds/sds.json out/my_sds --declared GB --type substance --out out/my_sds/s4.json
python3 -I tools/check_s567.py out/my_sds/sds.json out/my_sds --declared GB --type substance   # Sections 5, 6, 7 (or --section 6)
```

Each checker ends its output with a **Not run** list: rows that are manual, not yet coded, or not applicable to the jurisdiction or SDS type. No finding is not the same as passed.

For a full report on one SDS (all five sections, a summary, findings, and the Not run list at the end):

```bash
python3 -I tools/report.py path/to/sds.pdf out/my_sds --declared GB --type substance
```

Each script applies that section's checklist and prints every finding: check ID, status (fail/warning/info/not checked), what the SDS says and what's expected. A cross-section finding is counted under the section that needs fixing. For example, a bracketed P334 phrase in Section 2 is reported as `2-L1`.

Both scripts work out the jurisdiction from the SDS itself: the regulation cited and the supplier address. If that differs from `--declared`, they print `** MISMATCH **` and still run under the declared jurisdiction.

Duplicate rule (all sections, `tools/dedupe.py`): when two findings report the same gap (for example the same P-statement action or the same condition), only one is kept. That is the higher-severity one; on a tie, the more specific layer (B before A, C, D). The kept finding says which checks it also covers, e.g. `[also covers 4-C1 (P338)]`.

Known limits:
- US precautionary-statement wording (OSHA App C) is published only as images, so US text is matched against the CLP wording.
- GHS Rev.10 codes P316–P319 are matched as equivalents of P310–P315. That mapping has not been checked against the GHS Rev.10 text, because unece.org isn't reachable from here.
- The rules are keyword heuristics tuned on the regression set. Read every finding: the output is a review aid, not a verdict.

### How rules read the SDS text: `tools/textinterp.py`

Every rule asks one shared module how to read wording, instead of matching raw keywords:

- **negation**: "does not contain nanomaterials" is not a nanoform;
- **"no data" statements**, including "No additional information available", and whether a reason is given;
- **cross-references**: "(see section 7)" counts as covering Section 7;
- **synonyms**: flush = rinse = wash with water; "obtain medical attention" = "get medical advice";
- **"such as" lists**: they are examples, not a checklist; any one of them, or general wording, meets the requirement.

Unit tests are in `tests/test_textinterp.py`. Run them with `python3 -I -m unittest discover -s tests`.

### How much an ingredient's reference data counts: `tools/refgate.py`

Reference data (ICSC, CAMEO, NIOSH) describe a pure substance. Before such data can drive a finding, the rule checks the ingredient's concentration in Section 3 (the top of any range; "< 1" counts as just below 1) and the product's physical form.

The thresholds are in `config/reference_gating.json`; edit them there:

| Band | Default | What the data can drive |
|---|---|---|
| main | ≥ 10 % (or a substance SDS) | fails and warnings, as before |
| minor | 1–10 % | warnings only where the data fits the mixture's own classification (e.g. flammability advice only if the mixture is classified flammable); general incompatibility data at most info |
| trace | < 1 % | nothing, except explosive, peroxide-forming, water-reactive or toxic-gas data, at most a warning |

Data for a gas apply only to a gas or aerosol product, and dust/powder statements only to a solid. Each report lists what was capped or not applied. It also gives a coverage warning for any main ingredient with no ICSC, CAMEO or NIOSH record. Unit tests are in `tests/test_refgate.py`.

## 4. Re-run the regression set: `tools/run_regression.py`

```bash
python3 -I tools/run_regression.py /path/to/test_sds_folder
```

This runs Sections 10, 4, 5, 6 and 7 for every case in `regression/cases.json`. Each case lists its file name and SHA-256, the declared jurisdiction and the SDS type. The cases are:

- sodium hypochlorite solution (US, mixture)
- acetone (GB, substance)
- calcium carbide (GB, substance)
- the same calcium carbide SDS declared as EU, which must flag the mismatch

The PDFs themselves aren't committed, because they're supplier documents. Put them in one folder and pass its path.

There are also fifteen synthetic cases in `regression/synthetic/`, each clearly marked "SYNTHETIC TEST SDS — NOT A REAL PRODUCT". They are committed and need no folder. Each one triggers one rule:

- GHS Rev.10 codes → 2-L2
- "induce vomiting" with Asp. Tox. 1 → 4-B1 fail
- "induce vomiting" with Acute Tox. 4 oral only → 4-B1 warning
- flammable gas with no leaking-gas caveat or ignition control → 5-B3, 6-B3, 7-B1 fail
- the same flammable gas done right → no fails (checks for false fails)
- explosive 1.1 with no evacuation advice and no P401 storage → 5-B2, 7-B8 fail
- oxidising solid cat. 1 with no separation from combustibles → 5-B2, 7-B2 fail
- organic peroxide with "Store at temperatures not exceeding 0 °C" on the label but no temperature in 7.2 → 7-B3 fail
- chemically unstable gas whose 10.2 says "stable" → 10-B4 fail
- explosive whose 10.4 lacks shock, friction and static → 10-B5 fail
- organic peroxide with an incomplete 10.2–10.4 → 10-B7 fail
- peroxide-forming ether (EUH019, EUH044, EUH031) → 10-B13, 10-B14, 10-B15 fail
- inhibited monomer with no stabiliser or polymerisation in Section 10 → 10-A10, 10-A11 fail
- correct controls: peroxide former with EUH019/EUH044/EUH031 handled, and inhibited monomer with the inhibitor named → no Section 10 fail (checks for false fails)

To regenerate them, run `SOURCE_DATE_EPOCH=1795737600 python3 -I regression/synthetic/make_synthetic.py`. If the files change, update their SHA-256 in `cases.json`.

Options:
- `--section 10` or `--section 4` runs one section only.
- `--live` re-queries the sources instead of using the snapshots in `regression/lookups/`.
- `--write-expected` overwrites `regression/expected/section*/` with the current results.

Use `--write-expected` only for an intended, reviewed rule change, and commit the new expectations together with that change. The exit code is 0 when everything matches and 1 on any difference.

## Checklist status and coverage

The Checklist tab of the Sheet is the master copy. `checklist/coverage.csv` is generated from it and is not edited by hand:

1. Claude reads the tab's columns B (Check ID) and F:G (Applies to, Status) with the Claude Docs connector. Python cannot reach the Sheet directly.
2. `python3 -I tools/sync_checklist.py --from-transcript` saves those cells to `checklist/sheet_export.json` (with the Sheet revision and the date read) and rewrites `coverage.csv`. It stops, naming the row, on a Status or "Applies to" value it cannot read.

`CLAUDE.md` tells each session to do this at the start, and whenever you say you've edited the Sheet. Each engine declares the IDs it implements in a `CODED` set. In CI, `sync_checklist.py --check` fails when `coverage.csv` isn't what the committed export gives, and `tools/check_coverage.py` fails when a row's status and the engines disagree, or when a declared ID never appears in its engine.

## Continuous integration

`.github/workflows/regression.yml` runs the unit tests, the Sheet-export check and the coverage check, then `python3 -I tools/run_regression.py --synthetic-only` on every push and pull request, on Ubuntu 24.04 with pandoc 3.1.3, the version the expected results were generated with. Supplier SDSs stay local, so CI covers the synthetic cases only.

## Network access

These hosts must be allowed in the cloud environment: chemicalsafety.ilo.org, www.cdc.gov, cameochemicals.noaa.gov, gestis-api.dguv.de, pubchem.ncbi.nlm.nih.gov and publications.europa.eu (EU legal texts). The personal cloud environment "SDS_Section_by_Section" allows them.

`www.cdc.gov` refuses some custom user agents. The script uses curl's default.
