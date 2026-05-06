# TSE BVR Treatment Dataset

## Purpose

Build and maintain a reproducible dataset of Brazilian municipalities treated by biometric voter registration, with careful separation between:

- the year of legal act or recadastramento,
- and the first election year in which biometrics were actually used.

The target output is a municipality-level or municipality-zone-level dataset with:

- `municipality_id`
- `municipality_name`
- `state`
- `zone`
- `url_tse`
- `year_first_treat`

## Required Inputs

- Official TSE legal pages and linked official attachments.
- Official IBGE municipality identifiers.
- Raw-download directories under `data/raw/`.
- Intermediate and clean output directories under `data/interim/` and `data/clean/`.

## Target Outputs

- `data/interim/tse_bvr/tse_legal_sources_index.csv`
- `data/interim/tse_bvr/name_matching_review.csv`
- `data/clean/tse_bvr/municipality_bvr_first_treat.csv`
- `data/clean/tse_bvr/municipality_bvr_first_treat.parquet`
- `data/clean/tse_bvr/ibge_municipalities.csv`
- `resources/logs/tse_bvr_build_log.md`
- `docs/TSE_BVR_DATASET_NOTES.md`

## Workflow

1. Download and index TSE sources.
   Save every official TSE page or attachment used for extraction in `data/raw/tse_bvr_legal/`.
   Build an index with source URL, source type, title, issue date, treatment-reference year, annex URL, and notes.

2. Download and clean IBGE municipalities first.
   Use an official IBGE machine-readable endpoint.
   Standardize municipality names to lower-case ASCII with accents removed.
   Save the cleaned municipality table before any name matching starts.

3. Parse TSE materials conservatively.
   Extract municipality, UF, zone, source URL, source date, and any scope notes.
   Distinguish municipality-wide coverage from municipality-zone coverage.
   Preserve raw names and the normalized matching key.

4. Infer `year_first_treat` from election-use evidence, not from enrollment timing alone.
   Prefer explicit election-year language when a source states that biometrics will be used in a named election.
   When a source is a TSE summary attachment tied to a specific election cycle, document that it is the basis for the election-year inference.
   Never silently guess the election year when the official evidence is ambiguous.

5. Match to IBGE safely.
   Match within state first.
   Use fuzzy matching only to generate candidates.
   Treat exact normalized name matches as the default.
   Record all non-exact matches in the review table with notes.

6. Validate special cases.
   Identify hybrid municipalities.
   Identify zone-specific treatment.
   Check whether municipality-level sources obscure multiple zones.
   Flag locality names that may be districts or place names rather than municipalities.
   Record unresolved historical naming issues.

7. Write final outputs and logs.
   Save the clean dataset, the IBGE lookup, the source index, the matching review table, and the build log.
   Update `docs/TSE_BVR_DATASET_NOTES.md` with the evidence base, inference rules, and unresolved items.

## Matching Rules

- Normalize municipality names with:
  - lower-casing,
  - Unicode de-accenting,
  - punctuation stripping,
  - whitespace collapse,
  - removal of table asterisks and footnote markers.
- Match within the exact UF first.
- If there is one exact normalized match within UF, accept it.
- If not, generate fuzzy candidates and require manual review before treating the match as final.

## Treatment-Year Rules

- `year_first_treat` means the first election year in which biometric identification was used.
- If a legal act explicitly says the listed localities will vote with biometrics in a named election year, use that year.
- If an official TSE attachment is explicitly tied to a named election cycle, use that election year and document the inference.
- If only recadastramento timing is known but election use is not explicit, stop and look for another official TSE source.
- If no official source resolves the ambiguity, flag the row instead of forcing a year.

## Validation Checklist

- Check duplicates on `municipality_id + zone + year_first_treat + url_tse`.
- Check all states against the 27 valid UFs.
- Check municipality IDs against the IBGE table.
- Check that `municipality_name` is normalized.
- Review every fuzzy or non-exact match.
- Count rows by source year and compare them against source-level totals when available.

## Failure Modes

- SinTSE annex URLs may return access-rejected pages.
- A compiled TSE page may expose article text but not the annex body.
- Municipality-level summary files may not preserve zone identifiers.
- Some sources may aggregate localities across multiple legal acts.

## Escalation

- If SinTSE annexes are blocked, look for an official TSE attachment or official TSE news archive that reproduces the same municipality list.
- If only unofficial mirrors are reachable, do not use them as the primary source.
- If municipality-level summary files are the only accessible official evidence, record that limitation explicitly in the notes and log instead of pretending the row is backed by a direct legal annex.
