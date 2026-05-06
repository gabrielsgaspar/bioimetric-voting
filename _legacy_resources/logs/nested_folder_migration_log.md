# Nested Folder Migration Log

- Source folder removed: `biometric-registration-brazil/`
- Non-cache files moved up to the repo root structure: `59`
- Existing root files replaced with the nested copies: `20`
- Python cache files skipped and deleted with the nested folder: `10`

## Replaced Root Files

- `AGENTS.md`
- `README.md`
- `docs/PROJECT.md`
- `paper/main.tex`
- `paper/appendix/appendix_main.tex`
- `paper/frontmatter/abstract.tex`
- `paper/frontmatter/title.tex`
- `paper/inputs/macros.tex`
- `paper/inputs/notation.tex`
- `paper/inputs/packages.tex`
- `paper/inputs/settings.tex`
- `paper/references/references.bib`
- `paper/sections/01_introduction.tex`
- `paper/sections/02_institutional_background.tex`
- `paper/sections/03_data_and_measurement.tex`
- `paper/sections/04_bvr_and_electorate_size.tex`
- `paper/sections/05_bvr_and_electorate_composition.tex`
- `paper/sections/06_bvr_and_political_trust.tex`
- `paper/sections/07_backlash_and_electoral_integrity.tex`
- `paper/sections/08_conclusion.tex`

## New Top-Level Additions From The Nested Folder

- `.agents/skills/did-estimators/`
- `.agents/skills/lapop-brazil-harmonizer/`
- `.agents/skills/literature-review/`
- `.agents/skills/tse-bvr-treatment-dataset/`
- `.agents/skills/tse-eleitorado-education-gender/`

## Notes

- The nested folder appeared to be a duplicate project copy inside the working repository.
- For conflicting files, the nested versions were used because they were newer than the current root copies.
- `__pycache__/` and `.pyc` artifacts were not moved into the root repository.
- Empty directories inside the nested project were removed rather than recreated at the root.
