# SDS phrase recommender: design (for review, not yet built)

Status: draft for the user's review, 27 Nov 2026. No recommender code has been written. Stage 1 starts only after
approval of this document and answers to the open questions (section 12).

Every output of the recommender is labelled **"DRAFT – for review by a competent person"**.

## 1. Goal and scope

The recommender is the reverse of the checker. From a formulation it drafts SDS content for Section 2 (label elements),
4, 5, 6, 7 and 10, and later 8. Every recommended phrase carries its source: a rule ID, a legal text with version, or a
reference record with its snapshot date. Nothing comes from memory.

| Stage | Input | Drafts | Built from |
|---|---|---|---|
| 1 | Classification, P-statements, signal word (from the user's engine), physical form, jurisdiction, audience | 2.2 label elements; 4.1-4.3, 5.1-5.3, 6.1-6.4, 7.1-7.3, 10.1-10.6 | Inverted checklist rules (A and B rows), bundled CLP Annex III/IV tables, own phrase library |
| 2 | Stage 1 + ingredient identities and concentrations | 10.5 incompatibilities, 10.6 decomposition products, 7.2 segregation, 5.2 combustion products | Local reference database (ICSC/CAMEO/NIOSH/PubChem snapshots) through the existing gating config, element rule |
| 3 | Stage 2 + OEL lists | Section 8 (OELs with list, edition, date; PPE matched to hazards) | Section 8 checks (once coded), bundled OEL lists, HSG53 filter table |

Out of scope: classifying the mixture (the user's engine does that), Sections 1, 3, 9, 11-16, translations,
and any claim that a draft is compliant.

## 2. Architecture

```
formulation.json ──► engine adapter ──► classification.json ──┐
 (or calculator export                (user's CLP engine;       │
  .clpmix.json)                        run, not re-implemented) ▼
                                                     recommender core
 data/legal/*.json  (Annex III/IV, Annex II,  ──►   ├─ stage 1: inverted checklist rules
  App C/D, EH40 …, each with version/date)           ├─ stage 2: reference data via refgate
 data/reference.sqlite (local snapshots, dated) ──►  └─ stage 3: Section 8
 phrases/*.json (own phrase library)            ──►        │
 checklist/checklist.csv (offline checklist)    ──►        ▼
                                                   draft SDS model (same shape as sds.json)
                                                           │
                                                           ▼
                                                   existing checker (check_s10/s4/s567, later s8)
                                                           │
                                                           ▼
                                          report.md / report.html  (+ optional SDS skeleton)
```

- The draft is built in the same in-memory structure the checker already reads (`sections`, `subsections`,
  `codes_by_section`). The closed loop (section 9) needs no PDF round trip.
- Reused modules, no duplicated logic: `textinterp.py` (wording), `refgate.py` + `config/reference_gating.json`
  (stage 2), `coverage.py` (Not-run lists), the engines' trigger sets (classification → rule), `dedupe.py`.
- The P-statement triggers that today live inside the engines (e.g. `check_s4.P_ACTIONS`, the 5-7 B-rule conditions)
  move into one shared, data-driven table built from the bundled Annex IV extract, used by both checker and recommender.
  This is a refactor of the checker as well, verified by the existing regression (no expected result may change).

## 3. Offline operation and data bundling

### 3.1 Run time

The finished tool runs on the user's computer with no internet and no Claude: deterministic Python code plus bundled
data. Run-time requirements:

| Need | Why | Install |
|---|---|---|
| Python 3.10+ (standard library only) | checker, recommender, reports, SQLite reference DB | python.org installer |
| `pdftotext` (poppler) | reading PDF SDSs (checker) | Windows: poppler binaries in the release zip; macOS: Homebrew; Linux: package manager |
| Node.js 18+ | optional: only to run the user's classification engine headless | nodejs.org; not needed if the calculator's results file is used (section 4) |

`pandoc` (used today for synthetic `.docx` fixtures) and `beautifulsoup4` (used today by `lookup.py`) are only needed
by maintenance scripts that run online; the run-time path replaces them (`.docx` read with `zipfile` + XML from the
standard library).

### 3.2 Data bundles

Every bundle has a manifest entry: source URL, version/consolidation date, date retrieved, licence finding, SHA-256.
Every finding and every recommended phrase prints the date of the bundle it came from.

| Bundle (planned path) | Content | Source and version (as already verified in this project) | Bundle in repo? |
|---|---|---|---|
| `data/legal/clp_annex_iii_eu_2027-01-01.json` | H/EUH codes and wording | EU CLP consolidated 1 Jan 2027 (Cellar) | yes, see 3.3 |
| `data/legal/clp_annex_iv_eu_2027-01-01.json` | P codes, wording, class, category, conditions | same | yes |
| `data/legal/clp_annex_iii_iv_gb.json` | GB equivalents | legislation.gov.uk (GB CLP) | yes (OGL) |
| `data/legal/reach_annex_ii_{eu,gb}.json` | subsection titles and duties | EU 2020/878; GB REACH Annex II | yes |
| `data/legal/osha_app_c.json`, `osha_app_d.json` | US P-statement wording and conditions; SDS sections | osha.gov HTML (FR citations recorded) | to verify (3.3) |
| `data/legal/eh40_2005_4th_2020.json` | GB WELs | HSE EH40/2005, 4th ed. 2020 | yes (OGL) |
| `data/legal/eu_oels_*.json` | BOELV/IOELV tables | 2004/37 consol. 2024-04-08; IOELV directives; 2026/2450 | yes, see 3.3 |
| `data/legal/osha_z_tables.json` | US PELs | eCFR 1910.1000 | to verify (3.3) |
| `data/legal/hsg53_filters.json` | filter types | HSE HSG53 4th ed. 2013, Table 7 | yes (OGL) |
| `data/reference.sqlite` | ICSC/CAMEO/NIOSH/PubChem records by CAS, with snapshot dates | built by `tools/refresh_reference.py` from the current lookup snapshots | **no**: built and kept locally (see 3.3) |
| `checklist/checklist.csv` | full checklist (all columns A-G) | Sheet Checklist tab, synced when online | yes |

`tools/refresh_reference.py` (run when online) re-queries the sources for a CAS list, writes new dated snapshots into
`reference.sqlite`, and prints what changed since the previous snapshot. The checker and recommender only ever read the
local database. The Sheet stays the editing copy: the existing sync (now reading all columns) writes
`checklist/checklist.csv`, which the tool reads offline.

### 3.3 Licence findings

Read from the sources' own pages on 27 Nov 2026 where reachable. "Not verified" means the terms page could not be read
from this environment; nothing below is from memory.

| Source | What its page says | Verified? | Proposed handling |
|---|---|---|---|
| legislation.gov.uk (GB CLP, GB REACH) | "All content is available under the Open Government Licence v3.0 except where otherwise stated"; EUR-Lex-derived content "reused under the terms of the Commission Decision 2011/833/EU" | yes | bundle with OGL attribution |
| HSE (EH40, HSG53) | Crown material may be re-used "free of charge in any format or medium, under the terms of the Open Government Licence"; preferred acknowledgement "Contains public sector information published by the Health and Safety Executive and licensed under the Open Government Licence"; some images may not be Crown-owned | yes | bundle extracted tables with that acknowledgement |
| CDC / NIOSH Pocket Guide | "Most of the information on the CDC and ATSDR websites is not subject to copyright, is in the public domain … There are, however, a few exceptions" (contractor/grantee or third-party material) | yes (CDC-wide policy; no NPG-specific exception found) | eligible to bundle; keep the source and date per record |
| ICSC (ILO/WHO) | ILO pages: "© 1996-2018 International Labour Organization (ILO) \| Copyright and permissions" (the ILO terms page was not reachable); WHO INCHEM: "© World Health Organization All rights reserved" | partly | **do not bundle** in the repo; the user's refresh script builds a local copy on the user's own computer; ask ILO/WHO for permission if the tool is ever shared |
| CAMEO Chemicals (NOAA) | no reuse statement found on the help pages read; datasheets include the NFPA diamond (third-party content) | no | treat as not verified: local copy only, no NFPA ratings stored |
| PubChem (NCBI) | policy pages not readable from here | no | local copy only (only molecular formulas are used) |
| EUR-Lex / Publications Office | legal-notice page returned no content (bot protection); reuse basis known only via legislation.gov.uk's reference to Decision 2011/833/EU | no (indirect) | bundle extracted EU tables with source attribution once the user confirms; see open question |
| eCFR / OSHA | legal-status page not reachable (redirect to unblock.federalregister.gov) | no | as EUR-Lex: confirm before bundling |
| GESTIS (IFA/DGUV) | site is a script application; terms not readable | no | stays a manual link |
| ECHA (CHEM, C&L) | refuses automated access | n/a | stays manual |
| ACGIH TLVs | licensed | n/a | stays manual (agreed) |
| eSDScom phrase catalogue | licence not confirmed by the user | n/a | not used (agreed), see open question on SDS-Phrases |

**Existing issue to decide now:** the public repository already contains ICSC and CAMEO text excerpts in
`regression/lookups/` (4 supplier cases). Given the ICSC "All rights reserved" notice, propose moving these snapshots
to the git-ignored `local/` folder (CI uses only synthetic cases, which have no lookups).

### 3.4 Packaging and updates

Proposal: **command-line tool plus a static HTML report**, no server and no desktop framework.

```
sds check   path/to/sds.pdf  --jurisdiction GB --type mixture      → report.html + report.md
sds recommend formulation.json                                      → draft.html + draft.md (+ skeleton.docx later)
sds refresh --cas-from formulation.json   (online only)             → updates data/reference.sqlite
```

- Delivered as a versioned zip from GitHub Releases (code + legal bundles + poppler for Windows), or `git pull` for
  the user's own clone. A release note lists the bundle versions and checklist revision.
- Reference data stay in the user's local `data/reference.sqlite`, never overwritten by an update; `sds refresh`
  updates them when online.
- A desktop app or local web server adds installs and attack surface for no gain at this stage; the HTML report opens
  in any browser offline. Revisit if non-technical colleagues need it.

## 4. Integration with the user's classification engine

Repository read: `ConorTttttt/Classification` (commit `be42ceb`), read-only, not modified.

### 4.1 What it provides (from its README and `verification/engine.js`)

- A single-file offline browser calculator (`clp_mixture_calculator.html`) and the same engine as a Node module
  (`verification/engine.js`, Node 18+), exporting `classify`, `selectArticle26`, `selectArticle27`, `selectArticle28`,
  `report`, `blankIngredient`, `normalise` and more.
- EU CLP Annex I mixture rules (consolidated 1 Jul 2026) with a calculation trail; Article 26 pictograms, Article 27
  H/EUH precedence, Article 28 P-statements.
- Explicit limits it documents: physical hazards other than flammable liquids are not calculated (manual entries);
  Article 28 uses "a LIMITED initial catalogue of 21 verified Annex IV P-statement codes" and shows "at most six ranked
  candidates"; bridging principles and tested-mixture data are not modelled.
- Input: the calculator's saved file `{ "app": "clp-mixture-calculator", "version": 1, "mixture": {...} }`, with
  ingredients `{name, cas, pct, hcodes, hcodeDetails, acute{…}, skinCorr, eye, …, scl{}}`.
- A separate Python prototype in the same repository (`labelling-packaging-assistant/`) takes an already-approved
  classification and applies its own 27-entry provisional Annex IV policy (`eu/label_v2/annex_iv_policy.json`).

### 4.2 Interface: exchange a file, not a library call

The engine is JavaScript and the checker is Python, so a direct library call is not possible without embedding Node.
Proposal: **a versioned JSON file (`classification.json`) is the contract**, produced in one of two ways:

1. *Preferred:* an "Export for SDS" button added to the calculator (a small change in the user's repository, only with
   approval) that writes the result of `classify()` plus `selectArticle28()` candidates to `classification.json`.
   Fully offline, no Node needed.
2. *Fallback:* `tools/engine_bridge.js` (in this repository) runs `classify()` on a `.clpmix.json` under Node 18+ with
   the engine file from a pinned commit of the user's repository.

`classification.json` (adapter format, version 1):

```json
{
  "schema": "sds-classification/1",
  "engine": {"repo": "ConorTttttt/Classification", "commit": "be42ceb", "module": "verification/engine.js"},
  "jurisdiction": "EU",
  "mixture": {"name": "…", "physical_state": "liquid", "flash_point_c": 23, "ph": null},
  "classification": [
    {"class": "Flam. Liq.", "category": "2", "h": "H225", "basis": "calculated|manual", "trail_ref": "…"}
  ],
  "label": {
    "signal_word": "Danger",
    "pictograms": ["GHS02", "GHS07"],
    "hazard_statements": ["H225", "H319"],
    "euh_statements": [],
    "omitted_hazard_statements": [{"code": "H318", "overridden_by": "H314", "basis": "Annex III Part 1(b)"}],
    "p_statements_selected": ["P210", "P280", "P305+P351+P338"],
    "p_statements_candidates": [{"code": "P233", "decision": "not selected", "legalStatus": "candidate"}]
  },
  "warnings": ["…engine warnings verbatim…"],
  "manual_classifications": []
}
```

The adapter (`tools/adapters/clp_calculator.py`) reads this file, validates it, and maps it to the recommender's
internal input. It never recalculates a classification.

### 4.3 How the two P-statement sets are used

- **Section 2.2 (label elements):** the engine's selected P-statements are shown as the proposed label set, with
  wording from the bundled Annex IV table. Where the bundled Annex IV conditions call for a statement the engine did not
  select (beyond its six), the report lists it as "Annex IV candidate not on the proposed label" for the competent
  person; the recommender does not override the engine's selection.
- **Sections 4-7 and 10:** the content must cover every relevant P-statement and classification consequence, not only
  the six on the label (Annex II requires consistency with the classification). These sections are driven by the full
  classification and the bundled Annex IV conditions table.

### 4.4 One-off audit (after approval; findings reported, neither engine changed)

1. **P-selection given the same classification.** For each of the 27 cases (4 supplier, 15 synthetic, 8 blind), feed
   the SDS's own Section 2 classification to `selectArticle28()` (and to the Python assistant's policy), and compare
   with the P-statements that our verified Annex IV conditions table assigns. Report every code that one side assigns
   and the other does not, with the Annex IV row.
2. **Classification from Section 3 (informational).** Build a `.clpmix.json` from each SDS's Section 3 (names, CAS, %,
   ingredient H-codes) and compare the engine's classification with the SDS's Section 2. Differences are expected
   (missing SCLs, M-factors, test data) and are reported, not scored.

### 4.5 What the engine needs to run offline

The browser calculator already runs offline ("Works offline, no AI or installation required"); its optional Gemini
features are online-only and are not used. Node 18+ is needed only for the fallback bridge. Pictogram files
(`pictograms/`) are needed for rendering only. The engine covers EU CLP only (see open questions for GB and US).

## 5. Formulation input format

One JSON file per product. Composition reuses the calculator's ingredient fields, so one file can feed both tools.

```json
{
  "schema": "sds-formulation/1",
  "product": {
    "name": "Example Degreaser", "jurisdiction": "GB", "sds_type": "mixture",
    "audience": ["professional", "consumer"],
    "physical_state": "liquid", "form": "aerosol|liquid|paste|powder|granules|gas",
    "flash_point_c": 45, "initial_boiling_point_c": 120, "ph": 7.5,
    "identified_uses": ["Industrial degreasing (PROC 7, 10)"],
    "transport": {"un_number": "1993", "class": "3"}
  },
  "classification_file": "example.classification.json",
  "ingredients": [
    {"name": "hydrocarbons, C9-C11", "cas": null, "ec": "919-857-5", "pct_min": 30, "pct_max": 50,
     "role": "solvent", "hcodes": "H226 H304 H336 EUH066"},
    {"name": "4-methoxyphenol", "cas": "150-76-5", "pct_max": 0.01, "role": "stabiliser"}
  ],
  "facts": {
    "stabiliser": {"name": "4-methoxyphenol", "ppm": 50, "needs_oxygen": true},
    "control_temperature_c": null, "sadt_c": null, "antidote": null,
    "decomposition_onset_c": null, "test_methods": {}
  }
}
```

`facts` carries what a classification cannot say (rules that need them are listed in 6.3). Missing facts produce a
placeholder and a "needs data" flag, never a guessed value.

## 6. How the checklist rules invert

Principle: each B row (classification-driven) becomes a "must include" item with the official wording or a library
phrase; each A row (structure/content) becomes a skeleton slot; C rows are satisfied by construction (one source feeds
all sections) and re-verified by the closed loop; D rows belong to stage 2 (reference data) or stage 3 (Section 8).

### 6.1 Rows that invert directly (stage 1)

| Section | Rows | Generated item | Source cited in the output |
|---|---|---|---|
| 2.2 | — | signal word, pictograms, H/EUH, P (engine) with official wording | Annex III/IV bundle, engine commit |
| 4.1 | 4-A6, 4-A7, 4-B1-B6 | route-by-route first aid: P301/P330/P331, P302/P352, P303+P361+P353, P305+P351+P338, P304+P340, P308+P313, P335/P334, P306+P360, P336+P315; "do not induce vomiting" (H304/H314); first-aider protection; clothing removal | CLP Annex IV conditions; Annex II 4.1.2 |
| 4.1/4.3 | 4-A8, 4-B5 | urgency wording for P310 classes; medical advice for CMR/STOT | CLP Annex IV P310, P308+P313 |
| 4.2 | 4-C2, 4-A10 | symptoms keyed to each classified health hazard, using the H-statement wording (e.g. H319 "Causes serious eye irritation") plus library symptom phrases marked "verify" | Annex III; phrase library |
| 5.1 | 5-A4, 5-B1, 5-B5, 5-C3 | suitable/unsuitable media from form, flammability and water reactivity; P370+P378 media; water jet unsuitable for flammable liquids | Annex IV P370+P378 conditions; phrase library |
| 5.2 | 5-A5, 5-B4 | burst/explosion hazard (H280/H229), flammable vapour (H224-H226) | H-statement wording |
| 5.3 | 5-A6, 5-B2, 5-B3, 5-B4 | SCBA and protective clothing; explosion-risk and leaking-gas-fire statements (P370+P372+P380+P373, P377, P381, P370+P376) | Annex IV |
| 6.1-6.4 | 6-A6, 6-A7, 6-B1-B5 | ignition sources (P381), non-sparking tools, keep out of drains (P273), collect spillage (P391), absorb (P390), water-reactive spills, dust control, respiratory protection reference, cross-references to 8 and 13 | Annex IV; Annex II 6.1.1-6.4 |
| 7.1-7.2 | 7-A4, 7-A5, 7-A6, 7-B1-B14 | P210, P233, P240-P243, P403(+P235), P220, P420, P244, P411, P234, P410(+P412), P231+P232, P402+P404, P222, P407, P413, P401, P250, P406, P261/P271, P272, P273, P282; hygiene and incompatibility handling; storage basics | Annex IV; Annex II 7.1.1-7.2 |
| 10.1-10.4 | 10-A7, 10-A9, 10-B1-B17 | reactivity/stability statements consistent with the classification (never "no hazardous reactions" for a reactivity class); heat/ignition/static; aerosol/gas burst and 50 °C; unstable gas; explosive (shock, friction, static); self-reactive/organic peroxide temperature; pyrophoric air; self-heating; water-reactive (water in 10.5, moisture in 10.4, gas named); oxidiser vs combustibles; H290 metals; EUH019/044/031/032/206/018/209/207 | H/EUH wording; Annex IV conditions; Annex II 10.x |
| all | 4-A1-A5, 5-A1-A3, 6-A1-A4, 7-A1-A3, 10-A1-A6 | headings, numbered subsections (EU/GB) or App D elements (US), "no data" statements with a reason slot | Annex II Part B; App D |

### 6.2 Rows that belong to later stages

| Rows | Why | Stage |
|---|---|---|
| 10-A8, 10-A13, 10-C4, 10-C5, 10-D1, 10-D4-D6, 5-C1, 5-C2, 6-C1, 7-C1, 4-D1-D3, 5-D1, 6-D1, 7-D1 | need ingredient identities, concentrations and reference data | 2 |
| Section 8 rows (draft) | need OEL lists and the Section 8 checks | 3 |

### 6.3 Rows that cannot be inverted (the draft carries a placeholder and a "needs data" flag)

| Rows | Missing fact | Handling |
|---|---|---|
| 4-B7 | antidote / specific treatment (P320/P321 classes) | placeholder unless `facts.antidote` given |
| 4-A9 | none (a "don't" rule) | generator never writes clinical steps into 4.1 |
| 6-A5 | suitable fabric for responders' clothing | placeholder; filled in stage 3 from Section 8 glove/clothing data if available |
| 7-A7 | specific end uses / exposure scenario | from `product.identified_uses`; otherwise placeholder |
| 7-B3, 10-B7 | storage/control temperature for self-reactives and organic peroxides | from `facts.control_temperature_c` / label P411; else "needs data" (never guessed) |
| 10-A10, 10-A11 | stabiliser name and conditions; polymerisation conditions | from `facts.stabiliser`; else "needs data" |
| 10-A15 | test method for SADT/decomposition values | from `facts.test_methods` |
| 10-B6 | desensitised explosive: shelf life, verification method | from `facts`; else "needs data" |
| 10-A16 | which nanoform each statement covers | from `facts` |
| 10-C3, 10-C7, 7-C2 | consistency with Section 9 / NFPA ratings | checked in the closed loop when the user supplies those values |
| 10-J1, 2-L1, 2-L2, X-R1 | checks on an existing document (jurisdiction, label text, duplicates) | not generators; run in the closed loop |
| info / good-practice rows (e.g. 4-C3, 7-C4, 7-B12) | not legal duties | offered as optional phrases, marked "good practice" |

## 7. Phrase library

Location: `phrases/` in this repository, one JSON file per section, plus `phrases/README.md` with the governance rules.
Official H/P wording is **not** in the phrase library: it is read from the bundled Annex III/IV/App C tables, so it
cannot drift.

```json
{
  "id": "S7.1-HYG-001",
  "section": "7.1",
  "text": {"EU": "Do not eat, drink or smoke in work areas. Wash hands after use. Remove contaminated clothing and protective equipment before entering eating areas.",
           "GB": "= EU", "US": "= EU"},
  "triggers": {"always": true},
  "satisfies": ["7-A5"],
  "source": {"type": "own wording", "basis": "REACH Annex II 7.1.2 (examples)", "legal_ref": "data/legal/reach_annex_ii_eu.json#7.1.2"},
  "placeholders": [],
  "status": "draft|approved",
  "approved_by": null, "approved_on": null,
  "notes": ""
}
```

- `triggers` uses the same vocabulary as the checker (H/EUH/P codes, physical form, jurisdiction, audience, facts).
- `satisfies` lists the checklist rows the phrase is meant to meet; the closed loop proves it.
- A unit test fails if a phrase has no `source`, cites a row that does not exist in `checklist/checklist.csv`, or
  contains an H/P code whose official wording is not taken from the legal bundle.
- New phrases enter as `draft`; only phrases the user approves are used without a "draft phrase" marker.

## 8. Output format

1. **Report** (`draft.md` and `draft.html`): header (product, jurisdiction, engine commit, bundle versions and dates,
   checklist revision), the "DRAFT – for review by a competent person" banner, then per subsection:
   - the drafted text;
   - for every sentence: its source (rule ID, legal table and version, phrase ID and status, or reference record and
     snapshot date);
   - "needs data" items and placeholders;
   - Annex IV candidates the engine did not put on the label (2.2);
   - the checker's findings on the draft (closed loop) and its Not-run list.
2. **Optional SDS skeleton** (`draft_sds.md`, and `.docx` later if wanted): Sections 1-16 with 2.2, 4, 5, 6, 7 and 10
   filled and every other section marked "to be completed". Each page carries the DRAFT banner.

## 9. Closed loop

1. The draft model is passed to the existing checker functions with the same jurisdiction, type and classification.
2. Findings are attached to the output. Target: **no fails**. A fail on a generated draft is a recommender bug (or a
   checker false positive) and is listed for review; warnings are shown with their reason.
3. Regression: every generated draft for the test set is stored as an expected result, so a later rule change that
   makes a draft fail is caught in CI.

## 10. Test plan

| Step | Cases | Measure |
|---|---|---|
| Unit tests | rule inversions, phrase-library validation, adapter schema | all pass in CI |
| Closed loop | each test case's classification → draft → checker | 0 fails; warnings reviewed |
| Supplier comparison | 4 supplier + 8 blind + the 5 holdout SDSs (real) | per subsection: "must include" items the supplier also has; items the supplier is missing (checker findings); supplier statements the draft lacks (reviewed: our gap or supplier extra) |
| Engine path | same real SDSs, formulation from Section 3 → engine → draft | differences caused by classification differences reported separately from recommender differences |
| Synthetic | 15 synthetic cases (classification given) | 0 fails; every B-row trigger represented |
| Holdout | fresh SDSs not used for design | reported before any tuning, same as the checker's holdout rule |

Real-SDS reports and drafts quote supplier documents and stay in `local/`.

## 11. Stages 2 and 3 (designed now, built later)

- **Stage 2** uses the local reference database through `refgate` (same bands, form rules, unclassified-mixture cap)
  and the element rule: 10.5 families and named reagents with their record and snapshot date; 10.6 and 5.2 products by
  element (C → CO/CO2, N → NOx, S → SOx, P → phosphorus oxides, halogens → HX), separated into fire products (5.2)
  and use/storage/heating products (10.6); 7.2 segregation mirroring 10.5. Main ingredients without any record get the
  existing coverage warning and a "needs data" item.
- **Stage 3** starts after the Section 8 checks are coded. 8.1 limits come only from bundled lists with list, edition,
  and date checked, within the conversion and rounding rules already approved; PPE is matched to the hazards using the
  P280/P284/P283/P282 conditions and HSG53 filter types; glove material and breakthrough time remain "needs data"
  (manufacturer data, EN ISO 374 is paid).

## 12. Open questions for the user

1. **Engine repository.** Your message named "[owner/repo]". I used `ConorTttttt/Classification` (it matches the
   description). Correct?
2. **Adapter route.** May I propose an "Export for SDS" button (results JSON) in the calculator, as a separate change for
   your approval in that repository? Or should the recommender rely on the Node bridge only?
3. **GB and US.** The engine implements EU CLP only. For GB, CLP Annex I/III/IV is identical to the EU for the codes
   verified so far, so EU results could be used with a GB label; is that acceptable, with a warning? For US, HazCom
   classification differs (e.g. Eye 2A/2B, Flam. Liq. 4, no EUH); should US drafts wait for a US classification source,
   or accept a manually entered US classification?
4. **Physical hazards** other than flammable liquids are manual in the engine. Should the formulation file carry the
   manual physical classification, or should these be entered in the calculator (its "Manual classifications")?
5. **Label P-statements.** Confirm the split in 4.3: the label shows the engine's selection; Sections 4-7 and 10 use the
   full Annex IV conditions table, and extra Annex IV candidates are listed for review, not added to the label.
6. **The labelling-packaging-assistant** (same repository) has a separate 27-entry Annex IV policy. Should the audit
   include it, and is it meant to replace the calculator's Article 28 selection later?
7. **Phrase library vs SDS-Phrases.** Your `SDS-Phrases` repository is an offline phrase engine built on the eSDScom 5.5
   catalogue. Do you hold an eSDScom licence that allows that use? If yes, should the recommender read its SQLite
   catalogue (stage 1 free text) instead of building a separate library? If no, I build the own-wording library as
   described in section 7.
8. **ICSC excerpts already in the public repository** (`regression/lookups/`). Move them to `local/` now?
9. **EUR-Lex and eCFR tables.** Their reuse pages could not be read here. Bundle the extracted EU (via the reuse
   decision cited by legislation.gov.uk) and US federal tables now, or wait until the terms are read?
10. **US P-statement wording.** OSHA App C is published as images in eCFR and as HTML on osha.gov (read via the fetch
    agent, quotes limited to 125 characters). Is the osha.gov HTML acceptable as the bundled source?
11. **Strong peroxide formers** (`config/reference_gating.json`): which source should define the list? Prudent Practices
    (NAP) could not be fetched here. Also: below 1 %, peroxide-forming data still give a warning, while 1-10 % now gives
    info unless EUH019 or listed. Should the below-1 % rule follow the same condition?
12. **Packaging.** CLI + static HTML report (section 3.4): acceptable, or do you want a local web page from the start?
13. **Repository visibility.** This repository is public. The tool and bundles will contain only material whose licence
    allows it (section 3.3); confirm that is the intent, or should the repository become private?
