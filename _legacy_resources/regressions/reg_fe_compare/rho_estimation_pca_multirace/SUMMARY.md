# Multi-Race PCA Rho Estimation Summary

This phase builds a broader left-preference proxy from three electoral races in 2006, 2010, and 2014: PT presidential runoff vote share, federal deputy left-coalition candidate vote share, and state deputy left-coalition candidate vote share. The left coalition is coded as PT, PSB, PCdoB, PDT, PSOL, PV, and REDE. The goal is to move from a PT-presidential construct toward a more general local-left-preference construct.

The tradeoff is visible in the data. Presidential races are highly persistent across municipalities, but deputy races add local-candidate and party-list noise. Because the deputy variables are candidate-vote shares from `resultados_candidato_municipio`, the measure does not include separate party-list votes.

The multirace PC1 and simple mean are in standardized-index units, not presidential vote-share units. The comparison to the 2010 and PT-only PCA baselines is therefore informative about sign and precision, but the coefficient levels are not perfectly scale-equivalent across preference proxies.

## PCA Construct Validation

PC1 explains only 35.9% of the 9-variable standardized variance, while PC2 explains 27.0%. This is below the 50 percent warning threshold in the prompt, so the multirace PCA should not be treated as a clean one-dimensional replacement for the PT-only presidential PCA.

All nine PC1 loadings have the same positive sign, so the first component is at least directionally coherent. The loadings are reasonably balanced by race: president mean absolute loading 0.370, federal deputy 0.320, and state deputy 0.305. The individual loadings are pt_share_2006_runoff=0.358; pt_share_2010_runoff=0.385; pt_share_2014_runoff=0.366; left_share_dep_fed_2006=0.307; left_share_dep_fed_2010=0.326; left_share_dep_fed_2014=0.327; left_share_dep_est_2006=0.278; left_share_dep_est_2010=0.339; left_share_dep_est_2014=0.299.

Deputy vote-share sanity checks show no values outside [0,1]. Weighted left-coalition shares are roughly 29-36 percent across office-years, while unweighted municipality means are lower, around 25-31 percent. These are somewhat below the rough expectation in the prompt but not wildly implausible given the candidate-result table and the narrow party list.

## Updated Rho Estimates

Using the multirace PC1 as the outcome, the event-time-0 regressions give: Low-ed revealed cost: beta=0.080, SE=0.159, 95% CI [-0.264, 0.423], p=0.625; High-ed revealed cost: beta=0.056, SE=0.136, 95% CI [-0.237, 0.349], p=0.688; High-low compliance gap: beta=0.241, SE=0.275, 95% CI [-0.352, 0.834], p=0.396.

The headline gap estimate remains positive but becomes very imprecise. The separate low- and high-ed revealed-cost proxies are also positive, unlike the PT-only specifications, but neither is distinguishable from zero.

## Comparison To Baselines

For the compliance-gap proxy, the 2010 single-year estimate was beta=0.215 with SE=0.100; the PT-only 3-year PCA estimate was beta=0.174 with SE=0.101; and the multirace PCA estimate is beta=0.241 with SE=0.275. The multirace SE is 171.6% larger than the PT-only PCA SE, so the broader measure does not tighten inference.

This result is consistent with the PCA diagnostics: deputy races broaden the construct but introduce enough independent local noise that the first component is a weak summary of the full matrix.

## Robustness Via Simple Mean

Using the unweighted standardized simple mean of all nine variables gives: Low-ed revealed cost: beta=0.082, SE=0.157, 95% CI [-0.258, 0.421], p=0.613; High-ed revealed cost: beta=0.063, SE=0.136, 95% CI [-0.232, 0.357], p=0.653; High-low compliance gap: beta=0.189, SE=0.266, 95% CI [-0.385, 0.762], p=0.490.

For the gap proxy, the simple mean gives beta=0.189 with SE=0.266, compared with PC1 beta=0.241 and SE=0.275. The simple mean and PC1 agree on the positive sign, but both are too imprecise to improve on the PT-only benchmarks.

## Implications For The Welfare Framework

The multirace exercise supports the qualitative sign of rho_gap but weakens the case for using it as the headline calibration. Across the main specifications, the gap estimate is positive: about 0.215 in the 2010 single-year model, 0.174 in the PT-only 3-year PCA, and 0.241 in the multirace PC1 index. The plausible range remains wide because the multirace confidence interval is large and includes zero by a wide margin.

The most defensible calibration remains the PT-only set of estimates, with the multirace result as a robustness check showing that the positive sign is not unique to presidential PT support. It should not replace the PT-only measure because PC1 captures only 35.9 percent of the multirace variance.

## Limitations

Deputy elections add local-candidate effects, coalition heterogeneity, and candidate-entry noise. The party coding is consequential, especially for PV and REDE, and the candidate-result table omits separate party-list votes. The broader construct is conceptually closer to general left preference, but empirically less one-dimensional and less precise than the presidential PT measures.
