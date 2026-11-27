# SDS section checker: helper tools

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

## 3. Check Section 10: `tools/check_s10.py`

```bash
python3 -I tools/check_s10.py out/my_sds/sds.json out/my_sds --declared GB --type substance --out out/my_sds/findings.json
```

It applies the tuned Section 10 checklist and prints each finding: check ID, status (fail/warning/info/not checked) and what the SDS says against what's expected.

It also works out the jurisdiction from the SDS itself: the regulation cited and the supplier address. If that differs from `--declared`, it says `** MISMATCH **`, but it still runs the checks under the declared jurisdiction.

The rules are keyword heuristics tuned on the regression set below. Read every finding: the output is a review aid, not a verdict.

## 4. Re-run the regression set: `tools/run_regression.py`

```bash
python3 -I tools/run_regression.py /path/to/test_sds_folder
```

`regression/section10/cases.json` lists the test SDSs, each with its SHA-256, declared jurisdiction and SDS type:

- sodium hypochlorite solution (US, mixture)
- acetone (GB, substance)
- calcium carbide (GB, substance)
- the same calcium carbide SDS declared as EU, which must flag the mismatch

The PDFs themselves aren't committed, because they're supplier documents. Put them in one folder and pass its path.

By default the runner uses the stored lookup snapshots in `regression/section10/lookups/`, so results stay repeatable. Add `--live` to query the sources again. Results can drift as the sources change.

Expected findings per check are in `regression/section10/expected/`. The exit code is 0 when every case matches and 1 on any difference. Run it after every rule change. When a change is intended, update the expected file in the same commit.

## Network access

These hosts must be allowed in the cloud environment: chemicalsafety.ilo.org, www.cdc.gov, cameochemicals.noaa.gov, gestis-api.dguv.de, pubchem.ncbi.nlm.nih.gov and publications.europa.eu (EU legal texts). The personal cloud environment "SDS_Section_by_Section" allows them.

`www.cdc.gov` refuses some custom user agents. The script uses curl's default.
