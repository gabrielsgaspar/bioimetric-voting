# BJS Ref-0 Downstream Null and Non-Robust Findings

Date: 2026-05-19

This note records what did not yield a reliable downstream result in the BJS ref-0 nonhybrid screen. It complements `docs/BJS_REF0_DOWNSTREAM_FINDINGS.md` and uses the same generated artifacts:

- Master ranking: `resources/tables/downstream_bjs_ref0_nonhybrid/master_bjs_ref0_nonhybrid_ranking.csv`
- Augmented diagnostics: `resources/tables/downstream_bjs_ref0_nonhybrid/bjs_ref0_report_augmented_diagnostics.csv`
- Event-study outputs: `resources/did/downstream_bjs_ref0_nonhybrid/`
- Combined plots: `resources/figures/downstream_bjs_ref0_nonhybrid/`

The screen estimated 298 outcomes. All produced BJS event-study paths, but 236 failed the pretrend screen. Only 42 passed and 20 were near. The main conclusion of this null-results note is that the downstream evidence is selective. Several apparent post-BVR movements are large, but many of those large movements are already visible before treatment or have too little clean support to interpret causally.

## Definition of a Non-Result

I classify an outcome as a non-result for one of three reasons.

1. The outcome fails the pretrend screen. These estimates may still be descriptively interesting, but they do not provide credible event-study evidence under the current design.
2. The outcome passes or nearly passes pretrends but has a very small normalized post-BVR mean, weak post-period persistence, or no post-period precision.
3. The outcome belongs to a family where one isolated estimate survives but the broader family does not move coherently.

This distinction matters. A failed-pretrend estimate is not evidence of no effect. It is evidence that the current design cannot distinguish a BVR effect from pre-existing differential trends. A pass-pretrend estimate with little post movement is closer to a true null result.

## Summary of Failed Pretrends

| Category | Failed outcomes | Main implication |
|---|---:|---|
| Birth and health | 70 | No broad birth-health or health-system response can be claimed. |
| Education | 115 | Many education outcomes are not interpretable despite a subset of cleaner school-flow and achievement results. |
| Adult education / EJA | 21 | EJA enrollment, EJA teachers, and most EJA spending ratios fail pretrends. |
| SICONFI log per capita | 7 | Education, health, and transport spending levels do not pass cleanly in the dedicated SICONFI screen. |
| SICONFI spending shares | 10 | There is no clean budget-share reallocation result. |
| School access / transport | 13 | School transport and access channels are not supported under this design. |
| Total | 236 | Most downstream outcomes are exploratory only. |

## School Access and Transport

The school-access and transport outcomes are the clearest non-result. Thirteen of fourteen outcomes fail pretrends. The apparent post-BVR changes in public school transport, municipal-responsibility transport, and bus/van transport are descriptively large, but the pre-period trends are very strong. For example, public-school students using public transport have a post mean of 0.0198 in 0-1 units, but the maximum absolute pretrend t-statistic is 6.63 and all eight pre-period estimates are individually significant. Public-school students using municipal-responsibility transport show a post mean of 0.0213, but the maximum absolute pretrend t-statistic is 12.98 and all eight pre-period estimates are significant.

The only near-clean school-access outcome is the municipal-school share with state-responsibility transport. Its post mean is 0.0005 in 0-1 units, which is about 0.05 percentage points. The pretrend label is `near`, not `pass`, and the magnitude is tiny. This is not enough to support a school-transport mechanism.

Implication: the downstream story should not say that BVR clearly improved school access through transport provision. Transport may still be relevant descriptively, but the BJS evidence says treated municipalities were already on different transport trajectories before strict BVR.

## Adult Education and EJA

Most adult education and EJA outcomes do not survive the BJS pretrend screen. EJA enrollment, EJA teacher counts, EJA teacher shares, EJA enrollment shares, EJA spending per capita, EJA spending shares, and the EJA-to-child spending ratio mostly fail. Some of these estimates have large post means, but they also have large and systematic pre-period differences.

Examples:

| Outcome | Post mean | Max pretrend t | Pre p<0.05 count | Interpretation |
|---|---:|---:|---:|---|
| Public EJA enrollment per 1,000 residents | -1.444 | 10.510 | 8 | Strong pre-trends; not interpretable. |
| Municipal EJA enrollment per 1,000 residents | 1.071 | 2.692 | 3 | Fails pretrends. |
| Public EJA teacher share | 1.114 | 9.356 | 8 | Fails pretrends. |
| EJA share of education spending | 0.295 | 2.507 | 3 | Fails pretrends. |
| EJA spending relative to child/basic spending | 0.414 | 2.093 | 2 | Fails pretrends. |

The BJS screen therefore does not provide clean evidence that BVR reduced EJA provision or shifted resources away from adult education in levels. The positive child/basic education spending outcomes remain useful, but they should not be paired with a strong BJS claim that adult education fell.

Implication: a political-representation story can say that child/basic education appears to receive more attention, but it should not claim that BJS directly identifies an adult-to-child education reallocation.

## SICONFI Budget Shares

The SICONFI spending-share outcomes do not yield a clean result. None of the 16 spending-share outcomes pass the pretrend screen. Six are near, mostly in the two-year-cycle specifications, but their magnitudes are small:

| Outcome | Pretrend | Post mean | Unit | Interpretation |
|---|---:|---:|---|---|
| Annual urbanism share of total revenue | Near | -0.0069 | 0-1 share | Near only, negative sign. |
| Cycle education share of total spending | Near | 0.0028 | 0-1 share | Small positive movement. |
| Cycle urbanism share of total revenue | Near | -0.0021 | 0-1 share | Small negative movement. |
| Cycle infrastructure share of total revenue | Near | 0.0016 | 0-1 share | Small positive movement. |
| Cycle infrastructure share of total spending | Near | 0.0015 | 0-1 share | Small positive movement. |

The share results constrain the fiscal mechanism. The log per-capita results show some evidence of higher infrastructure and urbanism spending levels, but the share results do not show clean reallocation of the municipal budget. This is consistent with either higher total resources, scale expansion, or noisy denominators rather than a clear shift in budget priorities.

Implication: write the fiscal mechanism as a level-spending or capacity story, not as a proven budget-share story.

## Dedicated SICONFI Log Spending

Only three of ten dedicated SICONFI log per-capita spending outcomes are pass or near: annual infrastructure, cycle infrastructure, and cycle urbanism. The rest fail:

| Outcome | Post mean | Max pretrend t | Pre p<0.05 count | Interpretation |
|---|---:|---:|---:|---|
| Annual education log per capita | 0.004 | 4.402 | 5 | No clean dedicated education spending result. |
| Cycle education log per capita | 0.037 | 3.803 | 3 | Fails pretrends. |
| Annual health log per capita | -0.035 | 3.668 | 5 | Fails pretrends. |
| Cycle health log per capita | -0.006 | 4.327 | 4 | Fails pretrends. |
| Annual transport log per capita | 0.102 | 2.854 | 3 | Fails pretrends. |
| Cycle transport log per capita | 0.129 | 3.231 | 1 | Fails pretrends. |
| Annual urbanism log per capita | 0.013 | 2.303 | 2 | Fails pretrends. |

The fact that the education screen contains a pass-pretrend education spending per capita outcome, while the dedicated log education spending screen fails, means the education-spending result should be treated carefully. Differences in transformations, samples, denominators, or panel construction may matter.

Implication: infrastructure and urbanism are the cleaner fiscal candidates. Education spending is suggestive but needs harmonized follow-up.

## Birthweight, Birth Health, and Maternal Outcomes

The SINASC and health results do not support a broad birth-health improvement story. Many birth outcomes fail pretrends, including mean birthweight for low-education mothers and several preterm, prenatal, Apgar, and hospital birth outcomes. Some pass or nearly pass, but the family is not coherent.

Well-behaved but substantively small or weak post-period outcomes include:

| Outcome | Pretrend | Post mean | Interpretation |
|---|---:|---:|---|
| Dedicated low-birthweight share, low-education proxy | Pass | -0.0022 | Small decline in 0-1 units; not a broad birthweight pattern. |
| Low-education very-low-birthweight share | Pass | -0.112 pp | Clean pretrend but weak post-period precision. |
| Low-education adequate prenatal visits | Pass | 0.356 pp | Clean pretrend but weak persistence. |
| Hepatitis B newborn coverage | Pass | 0.044 pp | Clean pretrend but negligible post movement. |
| IEPS doctors per 1,000 | Pass | -0.025 | Clean pretrend, small and not a service expansion story. |

The teen-mother share is a near-clean positive signal, but it should not be generalized to all maternal or birth outcomes. It is better treated as a specific compositional result requiring targeted follow-up.

Implication: the BJS screen does not show that BVR broadly improved maternal health, birth outcomes, or primary care.

## General Health Outcomes

The health outcomes are mixed and do not form a coherent mechanism. Some IEPS outcomes pass pretrends, but signs are inconsistent. CSAP mortality falls, avoidable mortality rises, SUS beds fall, ICU beds rise, and doctors per 1,000 fall slightly. Hospitalizations, all-cause mortality, primary-care coverage, and several prenatal measures fail pretrends.

This pattern rules out a simple story in which BVR improved municipal health administration across the board. It also rules out the opposite simple story in which BVR broadly worsened health-service outcomes. The health block is best described as inconclusive, with selected outcomes worth checking only after stronger mechanism-specific predictions are developed.

Implication: health should not be the main downstream mechanism in the current paper draft.

## Education Outcomes That Do Not Survive

Education is the largest outcome family, and it contains both promising and non-robust results. The BJS screen estimates 146 education outcomes. Only 31 are pass or near; 115 fail. Many SAEB/IDEB achievement levels and INEP flow variables have large apparent post means but also large pre-period deviations.

Examples of large failed education estimates:

| Outcome | Post mean | Max pretrend t | Pre p<0.05 count | Interpretation |
|---|---:|---:|---:|---|
| Municipal grade-5 math mid-level share | 4.731 pp | 6.686 | 3 | Fails pretrends. |
| Public grade-5 math mid-level share | 4.673 pp | 7.259 | 3 | Fails pretrends. |
| Municipal grade-5 Portuguese mid-level share | 3.975 pp | 7.540 | 3 | Fails pretrends. |
| Public grade-5 math low-level share | -3.849 pp | 4.841 | 2 | Fails pretrends. |
| SICONFI investment spending per capita | -17.829 | 4.920 | 4 | Fails pretrends. |

The cleaner education result is therefore not "achievement improves everywhere." It is narrower: selected final-years approval, abandonment, repetition/reprobation, and a few assessment outcomes move in a favorable direction. The broader achievement distribution remains too noisy or pre-trended to interpret.

Implication: education mechanisms should focus on school progression and selected final-years outcomes before making achievement claims.

## Well-Identified Nulls

Several outcomes have acceptable pretrends but little post-BVR movement. These are useful because they rule out overly broad interpretations.

| Domain | Outcome | Pretrend | Post mean | Interpretation |
|---|---|---:|---:|---|
| Birth health | Dedicated low-birthweight share, low education | Pass | -0.0022 | No strong low-birthweight response in the dedicated share outcome. |
| Immunization | Hepatitis B newborn coverage | Pass | 0.0435 pp | No meaningful movement. |
| Health workforce | IEPS doctors per 1,000 | Pass | -0.0250 | No evidence of expanded physician supply. |
| Education inputs | Municipal secondary hours per day | Pass | 0.0336 | No clear instructional-time response. |
| Education inputs | Municipal secondary students per class | Pass | -0.0649 | No meaningful class-size response. |
| School access | Municipal-school state transport share | Near | 0.0005 | Tiny effect; not an access mechanism. |
| SICONFI shares | Cycle infrastructure share of total spending | Near | 0.0015 | Very small share movement. |
| SICONFI shares | Cycle education share of total spending | Near | 0.0028 | Very small share movement. |

These nulls help discipline the mechanism. The downstream response, if real, does not look like a broad increase in health inputs, a large improvement in school access, or a visible increase in all education inputs. It is narrower and more consistent with selected spending levels, school progression, and infrastructure/urbanism.

## Implications for the Mechanism Story

The null results are not a side issue. They shape the mechanism. A broad "state capacity improved everywhere" story is too strong because health, access, transport, and many education inputs do not move cleanly. A pure "municipalities reallocated the budget" story is also too strong because spending shares do not pass. A pure "adult education lost resources" story is not supported by BJS because EJA outcomes mostly fail pretrends.

The most defensible mechanism is narrower: strict BVR may have changed political representation and local administrative information in ways that encouraged selected child-oriented and visible municipal investments. The evidence is consistent with more attention to regular schooling and complementary infrastructure, but it does not identify a general service-delivery upgrade.

## Recommended Non-Results to Mention in the Paper or Appendix

1. School transport and access outcomes should be reported as failing pretrend checks. This prevents overclaiming an access channel.
2. Adult/EJA enrollment and teacher outcomes should be reported as non-robust under BJS. This prevents overclaiming an adult-to-child resource shift.
3. Health and birth outcomes should be described as mixed, with no broad health-system mechanism.
4. Spending shares should be described as weak or near-clean at best, implying that level-spending results are more credible than reallocation claims.
5. Most education outcomes fail pretrends, so any education mechanism should be limited to the subset of pass/near outcomes and tested in follow-up specifications.
