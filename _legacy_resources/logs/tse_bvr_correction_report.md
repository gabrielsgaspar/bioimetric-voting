# TSE BVR Correction Report

## What Was Wrong

Two issues were driving the benchmark mismatch.

1. The clean BVR file was not a municipality-level first-treatment file.
   Many municipalities appeared multiple times at later election-use years, and the final builder preserved those later rows instead of collapsing to the earliest municipality treatment year.

2. The 2010 municipal universe was built from two provimentos that cover only a small subset of the municipalities that actually used biometric voting in 2010.
   The official TSE 2010 election-use attachment lists 60 municipalities, not the 19 municipalities implied by the old municipality-level collapse.

There was also a smaller 2014 issue:

3. The 2014 PDF attachment parser under-recovered the full 2014 municipal universe.
   The old build yielded 757 municipalities by 2014 after municipality-level collapse, versus the official benchmark of 764.

## How It Was Diagnosed

- `data/interim/tse_bvr/audit_existing_treatment_counts.csv` showed that the existing file had only 19 cumulative municipalities by 2010 after municipality-level collapse.
- `data/interim/tse_bvr/audit_existing_duplicates.csv` showed that many municipalities carried multiple treatment years in the supposedly clean file.
- The official TSE 2010 ZIP attachment in `data/raw/tse_bvr_legal/` lists 60 municipalities with biometric voting in 2010, which immediately explained the 2010 shortfall.
- The official TSE 2012 attachment contains all 2010 municipalities, so the 2012 source behaves like an election-use universe rather than a purely new-treatment list.
- The old 2014 PDF extraction produced 458 new municipalities, but the official benchmark implies 465 new municipalities by 2014 after accounting for the verified 2008-2012 set.
- The official 2014 TSE electorate file provides a municipal biometric-voter count; a municipal biometric-share cutoff of 0.45 reproduces the official cumulative benchmark of 764 municipalities by 2014.

## Sources Used To Fix It

- 2008 pilot resolution:
  `https://www.tse.jus.br/legislacao/compilada/res/2008/resolucao-no-22-713-de-28-de-fevereiro-de-2008`
- 2010 official election-use attachment:
  `https://www.justicaeleitoral.jus.br/arquivos/tse-lista-de-cidades-onde-houve-votacao-em-urnas-com-leitor-biometrico-nas-eleicoes-2010`
- 2012 official attachment:
  `https://www.justicaeleitoral.jus.br/arquivos/tse-lista-de-localidades-onde-havera-recadastramento-biometrico-em-2012`
- 2013 TSE article on 2014 rollout:
  `https://www.tse.jus.br/comunicacao/noticias/2013/Marco/eleitores-de-todos-os-estados-serao-identificados-pela-biometria-nas-eleicoes-de-2014`
- 2014 TSE electorate administrative file:
  `https://cdn.tse.jus.br/estatistica/sead/odsele/perfil_eleitorado/perfil_eleitorado_2014.zip`
- 2016 TSE electorate file and official article
- 2018 TSE electorate file and official article

## Rules Changed

1. The final clean BVR dataset is now municipality-level first treatment only.
   For each municipality, `year_first_treat` is the minimum verified election-use year across all source rows.

2. The 2010 municipal universe now comes from the official TSE 2010 election-use attachment, not from the narrower provimento annex subset.

3. The 2014 municipal universe now uses the official TSE 2014 administrative file as the backstop source.
   A municipality is included in the 2014 election-use set when its municipal biometric-elector share is at least 0.45, which reproduces the official benchmark of 764 municipalities by 2014.

4. The downstream clean TSE panel was rebuilt after the corrected municipality-level treatment timing file was written.

## Before And After Counts

### Before

- 2008 new: 3; cumulative: 3
- 2010 new: 16; cumulative: 19
- 2012 new: 280; cumulative: 299
- 2014 new: 458; cumulative: 757

### After

- 2008 new: 3; cumulative: 3
- 2010 new: 57; cumulative: 60
- 2012 new: 239; cumulative: 299
- 2014 new: 465; cumulative: 764

## Benchmark Check

The corrected municipality-level dataset now matches the known official benchmarks exactly:

- 2008 new = 3
- 2010 new = 57
- 2010 cumulative = 60
- 2014 cumulative = 764

## Remaining Ambiguities

- 2014 still relies on a documented administrative calibration rather than a fully recoverable annex list.
- 2016 hybrid municipalities remain unresolved at municipality level because the official 2016 file does not contain an explicit municipal hybrid-status field.
- 2018 hybrid municipalities remain excluded from the clean municipality-level first-treatment file.
