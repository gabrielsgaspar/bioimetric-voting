# PAPER.md

## What this paper is about in one paragraph

This project studies biometric voter registration (BVR) in Brazil as a political and administrative tradeoff. The motivating idea is simple: reforms that are introduced to make elections cleaner, safer, or harder to manipulate can also make participation more bureaucratically demanding. In Brazil, biometric registration required voters to update their records with fingerprints, photos, and signatures, and that reform was rolled out gradually across municipalities from 2008 to 2018. The paper asks whether that modernization improved the integrity of the voter registry while also changing who remained on the rolls, how citizens felt about institutions and democracy, and whether later electoral distrust became especially sharp in places that had already been exposed to biometric administration.

## The big picture idea

The paper sits at the intersection of three literatures.

First, it is about electoral technology. A lot of work on election administration focuses on voting machines, ballot design, and polling-place procedures. This paper shifts attention upstream to the registration and identification stage. The question is not only whether the ballot is cast electronically, but also who is still in the registry by the time election day arrives and what kinds of political signals the administration of registration sends.

Second, it is about administrative burden and political inclusion. Biometric registration may clean duplicate or stale registrations from the roll, which is a genuine electoral-integrity gain. But it also requires citizens to interact with the bureaucracy before they vote. If that burden is unequally distributed, then a reform that looks technocratic can also reshape political voice.

Third, it is about trust and backlash. Electoral authorities often justify technology upgrades by claiming they build confidence in the system. That may be true, but technology can also become politicized. In Brazil, this became especially salient during the Bolsonaro period, when attacks on the TSE and the broader electoral apparatus turned election administration into a partisan object.

The paper's central claim is therefore not "technology is good" or "technology is bad." It is that electoral modernization can improve registry integrity while also changing inclusion, representation, and public attitudes, and those margins need to be studied together.

## Why Brazil is a strong setting

Brazil is unusually useful for this question for several reasons.

- Elections are centrally administered by the TSE and state TREs, so election rules and implementation are institutionalized and well documented.
- Voting is compulsory for most adults, which makes administrative barriers especially meaningful.
- Brazil had already gone through an earlier modernization wave with nationwide electronic voting by 2000, so biometric registration can be studied as a second wave of modernization rather than an isolated reform.
- The rollout of BVR was staggered across municipalities. That creates variation in timing, which makes event-study and staggered-adoption designs possible.
- Brazil also has good administrative electoral data and a reasonably rich survey archive through LAPOP.

The paper uses this setting to connect two ideas that are often studied separately: the mechanical effects of electoral administration and the attitudinal consequences of state capacity, trust, and suspicion.

## The institutional setup in the paper

The manuscript's background section treats BVR as a change in how voters are authenticated and how the registry is managed.

Before biometric identification, voters typically relied on the voter registration card plus another identity document, and poll workers handled the verification step. Under biometric registration, the electoral courts collect fingerprints, a photo, and a signature in advance, and those records can then be used for identity verification at the polling place.

The current treatment-timing file in the repository treats the first verified biometric election year as the municipality's treatment year. In the clean municipality-level file, treated municipalities arrive in these waves:

- 2008: 3 municipalities
- 2010: 57 municipalities
- 2012: 239 municipalities
- 2014: 465 municipalities
- 2016: 779 municipalities
- 2018: 1,251 municipalities

That produces 2,794 ever-treated municipalities by 2018 and 2,777 never-treated municipalities in the main municipal panel.

One important complication is hybrid implementation. In 2018, the official TSE file explicitly labels some municipalities as `Biometrico`, `Hibrido`, or `Sem biometria`. The clean panel carries a `hybrid` indicator for those 2018 hybrid municipalities, and the appendix reruns the main event studies excluding them. This matters because partial or zone-specific implementation is not the same thing as a full municipal transition.

## How the paper is structured

The manuscript entry point currently pulls in the abstract plus six substantive section files:

- `paper/frontmatter/abstract.tex`
- `paper/sections/introduction.tex`
- `paper/sections/institutional_background.tex`
- `paper/sections/bvr_and_electorate_size.tex`
- `paper/sections/bvr_and_political_trust.tex`
- `paper/sections/backlash_and_electoral_integrity.tex`
- `paper/sections/conclusion.tex`

Substantively, the paper has three empirical blocks.

### 1. Administrative effects on the voter registry

This is the strongest and most causally structured part of the paper. It asks whether BVR changed:

- the size of the registered electorate
- the education composition of the electorate
- in supporting outputs, the gender composition and related margins

### 2. Survey evidence on trust and democratic attitudes

This section asks whether living in a municipality that had already adopted BVR is associated with:

- higher trust in institutions
- higher support for democracy
- heterogeneous effects by gender, race, marital status, and education

This is more suggestive than the administrative analysis because it relies on repeated cross-sections rather than a panel of individuals.

### 3. Backlash and electoral-integrity beliefs

This section asks whether Bolsonaro-aligned respondents are especially skeptical about vote counting or ballot secrecy in municipalities exposed to BVR. It is designed as a backlash test, not as the main headline result.

## The data architecture behind the paper

The project is built around separate administrative and survey pipelines that only meet at explicit merge steps.

### Administrative side

The main administrative inputs are:

- TSE electorate files by year, used to build a municipality-election panel
- TSE legal and administrative evidence on biometric rollout timing
- IBGE municipality crosswalk and municipal covariates

The main clean administrative files are:

- `data/clean/tse_bvr/municipality_bvr_first_treat.parquet`
- `data/clean/tse_eleitorado/eleitorado_education_gender_2000_2018.parquet`
- `data/clean/tse/tse_clean_panel_2000_2018.parquet`

The main municipal panel contains `55,661` municipality-election observations across `5,571` municipalities.

### Survey side

The main survey inputs are LAPOP Brazil waves and municipal covariates. There are really two related LAPOP tracks in the repo.

The first track is the newer comparable core:

- `data/clean/lapop/lapop_brazil_core_2008_2019.parquet`
- `data/clean/lapop/lapop_brazil_with_pca_indices.parquet`
- `data/clean/lapop/lapop_brazil_with_pca_indices_regression_ready.parquet`

This comparable core contains `10,009` respondents from survey years `2008, 2010, 2012, 2014, 2017, 2019`.

The second track is a benchmark-notebook reconstruction used to line up the trust section with the older draft workflow:

- `data/clean/lapop/lapop_brazil_with_pca_indices_regression_ready_corrected.parquet`

That benchmark-style trust workflow corresponds to a linked sample of `11,008` respondents in `235` municipalities, with a main regression sample of `10,632` once common controls and non-missing outcomes are imposed.

There is also now a separate 2021 backlash file:

- `data/clean/lapop/lapop_brazil_backlash_2021_regression_ready.parquet`

This separation matters because the trust section and the backlash section do not rely on exactly the same survey universe.

## The main regressions

## Administrative event studies

The core administrative specification is a dynamic two-way fixed effects event study:

```text
y_mt = sum_k beta_k * 1{t - g_m = k} + alpha_m + lambda_t + error_mt
```

where:

- `y_mt` is a municipality-level outcome
- `g_m` is the first biometric election year
- `alpha_m` are municipality fixed effects
- `lambda_t` are election-year fixed effects

The event-time window used in the paper is eight years before and after adoption, with event time `-2` omitted as the reference period. Untreated municipalities stay in the sample as controls. The outcomes emphasized in the paper are:

- `log_num_voters`
- `pct_voters_low_ed`
- `pct_voters_high_ed`

Standard errors are clustered by municipality and election year.

The paper is careful, at least in principle, about the limitations of TWFE under staggered adoption. The main text uses TWFE as the baseline visual summary, while the appendix compares it to alternative estimators including Callaway-Sant'Anna and Borusyak-Jaravel-Spiess. That is an important design choice: the project is not pretending TWFE is the only or obviously best estimator in a staggered setting.

## LAPOP trust and democracy regressions

The trust section uses interaction regressions of the form:

```text
y_imt = beta * BVR_mt + lambda * G_i + theta * (BVR_mt x G_i)
        + controls + municipality FE + survey-year FE + error_imt
```

where:

- `y_imt` is either the institutional-trust index or the democracy index
- `BVR_mt` indicates whether the municipality had adopted BVR by the survey year
- `G_i` is one respondent characteristic at a time

The four interaction variables are:

- `female`
- `white`
- `married`
- `low_ed`

The control set is:

- `low_ed`
- `female`
- `white`
- `married`
- `working`
- `age`
- `log_gdp_pc`
- `log_total_pop`

The outcomes are standardized PCA indices. The trust index is built from eight institutional-confidence items. The democracy index is built from three broader democracy items. Municipality fixed effects and survey-year fixed effects are included, and the benchmark notebook replication uses two-way clustering on municipality and year.

## Backlash regressions

The backlash section uses a weighted cross-sectional linear probability model on the Brazil 2021 LAPOP wave:

```text
y_im = beta1 * BVR_m + beta2 * BolsonaroApproval_i
       + beta3 * (BVR_m x BolsonaroApproval_i)
       + controls + error_im
```

There are two dependent variables:

- `count_fair_always`: respondent says votes are counted correctly "always"
- `ballot_secret_never`: respondent says politicians can identify how people voted "never"

The individual-level alignment proxy is not reported presidential vote choice. It is approval of the Bolsonaro government, because the reproducible public 2021 file contains the integrity battery but not vote recall.

Controls in this smaller module are:

- `low_ed`
- `female`
- `white`
- `age`
- `urban`
- `log_total_pop`

All specifications use LAPOP survey weights and cluster standard errors by municipality.

The current paper table reports `698` observations for the count-fair regressions and `715` for the ballot-secrecy regressions.

## What the paper currently finds

## 1. BVR shrinks the registry on impact

This is the cleanest and clearest result in the project.

From `resources/tables/twfe_dynamic_main_table.tex`, the estimated impact on the log number of voters at event time `0` is `-0.115` with standard error `0.006`. Interpreted roughly in percent terms, that is an immediate contraction of about 11 percent relative to two years before adoption.

The dynamic path matters too. The registry then partially recovers:

- event time `2`: `-0.070`
- event time `4`: `-0.044`
- event time `6`: `-0.002`
- event time `8`: `0.027`

The basic story is that biometric recadastramento causes a sharp short-run contraction and then a gradual recovery. That pattern is consistent with a mix of registry cleaning and delayed re-entry by voters who did not complete the new registration process right away.

## 2. BVR changes who remains on the rolls

The education-composition result is just as important as the registry-size result.

At event time `0`, the low-education share falls by `0.089` and the high-education share rises by `0.089`, both with very small standard errors. These effects remain visible for years after adoption:

- low-education share at `8`: `-0.054`
- high-education share at `8`: `0.054`

This strongly suggests that BVR is not only cleaning the registry mechanically. It is reweighting the electorate toward more educated voters, at least in the short and medium run.

The paper is appropriately cautious about mechanism. Some of this could be:

- real exclusion or slower re-entry among lower-education voters
- differential compliance costs
- improved measurement of education in the registry

But the magnitude and persistence make it hard to read the pattern as a trivial artifact.

## 3. Institutional trust rises mainly among lower-education respondents

The trust section is more nuanced.

The current main table, `resources/tables/lapop_trust_interactions_main_table.tex`, shows that heterogeneity in institutional trust is mostly weak except for education. The key coefficient is the low-education interaction in the trust-in-institutions regression:

- interaction estimate: `0.123`
- standard error: `0.031`
- `p = 0.007`

The base treatment effect for the higher-education reference group is basically zero at `-0.008`, while the combined effect for lower-education respondents is `0.115`.

The other trust interactions are small and imprecise:

- female: `0.082`
- white: `-0.039`
- married: `-0.047`

For the democracy index, the pattern is weaker. The low-education interaction is positive (`0.054`) but not statistically persuasive, and the other interactions are again small and noisy.

The paper's current interpretation is appropriately restrained: the attitudinal evidence is suggestive, and the strongest survey-side result is a positive institutional-trust association among lower-education respondents in treated municipalities.

## 4. The backlash evidence is limited

The backlash section does find skepticism among Bolsonaro-aligned respondents, but it does not find a clear BVR-specific backlash channel.

From `resources/tables/lapop_backlash_2021_main_table.tex`:

- in untreated municipalities, Bolsonaro approval is associated with a large negative gap in saying votes are counted correctly
- the interaction `BVR x Bolsonaro approval` for the count-fair outcome is `+0.198` with standard error `0.107` and `p = 0.063`
- the interaction for ballot secrecy is `-0.112` with standard error `0.105` and `p = 0.283`

That means Bolsonaro-aligned respondents are indeed more skeptical about vote counting, but the gap is not larger in BVR municipalities. If anything, it is somewhat smaller there. So the current evidence does not support the story that prior exposure to biometric administration made Bolsonaro-aligned respondents especially distrustful of count integrity.

## The setup of the trust indices

The PCA table in `resources/tables/lapop_pca_decomposition_main.tex` shows why the paper treats the two attitudinal outcomes differently.

For institutional trust:

- PC1 explains `49.1%` of the variance
- PC2 explains only `10.9%`

This is a relatively clean one-dimensional index.

For democracy:

- PC1 explains `41.0%`
- PC2 explains `30.5%`

This is much less one-dimensional. That is one reason the democracy findings are interpreted more cautiously than the trust findings. The trust index is a more coherent latent variable than the democracy index.

## What is strongest in the paper

The strongest parts of the paper are:

- the treatment-timing build from TSE material
- the clean municipality-election panel
- the dynamic evidence that BVR shrinks the registry on impact
- the equally strong evidence that the electorate shifts away from lower-education registrants

These are the parts where the identification is clearest, the outcomes are administrative rather than self-reported, and the estimates line up with a coherent reform narrative.

## What is more suggestive

The more suggestive parts are:

- the LAPOP trust results
- the backlash section

These are still valuable, but the inferential limits are real. The survey analyses assign treatment at the municipality level, not the individual level. They use repeated cross-sections, not a respondent panel. And because the administrative results already show compositional change in the electorate, post-treatment attitudinal differences can reflect both changing beliefs and changing sample composition.

## The main struggles and unresolved issues

This repository already documents several genuine empirical struggles. They are not cosmetic; they materially affect how the paper should be read.

## 1. Treatment timing is hard

The BVR rollout is not given in one clean, perfectly municipal source across the whole period. The project had to combine:

- direct legal evidence for early years
- official attachments
- election-year electorate files
- calibration rules for 2014 and 2016
- explicit status labels for 2018

That means treatment timing is carefully built, but it is not a frictionless one-source dataset. The 2014 cutoff is calibrated to the official benchmark, and hybrid treatment in 2016 remains partially unresolved.

## 2. Hybrid municipalities are a first-order design issue

The project does not ignore hybrid rollout. It documents it and reruns the event studies excluding municipalities flagged as hybrid in 2018. That is exactly the right instinct, but it also means there is still some unavoidable uncertainty about partial treatment histories outside the clean full-biometric timing file.

## 3. Municipality harmonization is nontrivial

The project repeatedly has to harmonize between TSE identifiers, IBGE identifiers, and municipality names appearing in LAPOP labels. Manual overrides were needed for some municipality-name differences. This is normal in Brazil work, but it is an actual empirical task, not just housekeeping.

## 4. The LAPOP workflow split into two competing universes

One of the biggest paper-construction struggles was that the newer clean comparable LAPOP core did not reproduce the older benchmark notebook results. The reason was not mainly municipality matching. It was that the benchmark notebook:

- rebuilt from older raw waves
- included 2006
- used a different effective sample
- standardized the PCA outcomes on a different universe

That discrepancy has now been audited and a corrected benchmark-style regression-ready file exists. Still, it means the trust section depends on a more delicate reproduction path than the administrative section.

## 5. The backlash design had to be redesigned around public data constraints

The draft backlash section was framed as a 2023 LAPOP exercise linked to the 2022 presidential election. That design was not cleanly reproducible with the public-data access available in this environment. The official Brazil 2023 study page existed, but the public download route returned an HTTP 500 error here, and the public 2021 file had the integrity questions without vote recall. So the current section uses 2021 plus Bolsonaro approval as a proxy for alignment.

That is a sensible workaround, but it is still a workaround. The paper should not pretend it is a direct "voted for Bolsonaro in 2022" test.

## 6. The conclusion is still provisional

`paper/sections/conclusion.tex` explicitly says it is scaffold text. That means the empirical core is much more developed than the closing synthesis. Anyone taking over the paper should expect to rewrite the conclusion once the argument is finalized.

## How to think about the paper's contribution right now

The cleanest current contribution is this:

Brazil's biometric voter registration program appears to have improved or at least tightened registry administration in a way that sharply reduced the number of registered voters at adoption, and it disproportionately reduced the share of lower-education voters on the rolls. Survey evidence then suggests that institutional trust may have increased among lower-education respondents in treated places, but broader democratic attitudes moved less clearly, and later Bolsonaro-era skepticism does not seem to have been uniquely intensified by BVR exposure.

That is a meaningful contribution because it shows that electoral modernization has distributive and attitudinal consequences, not only administrative ones.

## What would still strengthen the paper

If the project continues, the biggest upgrades would be:

- fully locking down treatment timing for the ambiguous/hybrid years
- continuing to document treatment coding with publication-grade provenance
- deciding exactly which LAPOP workflow is canonical for the trust section
- obtaining a cleaner public or documented route for the later-wave integrity/backlash design
- rewriting the conclusion so the paper ends with evidence-backed rather than scaffold prose

## Key files if you want to understand or extend the paper

Start with these:

- `paper/main.tex`
- `paper/sections/institutional_background.tex`
- `paper/sections/bvr_and_electorate_size.tex`
- `paper/sections/bvr_and_political_trust.tex`
- `paper/sections/backlash_and_electoral_integrity.tex`

Then move to these data and notes files:

- `data/clean/tse/tse_clean_panel_2000_2018.parquet`
- `data/clean/tse_bvr/municipality_bvr_first_treat.parquet`
- `data/clean/lapop/lapop_brazil_with_pca_indices_regression_ready_corrected.parquet`
- `docs/TSE_BVR_DATASET_NOTES.md`
- `docs/TSE_CLEAN_PANEL_NOTES.md`
- `docs/LAPOP_PCA_INDICES_NOTES.md`
- `docs/LAPOP_TRUST_REPLICATION_DEBUG_NOTES.md`
- `docs/LAPOP_BACKLASH_REGRESSIONS_NOTES.md`

And if you want the paper-ready outputs:

- `resources/tables/twfe_dynamic_main_table.tex`
- `resources/tables/lapop_pca_decomposition_main.tex`
- `resources/tables/lapop_trust_interactions_main_table.tex`
- `resources/tables/lapop_backlash_2021_main_table.tex`
- `resources/images/regressions/twfe_dynamic/log_num_voters/event_study_plot.pdf`
- `resources/lapop/figures/trust_interactions_barplot.pdf`
- `resources/lapop/figures/democracy_interactions_barplot.pdf`

## Bottom line

The paper argues that biometric voter registration should be understood as both a registry-cleaning reform and a political inclusion shock. In Brazil, the reform appears to have contracted the electorate at adoption, shifted the electorate away from lower-education voters, and been associated with more positive institutional trust among lower-education respondents who remained linked to treated municipalities. The later backlash evidence is more limited and does not show that BVR exposure clearly intensified Bolsonaro-era skepticism about electoral integrity. The project is already substantial and empirically interesting, but it still carries real design caveats that should remain visible in any final draft.
