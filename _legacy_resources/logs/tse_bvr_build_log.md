# TSE BVR Build Log

## Summary

- Number of source rows indexed: 26
- Number of treated municipality-zone rows in clean output: 2794
- Number of direct TSE-code matches to IBGE: 5097
- Number of exact matches to IBGE: 360
- Number of manually confirmed spelling-variant matches: 2
- Number of fuzzy candidate matches: 0
- Number of unresolved matches: 0
- Hybrid or partial-treatment cases explicitly coded in final data: 0

## Validation

- Duplicate rows on `municipality_id + zone + year_first_treat + url_tse`: 0
- Invalid UF values: none
- Malformed municipality IDs: none
- Non-normalized municipality names in final output: 0
- Municipality IDs missing from IBGE table: 0

## Unresolved Items

1. The 2015-2016 and 2017-2018 municipality annexes were identified but remained blocked behind SinTSE access-rejected pages when fetched via `requests` and via a headless browser.
2. The 2012 rows are verified from an official TSE attachment, but not mapped one-by-one to individual provimentos.
3. The 2014 rows are benchmarked with the official TSE article and recovered from the official election-year administrative file rather than a fully recoverable annex list.
4. Municipality-level hybrid treatment for 2016 remains unresolved because the official TSE 2016 electorate file does not carry an explicit municipal hybrid status field.
5. Municipality-level 2018 hybrid rows are preserved in `data/interim/tse_bvr/hybrid_2018_review.csv` but excluded from the clean municipality-level first-treatment dataset.
