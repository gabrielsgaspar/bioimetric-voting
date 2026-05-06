---
name: lapop-brazil-harmonizer
description: Download, harmonize, and document official LAPOP Brazil AmericasBarometer data. Use when building the 2008-2019 Brazil comparable core, inspecting cross-wave variable consistency, or extracting a specific official Brazil wave such as 2021 with selected questions.
---

# LAPOP Brazil Harmonizer

## Purpose

This skill builds a reusable, documented harmonization pipeline for official LAPOP Brazil survey data.

It supports two main workflows:

1. build the comparable Brazil core for `2008, 2010, 2012, 2014, 2017, 2019`
2. extract a specific official Brazil wave, such as `2021`, with user-specified questions

## Important Scope Rule

- Brazil has official public AmericasBarometer waves in `2008, 2010, 2012, 2014, 2017, 2019, 2021`.
- There is no official public Brazil `2020` wave in the LAPOP catalog.
- Do not relabel `2019` as `2020`.
- The harmonized core is therefore `2008-2019` using the actual LAPOP survey years `2008, 2010, 2012, 2014, 2017, 2019`.

## What The Skill Produces

Core build outputs:

- `data/interim/lapop/source_inventory.csv`
- `data/interim/lapop/variable_crosswalk.csv`
- `data/interim/lapop/wave_variable_availability.csv`
- `data/clean/lapop/lapop_brazil_core_2008_2019.csv`
- `data/clean/lapop/lapop_brazil_core_2008_2019.parquet`
- `resources/logs/lapop_brazil_build_log.md`
- `docs/LAPOP_BRAZIL_HARMONIZATION_NOTES.md`

Optional requested-year extracts:

- a user-specified CSV/Parquet file for an official requested Brazil wave
- a graceful unavailable-year note if the requested wave does not exist

## Core Comparable Variables

The preferred trust block is:

- `trust_inst_respect` from `b2`
- `trust_rights_protected` from `b3`
- `trust_proud_system` from `b4`
- `trust_support_system` from `b6`
- `trust_parties` from `b21`
- `trust_president` from `b21a`
- `trust_municipal_gov` from `b32`
- `trust_elections` from `b47` in `2008/2010` and `b47a` from `2012` onward

The preferred democracy block is:

- `democracy_best_form` from `ing4`
- `democracy_satisfaction` from `pn4`
- `democracy_voice_matters` from `eff1`

`democracy_understands_politics` from `eff2` is retained when available, but it is not the preferred 3-item democracy index unless explicitly requested.

## How Variable Renaming Works

- Variables are only promoted into the comparable core after cross-wave presence is verified in the official wave files.
- Raw wave aliases are mapped into canonical names through `data/interim/lapop/variable_crosswalk.csv`.
- Raw and normalized location fields are both preserved when feasible.
- Demographic recodes are conservative and documented in `docs/LAPOP_BRAZIL_HARMONIZATION_NOTES.md`.

## Commands

Build the core:

```bash
python .agents/skills/lapop-brazil-harmonizer/scripts/run_lapop_harmonizer.py \
  .agents/skills/lapop-brazil-harmonizer/examples/config_core_2008_2019.yml
```

Extract a specific official year:

```bash
python .agents/skills/lapop-brazil-harmonizer/scripts/run_lapop_harmonizer.py \
  .agents/skills/lapop-brazil-harmonizer/examples/config_specific_year_2021.yml
```

Extract selected questions:

```bash
python .agents/skills/lapop-brazil-harmonizer/scripts/run_lapop_harmonizer.py \
  .agents/skills/lapop-brazil-harmonizer/examples/config_specific_questions.yml
```

## Workflow

1. Discover official LAPOP/Vanderbilt Brazil source pages and download links.
2. Download the requested Brazil wave files to `data/raw/lapop/{wave}/`.
3. Inspect official wave schemas.
4. Build a documented canonical crosswalk.
5. Harmonize verified cross-wave variables into project-friendly names.
6. Validate wave coverage, variable consistency, name normalization, and trust-item harmonization.
7. Save clean outputs and a build log.

## Failure Modes

- Official public access can expose only a click-through terms page before the direct data file link.
- Some location fields are numeric with value labels rather than raw text strings.
- Some notebook aliases are not valid cross-wave harmonization rules and must be rejected after file inspection.
- `2020` and future years like `2024` may be requested even when they do not exist; the skill should fail gracefully and report nearby official Brazil waves.

## Practical Guidance

- Use the core build for trust/democracy analysis tied to municipal BVR exposure.
- Use requested-year extraction for later waves like `2021` that are useful for side analyses but not part of the `2008-2019` comparable core.
- Keep `survey_year` equal to the actual LAPOP field year. Never remap years silently.
- Do not promote variables into the comparable core unless the official wave files confirm the mapping.
