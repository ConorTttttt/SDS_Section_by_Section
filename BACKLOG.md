# Backlog

These are findings and open items that fall outside the sections built so far. Each one names the checklist it belongs to.

## Out-of-scope findings from the test SDSs

| SDS | Section | Finding | Belongs to |
|---|---|---|---|
| Acetone (Fisher, rev 14, 19-Oct-2023; GB) | 2.2 | Classified Eye Irrit. 2 (H319), but the label omits P305+P351+P338. CLP Annex IV assigns that combination to Eye Irrit. 2 (EU and GB text, verified). | Section 2 checklist |
| Sodium hypochlorite (Fisher/Acros, rev 11, 19-Dec-2025; US) | 11 | Section 11 says "Inhalation: Not an expected route of exposure", but the product is classified STOT SE 3 (respiratory irritation, H335) and Section 4 gives inhalation first aid. | Section 11 checklist |
| Calcium carbide (SLS CHE1468, rev 1.1; GB) | 2.2 | P223 is printed as "Keep away from any possible contact with water, because of violent reaction and possible flash fire." The official CLP text is "Do not allow contact with water." | Section 2 checklist |
| Calcium carbide (SLS CHE1468) | 1 / 16 | Cites Reg. (EU) 2015/830 together with GB CLP. For EU use, that format has been superseded since 1 Jan 2023. | Section 1/16 checklist |

## Verification still open

- **GHS Rev.10 codes P316–P319.** The equivalence to P310–P315 is unverified. It will be checked against GHS Rev.11 Annex 3, which the user will upload. Until then, findings say "UNVERIFIED".
- **OSHA Appendix C (US P-statement wording).** eCFR and federalregister.gov publish it only as images. US text is matched against the CLP wording for now.
- **EUH211/EUH212.** These are deleted in the EU text consolidated to 1 Jan 2027, following titanium dioxide notice C/2025/6670. They were never in GB CLP. This matters for the Section 2 and Section 8 checklists.
- **Sources that refuse automated access:** ECHA CHEM / C&L Inventory (Azure gateway), ERG/PHMSA (Akamai) and UNECE (Cloudflare). The checks that rely on them report "not checked".
- **PubChem** intermittently refuses requests with "server busy", so elemental-composition checks fall back to the formulas given in the SDS.
- **GESTIS** article text needs an API key we don't hold, so it stays a manual link.

## Engine coverage

Status per Checklist row is in the Checklist tab (column G), mirrored in `checklist/coverage.csv`. `tools/check_coverage.py` keeps the two in line with the engines.

| Section | Coded / total (27 Nov 2026) | Not coded | Manual (reason) |
|---|---|---|---|
| 10 (incl. linked 5-C1, 5-C2, 6-C1, 7-C1 and 10-J1) | 51 / 57 | — | D2 (Bretherick's is paid), D3 (CRW 4 is a desktop tool), D7 (ERG refuses automated access), D8 (C&L Inventory refuses automated access; GB MCL not yet parsed), D9 (ECHA CHEM refuses automated access), D10 (needs supplier test reports) |
| 4 (incl. 2-L1, 2-L2) | 26 / 27 | — | A11 (informational; its triggers are reported by 4-B7, 4-D2, 4-D3) |
| 5 | 16 / 16 | — | — |
| 6 | 14 / 15 | C3 (info) | — |
| 7 | 25 / 27 | — | D2 (ECHA CHEM refuses automated access), D3 (HSE guidance documents) |

## Other

- The Sheet title still reads "(Sections 4-8)". It can only be renamed in the Sheet page.
