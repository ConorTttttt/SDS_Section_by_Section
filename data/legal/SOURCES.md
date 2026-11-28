# Bundled CLP legal tables

| File | Content |
|---|---|
| `clp_annex_iv_eu_2027-01-01.json` | Annex IV Part 1 (Tables 6.1–6.5): every precautionary statement with its English wording and each hazard class / category / conditions-for-use row |
| `clp_annex_i_label_p_eu_2027-01-01.json` | Annex I label-element tables: signal word and listed precautionary statements per class/category column (tables printed as one text block are not included) |
| `clp_category_h_eu_2027-01-01.json` | Annex I label-element tables: hazard class + category → hazard statement codes |
| `clp_annex_vi_codes_eu_2027-01-01.json` | Annex VI Part 1 Table 1.1 hazard class and category codes |

**Source:** Regulation (EC) No 1272/2008 (CLP), consolidated version 01.01.2027, CELEX 02008R1272-20270101, EUR-Lex
(<https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:02008R1272-20270101>), retrieved 27 Nov 2026. Annex IV
Part 1 is identical in the 01.07.2026 consolidation. Consolidated texts are documentation; only the Official Journal
versions are authentic.

**Reuse:** EU legal texts are reused under the Commission's reuse policy, with credit to the source. Changes: the tables
were extracted from the consolidated text and restructured as JSON; statement wording is unchanged. The SHA-256 of the
text the tables were extracted from is in each file (`source_sha256`).

**How they were made:** `python3 -I tools/legal_tables.py <consolidated text> --celex 02008R1272-20270101 --retrieved 2026-11-27`.
The consolidated text (XHTML from the Publications Office, flattened to one table row per line) is not stored here.
The same files are bundled in ConorTttttt/Classification (#46), where `verification/build_annex_iv.js` embeds them in the
calculator. `tests/test_legal_tables.py` checks their consistency.

**Known differences inside the consolidated text** (both readings accepted by `tools/verify_p_calculator.py` and `tests/test_legal_tables.py`):
- Explosives: Annex I Table 2.1.2 lists P501; Annex IV Table 6.5 lists P503.
- Self-heating substances: Annex IV lists P410; Annex I Table 2.11.2 does not.
- Effects on or via lactation: Annex IV lists P202; Annex I Table 3.7.3 does not.
- CMR and lactation: Annex IV limits P201 to consumer products ("omit where P202 is used"); the Annex I tables list it
  without that condition.
- Skin corrosion: some Annex IV rows list sub-categories 1A, 1B, 1C but not Category 1; Annex I Table 3.2.5 gives
  them one column, so Category 1 takes the 1A rows.
- Skin irritation: the Annex IV row for P313 lists "2, 3"; EU CLP has no skin irritation Category 3.
