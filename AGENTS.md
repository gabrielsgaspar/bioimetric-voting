# AGENTS.md

## Purpose

This repository supports an academic political-economy paper on biometric voter registration (BVR) in Brazil. The project studies whether the staggered rollout of BVR changed:

1. the size of the electorate,
2. the composition of registered voters,
3. trust in institutions and support for democracy, and
4. perceptions of electoral integrity, skepticism, or backlash.

Agents working in this repository should optimize for rigor, reproducibility, and clarity. Prefer conservative, well-documented changes over clever shortcuts.

---

## Project-Specific Priorities

This project combines administrative electoral data, survey data, econometric analysis, and manuscript writing. The highest priorities are:

- preserving raw-data integrity,
- documenting treatment timing and sample restrictions clearly,
- keeping municipal and survey pipelines separate until the merge step is explicit,
- avoiding causal language unless the identification assumptions are defended,
- ensuring that tables, figures, and paper claims are traceable to scripts.

The main empirical sources are expected to include:

- TSE administrative electoral data,
- LAPOP AmericasBarometer survey data,
- IBGE municipal covariates and demographic statistics,
- shapefiles, crosswalks, and municipality-code harmonization files.

---

## Core Principles

1. **Correctness over speed**
   Never trade rigor for speed. Check claims before writing them into the paper.

2. **Reproducibility is mandatory**
   Core results should be reproducible from raw data to final manuscript outputs.

3. **Small, verifiable changes**
   Work incrementally. After each meaningful step, validate joins, counts, code paths, or outputs.

4. **Be explicit about uncertainty**
   Distinguish facts from assumptions, preliminary findings, robustness checks, and conjectures.

5. **Follow repository structure**
   Reuse existing directories and naming conventions instead of creating parallel workflows.

6. **Paper-code consistency matters**
   Do not let the manuscript drift away from the implemented specification.

---

## Default Workflow

For most non-trivial tasks, do the following:

1. Read `README.md` and `docs/PROJECT.md`.
2. Inspect the relevant source files and repository structure.
3. Make a short plan before changing multiple files.
4. Implement in small steps.
5. Validate outputs.
6. Summarize what changed, how it was checked, and what remains uncertain.

Create a plan first when the task affects identification, treatment coding, merge logic, manuscript claims, or project structure.

---

## Data Rules

- Never overwrite files in `data/raw/`.
- Record provenance for each dataset in `docs/DATA_SOURCES.md`.
- Keep intermediate transforms in `data/interim/` and analysis-ready files in `data/clean/`.
- Log major sample restrictions and dropped observations.
- Verify municipality identifiers carefully across years and sources.
- Treat hybrid BVR municipalities and municipality boundary changes as first-order design issues, not cleanup details.

When merging:

- report merge keys,
- report match rates,
- inspect duplicates,
- document how municipality codes are harmonized over time.

---

## Econometrics Rules

Because treatment is staggered over municipalities, agents should:

- avoid default two-way fixed effects event-study claims without checking known staggered-adoption issues,
- document estimator choice for dynamic effects and aggregate treatment effects,
- cluster standard errors at the municipality or municipality-wave level when appropriate,
- separate descriptive results from causal interpretation,
- check pre-trends and support windows,
- make treatment timing, comparison groups, and excluded cohorts explicit in every relevant output.

If using alternative estimators or robustness checks, document why they were chosen and what identifying assumptions they rely on.

---

## Writing Rules

- Keep prose precise and readable.
- Do not overstate random assignment, exogeneity, or causal proof without support.
- When discussing mechanisms, say whether they are directly tested or only suggestive.
- Keep notation and variable names consistent across paper, code, and tables.
- If a result is preliminary, label it as preliminary.

The manuscript is modular. Add content to the appropriate file under `paper/sections/` rather than expanding `paper/main.tex`.

---

## Repository Expectations

Preferred structure:

- `data/raw/` for immutable source files,
- `data/interim/` for temporary transformed datasets,
- `data/clean/` for analysis-ready datasets,
- `src/` for reusable code,
- `tests/` for lightweight validation code,
- `resources/` for generated figures, tables, logs, and other derived assets,
- `paper/` for the manuscript,
- `docs/` for durable notes and decisions,
- `.agents/skills/` for repository-local Codex skills.

Store planning notes, audit notes, and data-source records under `docs/`, not in the repository root.

---

## Skills

Repository-local skills should live under `.agents/skills/`. At minimum, this project should eventually include skills for:

- literature review,
- TSE data ingestion,
- LAPOP data ingestion,
- municipality panel construction,
- event-study estimation,
- plotting figures,
- paper writing,
- replication audit.

A placeholder literature-review skill is included and can be filled in manually later.

---

## Definition of Done

A task is not done unless:

- the relevant files are updated,
- the change is consistent with repository structure,
- any generated artifacts are saved to the right location,
- key assumptions or caveats are documented,
- and the final summary states what was done and how it was checked.
