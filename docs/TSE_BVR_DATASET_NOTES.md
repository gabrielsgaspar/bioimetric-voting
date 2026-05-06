# TSE BVR Dataset Notes

## Scope

This note documents the construction of the municipality-level dataset of first verified biometric voter registration election use in Brazil.

The current build combines direct legal and attachment evidence for 2008-2012 with official TSE election-year administrative or open-data evidence for 2014, 2016, and 2018. The evidence base used in the clean municipality-level dataset is:

- the 2008 pilot resolution,
- the official TSE ZIP attachment listing the municipalities where biometric voting occurred in 2010,
- the official TSE ZIP attachment listing municipalities apt for biometric identification in 2012,
- the official TSE 2014 electorate file, calibrated to the official municipality benchmark of 764 municipalities by 2014,
- the official TSE 2016 electorate open-data file, calibrated to the official TSE article reporting 1,540 municipalities voting totalmente com biometria in 2016,
- and the official TSE 2018 electorate open-data file, which explicitly labels municipalities as `Biométrico`, `Híbrido`, or `Sem biometria` in the election-year snapshot.

The dataset therefore now covers the first verified election-use years 2008, 2010, 2012, 2014, 2016, and 2018 for municipality-level full-biometric treatment. The 2015-2016 and 2017-2018 legal annexes were identified and indexed, but their municipality lists remain blocked behind SinTSE access controls in this environment. Municipality-level hybrid treatment for 2016 and municipality-level hybrid first-use timing for 2018 remain partially unresolved and are documented below.

## Source Inventory

- `data/interim/tse_bvr/tse_legal_sources_index.csv` records every TSE source downloaded or indexed for this build.
- `data/raw/tse_bvr_legal/` preserves the raw HTML, ZIP, and PDF downloads used in the build.
- `data/raw/ibge/` preserves the raw IBGE municipality API response used for the official municipality crosswalk.

## Interpretation Rules

### Year-first-treat rule

- `year_first_treat` is the first election year in which biometric identification was verified as being used.
- For 2008, the pilot resolution explicitly states that the listed municipalities would use biometric identification on election day.
- For 2010, the official TSE ZIP attachment listing the municipalities where biometric voting occurred in the 2010 election is treated as the election-use source. The legal provimentos remain indexed as supporting context but are not used as the municipal universe because they cover only a subset.
- For 2012, the official TSE ZIP attachment from the `Revisao eleitoral` page is treated as the verification source for municipalities apt for biometric identification in the 2012 elections.
- For 2014, the official TSE article gives the benchmark count and the official TSE 2014 electorate file is used to recover the election-use municipality set. A municipality is retained when its municipal biometric-elector share is at least 0.45, which reproduces the official cumulative benchmark of 764 municipalities by 2014.
- For 2016, the official TSE article states that 1,540 municipalities would vote totalmente com biometria and 840 would use sistema híbrido. The municipality-level TSE open-data electorate file is then used to identify which municipalities belong to the full-biometric 2016 group. A municipality is retained in the clean municipality-level dataset when its municipal biometric-elector share is at least 0.95, which reproduces the official full-biometric municipality count.
- For 2018, the official TSE article states that 2,793 municipalities would vote exclusively with biometrics and 1,533 would use hybrid identification. The official TSE 2018 electorate open-data file explicitly labels each municipality as `Biométrico`, `Híbrido`, or `Sem biometria`, allowing direct identification of municipality-level full-biometric treatment in 2018.

### Evidence versus inference

- 2008 and 2010 rows rely on direct legal-act text or inline annex text.
- 2010 rows rely on the official TSE election-use attachment rather than the narrower provimento annexes.
- 2012 rows rely on an official TSE summary attachment that is explicit about the election cycle, but it is not a one-to-one legal-act annex extract. This is a documented limitation.
- 2014 rows rely on the official TSE benchmark article plus the official TSE 2014 election-year electorate file because the archived PDF attachment under-extracts the full municipal universe in this environment.
- 2016 municipality-level full-biometric rows rely on an official TSE election-year open-data file plus a documented calibration rule anchored to the official TSE municipality count.
- 2018 municipality-level full-biometric rows rely on an explicit municipal status label in the official TSE election-year open-data file.
- 2018 hybrid municipalities are preserved in an interim review file but excluded from the clean municipality-level first-treatment dataset because municipality-wide first use may predate 2018 and zone-specific coverage is not explicit.

## Name-Standardization Rules

- Municipality names are lower-cased.
- Accents are removed with Unicode normalization.
- Asterisks from TSE tables are stripped.
- Punctuation is removed and whitespace is collapsed.
- Matching is always constrained within state before any fuzzy candidate generation is attempted.

## Matching Notes

- `data/clean/tse_bvr/ibge_municipalities.csv` is built from the official IBGE `localidades/municipios` API endpoint.
- `data/interim/tse_bvr/name_matching_review.csv` records every municipality-name match.
- Four within-state spelling variants have now been manually confirmed and are carried as `manual_override` matches in the review file: `santo antonio do leverger` in `MT`, `iguaraci` in `PE`, `machadinho do oeste` in `RO`, and `amparo de sao francisco` in `SE`.
- Fuzzy matching is used only to generate candidates. Any non-exact rows should be reviewed before treating the dataset as final for publication-grade analysis.

## Ambiguous and Unresolved Cases

- Exact municipality-level annex extraction remains unresolved for the 2013-2014 complementary provimentos and for the 2015-2016 and 2017-2018 program cycles.
- Zone-specific versus municipality-wide treatment cannot be fully resolved for 2012 from the accessible official attachment, because it reports municipality-level coverage without zone identifiers.
- The 2014 election-use set is calibrated from the official administrative file. The benchmark is matched, but the file does not include an explicit municipal status label, so the 0.45 cutoff should be treated as a documented administrative calibration rather than a direct legal annex extract.
- Hybrid identification in 2016 is documented as an important edge case by the official TSE article, but municipality-level hybrid coding is not directly recoverable from the blocked annexes or from an explicit status field in the 2016 electorate file.
- The 2018 electorate file does explicitly flag hybrid municipalities. These rows are preserved in `data/interim/tse_bvr/hybrid_2018_review.csv`, but they are excluded from the clean municipality-level first-treatment dataset because partial municipality coverage may have begun before 2018 and municipality-zone identifiers are not available in the open-data file.

## Legal and Timing Caveats

- `url_tse` is the exact official TSE URL used as evidence in the build. For 2012 and 2014 rows, this may be an official TSE attachment rather than an individual provimento page.
- For 2014, 2016, and 2018 full-biometric rows, `url_tse` points to the official TSE election-year administrative or open-data source used for municipality identification.
- The current clean dataset should be treated as a verified lower bound on municipality-level first use, with especially conservative handling of hybrid treatment.
