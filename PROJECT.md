# Project Brief

## Title

**In Technology We Trust? Biometric Voter Registration in Brazil, Electoral Access, and Democratic Attitudes**

## Core Framing

This project studies the tradeoff between electoral integrity and electoral access. Brazil's biometric voter registration (BVR) program was introduced to improve voter identification, reduce duplicate or fraudulent registration, and modernize election administration. But reforms designed to secure elections can also change the practical burdens citizens face when they register, remain on the rolls, and show up to vote. The paper asks whether a security-oriented reform can also reshape political inclusion, participation, and perceptions of democracy.

The project treats BVR as Brazil's second wave of electoral modernization. The first wave was electronic voting at ballot casting. This paper focuses on a later reform at the registration and verification stage, where the state changed how voters proved who they were and how the registry itself was maintained.

## Main Questions

1. Did BVR reduce the size of the municipal electorate in the short run, and how persistent were those effects?
2. Did BVR change the composition of the voter registry, especially by education and gender?
3. Are respondents living in BVR-exposed municipalities more trusting of institutions or more supportive of democracy?
4. Are any trust or democracy associations concentrated among women, white respondents, married respondents, or low-education respondents?
5. Did BVR later feed skepticism or backlash about vote counting, vote secrecy, or electoral integrity?

## Empirical Structure

The repository is built around three linked empirical blocks.

### 1. Administrative electorate analysis

Using TSE municipality-year data, the project estimates how BVR changed:

- the number of registered voters,
- the composition of the electorate by education,
- the composition of the electorate by gender,
- and related dynamic patterns before and after treatment.

This is the strongest causal part of the paper and relies on staggered municipal adoption, event-study specifications, and robustness checks with alternative DiD estimators.

### 2. Political trust and democracy

Using harmonized LAPOP Brazil repeated cross-sections, the project studies whether municipal exposure to BVR is associated with:

- trust in institutions,
- support for democracy,
- and heterogeneity across key respondent characteristics.

These analyses are more associational than the administrative panel results and require careful attention to municipality matching, survey-wave timing, and index construction.

### 3. Backlash and electoral integrity

Using later-wave LAPOP evidence, the paper examines whether exposure to BVR is associated with beliefs about:

- whether votes are counted fairly,
- whether the ballot is secret,
- and whether skepticism is stronger among politically relevant subgroups such as Bolsonaro voters.

This section is explicitly more descriptive and should not be written as if it has the same identification strength as the administrative panel.

## Main Data Sources

### TSE administrative data

- municipal treatment timing and rollout information,
- electorate counts,
- education and gender composition of registered voters,
- related election-administration quantities used to build municipality panels.

### LAPOP AmericasBarometer

- harmonized Brazil waves for trust and democracy analyses,
- selected later-wave items for backlash and electoral integrity questions,
- respondent demographics and municipality linkage information.

### IBGE municipal covariates

- population,
- GDP and GDP per capita,
- municipality identifiers and crosswalks used for harmonization and survey merges.

## Design Principles

- Preserve raw inputs and document provenance.
- Keep `raw`, `interim`, and `clean` datasets distinct.
- Treat municipality harmonization and hybrid implementation as substantive design issues.
- Separate administrative facts, attitudinal associations, and stronger causal claims.
- Keep the manuscript synchronized with the code that generates its tables and figures.
- Prefer explicit audits when replicated results differ from notebook or draft versions.

## Current Repository Priorities

1. Keep the treatment-timing file, clean municipality panel, and survey-regression files reproducible from source data.
2. Maintain a clear line between the administrative event-study module and the LAPOP attitudinal module.
3. Preserve notebook-replication paths when they differ from the paper-consistent baseline, and document the difference rather than hiding it.
4. Route all paper assets through `resources/` so the manuscript reads from generated outputs directly.
5. Keep repository documentation current enough that a new collaborator can understand where everything lives and how the paper is assembled.

## Key Files

- [STRUCTURE.md](STRUCTURE.md): detailed repository map.
- [README.md](README.md): quick orientation.
- [paper/main.tex](paper/main.tex): manuscript entry point.
- [docs/TSE_BVR_DATASET_NOTES.md](docs/TSE_BVR_DATASET_NOTES.md): treatment-timing notes.
- [docs/LAPOP_BRAZIL_HARMONIZATION_NOTES.md](docs/LAPOP_BRAZIL_HARMONIZATION_NOTES.md): LAPOP harmonization notes.
- [docs/LAPOP_PCA_INDICES_NOTES.md](docs/LAPOP_PCA_INDICES_NOTES.md): trust/democracy PCA notes.
- [docs/LAPOP_TRUST_REPLICATION_DEBUG_NOTES.md](docs/LAPOP_TRUST_REPLICATION_DEBUG_NOTES.md): notebook-replication audit.
