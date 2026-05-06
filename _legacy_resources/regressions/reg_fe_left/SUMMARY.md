# BVR Vote-Share Policy Shift Tests

This analysis tests whether BVR exposure is associated with a rightward shift in PT presidential vote shares, as predicted by the welfare model when compliance costs are positively correlated with left preferences. The estimands are cross-sectional first differences in municipality-level presidential vote shares, with state fixed effects, 2010 population and GDP-per-capita controls, and state-clustered standard errors.

I separate a cleaner 2010-to-2014 test from a fuller 2014-to-2018 test because 2018 changes combine BVR exposure with the Dilma-to-Haddad candidate transition and the Bolsonaro election environment. The evidence is mixed: the clean test has the predicted negative sign and a negative baseline-left heterogeneity gradient, but its placebo shows a marginal pre-trend; the full 2018 PT-runoff test does not support the prediction, while the broader left-coalition robustness gives weak evidence that strict BVR shifts left vote share down relative to hybrid BVR.

## Data And PC1

The 2018 Base dos Dados pull passes the national sanity check: the weighted Haddad runoff share is 44.90%, close to the expected 44.87%. The final analysis panel has 5,565 complete municipalities. The Test 1 sample has 2,006 municipalities, with 763 treated by 2014 and 1,243 never-treated controls; only 2 of the treated-by-2014 municipalities are hybrid-first. The Test 2 sample has 5,565 municipalities, with 4,322 treated by 2018 and 1,243 never-treated controls.

The pre-treatment PC1 constructed only from 2006 and 2010 PT runoff shares explains 94.25% of the two-year standardized variance. Both loadings are positive and equal by construction in the two-variable PCA, so higher PC1 means higher baseline PT support.

## Test 1 Results

The pooled 2010-to-2014 coefficient is -1.07 pp with SE 0.64 pp, 95% CI [-2.38 pp, 0.24 pp], p=0.106. The sign is consistent with the model's rightward-shift prediction, but the estimate is not conventionally significant.

In the strict-versus-hybrid breakdown, strict-first municipalities have coefficient -1.07 pp with SE 0.64 pp, while hybrid-first municipalities have coefficient -2.41 pp with SE 4.23 pp. The hybrid estimate is not informative because there are only 2 hybrid-first municipalities in the Test 1 treated sample. The strict-minus-hybrid difference is 1.34 pp with SE 4.10 pp, p=0.746.

The heterogeneity result is more aligned with the theory: the interaction between BVR-by-2014 and baseline-left PC1 is -1.43 pp per one standard deviation of baseline PT support, with SE 0.57 pp, 95% CI [-2.61 pp, -0.25 pp], p=0.020. This means the estimated PT-share decline is larger in municipalities that were more left-leaning before BVR.

## Test 2 Results

In the 2014-to-2018 pooled PT-runoff specification, the BVR-by-2018 coefficient is 0.33 pp with SE 0.50 pp, 95% CI [-0.70 pp, 1.36 pp], p=0.521. This is the opposite sign from the model prediction and is not statistically distinguishable from zero.

The strict and hybrid PT-runoff coefficients are similarly small and positive: strict 0.29 pp with SE 0.54 pp, and hybrid 0.39 pp with SE 0.50 pp. The strict-minus-hybrid difference is -0.09 pp with SE 0.38 pp, p=0.806. The baseline-left interaction is 0.35 pp, p=0.605, so the 2018 runoff test does not reproduce the Test 1 heterogeneity pattern.

Using the broader 2014-to-2018 first-round left-coalition outcome, the pooled BVR coefficient is -0.27 pp with SE 0.68 pp, p=0.692. The strict coefficient is -0.50 pp and the hybrid coefficient is 0.17 pp; the strict-minus-hybrid difference is -0.68 pp with SE 0.33 pp, p=0.052. This robustness is closer to the model's strict-versus-hybrid prediction, but remains borderline.

## Placebos

The Test 1 placebo, using the 2006-to-2010 change and eventual BVR-by-2014 status, gives coefficient -0.96 pp with SE 0.49 pp, 95% CI [-1.97 pp, 0.04 pp], p=0.060. This marginal negative pre-trend is a real warning: the clean Test 1 sign may partly reflect pre-existing differential PT trends rather than BVR alone.

The Test 2 placebo, using 2010-to-2014 changes for municipalities first treated in 2016 or 2018 versus never-treated municipalities, gives coefficient -0.73 pp with SE 0.49 pp, 95% CI [-1.74 pp, 0.29 pp], p=0.151. This placebo is not significant, though the sign is also negative.

## Strict Versus Hybrid

The strict-versus-hybrid decomposition is weakest in Test 1 because hybrid-first exposure by 2014 is almost absent. In Test 2 using PT runoff shares, strict and hybrid effects are nearly identical and small. In the broader left-coalition 2018 robustness, strict BVR is more negative than hybrid by about 0.68 percentage points, which is the closest result to the theoretical exclusion channel.

## Implications

The empirical evidence does not deliver a clean, decisive vote-share confirmation of the model. The most credible pro-model evidence is the Test 1 negative pooled sign and the negative baseline-left heterogeneity coefficient, plus the strict-relative-to-hybrid left-coalition result in 2018. The main caution is that the Test 1 placebo has a marginal pre-trend in the same direction, while the full 2018 PT-runoff test is null and opposite-signed.

For the welfare framework's d(tau) component, a cautious calibration would treat the observable vote-share shift as small: roughly a 1.1 percentage-point PT-share decline in the clean 2010-to-2014 pooled specification, with uncertainty large enough to include zero. The evidence supports using a modest rightward-shift channel in sensitivity analysis, not as a tightly estimated central effect.

## Limitations

The 2018 estimates are hard to interpret because the election combines BVR exposure with the Bolsonaro environment and the Dilma-to-Haddad candidate change. The Test 1 treated sample is much smaller and nearly all strict-first, so it cannot identify a clean strict-versus-hybrid contrast. The designs also rely on parallel trends, and the 2006-to-2010 placebo raises concern for the clean test. Finally, presidential vote shares combine turnout, persuasion, composition, and candidate effects, so they are only an indirect proxy for equilibrium policy shifts.
