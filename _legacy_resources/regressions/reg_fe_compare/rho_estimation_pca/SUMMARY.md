# PCA-Based Rho Estimation Summary

This phase replaces the single 2010 presidential vote-share proxy with a multi-year left-preference measure built from PT second-round presidential vote shares in 2006, 2010, and 2014. The purpose is to smooth away year-specific noise while preserving the same hybrid event-time-0 sample and the same state-fixed-effect, state-clustered regression design used in the original rho estimation.

The three years cover Lula's 2006 runoff victory and Dilma's 2010 and 2014 runoff victories, all against PSDB candidates. The 2002 and 2018 elections are excluded because they reflect different coalition and backlash environments. The 2014 vote is contemporaneous with first hybrid status for the 2014 hybrid cohort, so it should be read as a useful but not perfectly pre-treatment component of the preference proxy.

The signed PC1 score used in the regressions is rescaled to the mean and standard deviation of the simple three-year PT runoff average. This keeps the coefficient and standard-error scale comparable to the original single-year vote-share outcome while preserving the PCA ranking; raw and z-scored PC1 scores are retained in `municipality_pc1_scores.csv`.

## PCA Construct Validation

PC1 explains 91.8% of the standardized three-year runoff-share variance. The loadings are all positive and nearly equal (2006=0.574, 2010=0.582, 2014=0.576), so the component is a coherent level-of-PT-support construct. The vote-share-scaled PC1 has correlation 0.965 with the 2010 runoff share and the simple three-year mean has correlation 0.962 with the 2010 runoff share.

This is stronger coherence than expected: PC1 captures well above 80 percent of the variance. That validates the multi-year preference construct, but it also means the simple mean and PC1 are almost identical empirically.

## Updated Rho Estimates

Using PC1 as the political-preference outcome, the event-time-0 regressions give: Low-ed revealed cost: beta=0.009, SE=0.035, 95% CI [-0.067, 0.085], p=0.809; High-ed revealed cost: beta=-0.008, SE=0.024, 95% CI [-0.061, 0.045], p=0.753; High-low compliance gap: beta=0.174, SE=0.101, 95% CI [-0.044, 0.393], p=0.108.

The gap-based estimate remains positive, but it is smaller and less precise than the 2010-only estimate. The separate low- and high-ed revealed-cost proxies remain close to zero and imprecise, as in the original state-fixed-effect specification.

## Comparison To Single-Year Baseline

Relative to the single-year 2010 outcome, the PC1 standard-error changes are: Low-ed revealed cost: 13.3% (single-year SE 0.041, PC1 SE 0.035); High-ed revealed cost: 16.5% (single-year SE 0.029, PC1 SE 0.024); High-low compliance gap: -1.5% (single-year SE 0.100, PC1 SE 0.101).

For the headline compliance-gap proxy, the point estimate falls from 0.215 in the single-year model to 0.174 using PC1, and the SE changes from 0.100 to 0.101. Thus the multi-year PCA measure does not tighten the headline gap estimate. The likely reason is not an incoherent preference construct, since PC1 is very stable, but that the 2010-specific relationship between the compliance gap and Dilma support is stronger than the averaged 2006-2014 relationship; after state fixed effects and state-clustered inference, the smoothed outcome does not reduce residual uncertainty for the gap coefficient.

## Robustness Via Simple Mean

The simple three-year runoff mean produces nearly the same results as PC1: Low-ed revealed cost: beta=0.009, SE=0.035, 95% CI [-0.067, 0.084], p=0.805; High-ed revealed cost: beta=-0.007, SE=0.024, 95% CI [-0.060, 0.045], p=0.764; High-low compliance gap: beta=0.171, SE=0.100, 95% CI [-0.045, 0.387], p=0.111.

For the gap proxy, the simple mean gives beta=0.171 with SE=0.100, compared with PC1 beta=0.174 and SE=0.101. Because PC1 and the simple mean are nearly identical and the simple mean is easier to explain, the simple mean is the more interpretable headline multi-year measure.

## Implications For The Welfare Framework

The preferred multi-year descriptive value for the gap-based rho analog is therefore about 0.171 on the vote-share scale, with a plausible interval spanning roughly -0.045 to 0.387. This keeps the sign positive, consistent with the model-relevant concern that differential compliance costs are politically non-random, but it weakens the precision relative to the borderline 2010-only estimate.

## Limitations

The same caveats from the original rho analysis apply: this is a cross-municipality correlation, not the within-individual correlation between compliance cost and ideal policy in the model; hybrid assignment is not random; and voluntary compliance can reflect information, trust, civic engagement, and administrative outreach as well as cost. The inclusion of 2014 may also contaminate the preference proxy for municipalities first exposed to hybrid BVR in 2014, so a narrower 2006-2010 robustness check would be the next natural sensitivity analysis if this measure becomes central to the welfare calibration.
