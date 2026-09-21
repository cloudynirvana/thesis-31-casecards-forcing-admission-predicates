# NSTG CaseCards as predicates for tip-ODE forcing admission without guideline-to-Θ leakage

**Thesis #31.** Computational research, set out in Nile University B.Sc. chapter order for handoff.

**Depends on:** Thesis #2 (NSTG CaseCards; guideline ≠ coefficient) and Thesis #19 (forcing admission under evidence gates).

**Author:** Kelechi Emeka Ogbonna  
**Email:** kelechiogbonna300@gmail.com  
**GitHub:** https://github.com/cloudynirvana  
**Date:** 21 September 2026

Can NSTG CaseCards encode the Thesis #19 admission predicates so that guideline or knowledge text is refused as a coefficient write, while a protocol-constant known forcing with named provenance is still admitted?

On this ledger, they can. The legal card stores the checks as tokens and contains no digit. A loader refuses a card with a JSON number and a card whose prose contains a dose token. Five declared rows yield two eligible rows, `row_north` and `row_west`. Twenty calls are issued. Nineteen return refused, including the touchpoint sentence aimed at `d0`, the framing sentence aimed at `k_glyc`, a parsed `0.42` aimed at `d0`, and a side score copied into the amplitude. One call, A01, admits `row_north` as the provenance of `u_phyto = 1`. The SHA-256 of kinetic Θ is `912e19683e84f4fe7c4cddee6672eb08d26af94ddf79dcde23d876a8eac7b251` before the calls and the same string after the admission. The forcing digest changes. The glucose-like path does not. The stress-like equilibrium moves from 0.500000 to 0.200000.

No kinetic string is taken from Thesis #19, and no seed card is taken from Thesis #2. The digest above is not Thesis #19's digest. This deposit does not claim a dose or an efficacy.

This is research only. It is not a medical device, not clinical decision support, not a dose, and not a cure. No document DOI is registered.

See [DISCLAIMER.md](DISCLAIMER.md). The manuscript is [THESIS.md](THESIS.md).

## Files

| Path | Role |
| --- | --- |
| `THESIS.md` | Manuscript (Chapters 1 to 5, Vancouver citations) |
| `THESIS.pdf` | PDF built from the Markdown |
| `build_pdf.py` | Regenerates `THESIS.pdf` |
| `CITATION.cff` | Citation metadata, no document DOI |
| `DISCLAIMER.md` | Research-only boundary |
| `sim/predicate_ledger.py` | CaseCard predicate ledger and bounded tip field (no random draw) |
| `sim/cards/cc_tip_admission.json` | Digit-free CaseCard that encodes the admission checks |
| `sim/cards/cc_poison_leaf.json` | Loader fixture: numeric leaf, refused |
| `sim/cards/cc_poison_prose.json` | Loader fixture: dose and schedule tokens, refused |
| `sim/claims.json` | Declared rows. Not a transcription of another results file |
| `sim/results.json` | Numbers cited in Chapter Four |
| `sim/figures/` | Eligibility, digests, trajectories, equilibria |

## Reproduce

```bash
python3 -m pip install -r sim/requirements.txt
python3 sim/predicate_ledger.py
python3 build_pdf.py
```

NumPy, SciPy, and Matplotlib are required for the ledger. The PDF step also needs the `markdown` and `weasyprint` packages. Regenerating the script rewrites `sim/results.json` and `sim/figures/`. The card-file and claims-file SHA-256 pins are inside `sim/predicate_ledger.py`. A byte edit that does not update the pin raises.

## Cite

Ogbonna KE. NSTG CaseCards as predicates for tip-ODE forcing admission without guideline-to-Θ leakage [Internet]. Thesis #31 computational research thesis. 21 September 2026 [cited YYYY Mon DD]. Available from: https://github.com/cloudynirvana/thesis-31-casecards-forcing-admission-predicates

Machine-readable fields are in `CITATION.cff`. Add a document DOI there only after one exists.

Hub index, for cataloguing only: [research-theses-hub](https://github.com/cloudynirvana/research-theses-hub).

## Licence

Text and sketch code are MIT, with attribution. Computational research only.
