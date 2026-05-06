# Biometric Voter Registration in Brazil

This repository supports an academic political-economy paper on Brazil's biometric voter registration (BVR) rollout. The paper studies a central tradeoff in electoral administration: reforms introduced to improve electoral integrity can also change the practical costs of participation and, in turn, who remains in the electorate, who turns out, and how citizens evaluate democratic institutions.

In the current project, Brazil is treated as a particularly useful setting because BVR was rolled out gradually across municipalities and because the reform sits naturally as a second wave of electoral modernization after the earlier adoption of electronic voting. The repository therefore combines municipality-level administrative data, respondent-level LAPOP survey data, municipal covariates, reusable estimation pipelines, and a modular LaTeX paper.

## What The Repository Is For

The repository is organized around four linked empirical questions:

1. Did BVR shrink the voter registry in the short run and, if so, did the electorate recover over time?
2. Did BVR change the composition of the registered electorate, especially along education and gender dimensions?
3. Is municipal exposure to BVR associated with trust in institutions and support for democracy in LAPOP repeated cross-sections?
4. Did BVR exposure shape later beliefs about electoral integrity, secrecy, or backlash, especially among politically salient groups?

## Working Principles

- Reproducibility comes first: raw inputs, interim transforms, clean analysis files, code, manuscript outputs, and logs are separated on purpose.
- Administrative facts and attitudinal associations are treated as distinct objects; causal language should follow the design, not the other way around.
- Municipality harmonization, treatment timing, hybrid implementation, and survey matching are first-order design choices and are documented explicitly.
- The paper and the code should stay synchronized: tables, figures, notes, and manuscript claims should all be traceable to scripts in the repository.

## Start Here

Read these files first:

1. [STRUCTURE.md](STRUCTURE.md) for a detailed map of the repository.
2. [PROJECT.md](PROJECT.md) for the project brief, research framing, and priorities.
3. [AGENTS.md](AGENTS.md) for repository-specific instructions for coding and research agents.
4. [paper/main.tex](paper/main.tex) for the manuscript entry point.

## Main Components

- `data/raw/`: immutable source material from TSE, IBGE, LAPOP, and related legal or institutional documents.
- `data/interim/`: diagnostics, parsed files, harmonization reviews, and replication audits.
- `data/clean/`: analysis-ready municipality and survey datasets.
- `src/data/`: downloaders for public source files.
- `src/cleaning/`: parsers and harmonizers for municipality codes, eleitorado files, and legal treatment sources.
- `src/analysis/`: main reproducible analysis scripts for treatment timing, clean panels, PCA indices, regressions, figures, and tables.
- `.agents/skills/`: repository-local skills for DiD estimation, LAPOP harmonization, regression running, TSE treatment construction, and eleitorado harmonization.
- `resources/`: generated figures, tables, logs, and paper-ready assets.
- `paper/`: the modular LaTeX manuscript, references, front matter, and appendix.
- `docs/`: durable notes on data construction, PCA choices, trust regressions, treatment timing, and replication audits.

## Current Workflow

The repository currently supports these main workflows:

- Build and audit municipality BVR timing from TSE legal and administrative sources.
- Construct the municipality-year electorate panel and derived outcomes for registry size and composition.
- Estimate dynamic TWFE event studies and alternative staggered-adoption robustness checks.
- Harmonize LAPOP Brazil waves, construct trust and democracy indices by PCA, and run interaction regressions.
- Keep the paper's trust module aligned with the live LAPOP pipeline: the main text uses standardized first-principal-component indices for both trust in institutions and trust in democracy, reports the PCA decomposition table in the main text, and pushes explained-variance plots to the appendix assets under `resources/lapop/pca/`.
- Audit notebook-paper mismatches explicitly when a reproduced result does not match an earlier workflow.
- Compile the paper from modular section files while reading figures and tables directly from `resources/`.

## Manuscript

The LaTeX manuscript is modular. Main sections live in `paper/sections/`, the appendix lives in `paper/appendix/`, and bibliography inputs live in `paper/references/`. Figures and tables used by the paper should live under `resources/`, not inside `paper/`. The political-trust section is currently organized into two substantive subsections, `Building Trust and Democracy Indices` and `BVR Exposure and Political Attitudes`, which mirror the older project draft while keeping the paper's updated interpretation.

## Practical Note

If you are trying to understand where a dataset, table, figure, or script belongs, use [STRUCTURE.md](STRUCTURE.md) as the canonical navigation guide.
