# Rho Estimation Summary

This phase estimates the cross-municipality empirical analog of the model's cost-preference correlation. The analytical sample is hybrid-status municipality-years, where voluntary biometric compliance can be interpreted as revealed compliance friction rather than mechanical saturation after cancellation. The main political-preference proxy is Dilma Rousseff's 2010 second-round presidential vote share, which predates hybrid BVR exposure.

The maintained interpretation is that lower voluntary compliance within an education group reflects higher average compliance cost for that group, while pre-BVR presidential vote shares proxy for local political preferences. These estimates are descriptive correlations, not causal effects, and they are intended to calibrate the sign and approximate magnitude of the welfare-framework parameter rather than identify a treatment effect.

The event-time-0 dataset has 1,845 matched hybrid municipalities. The event-time-2 dataset has 528 matched hybrid municipalities; the `reg-fe` event-time-2 models drop one singleton fixed-effect observation, leaving 527 observations in the regression outputs.

## Raw Correlations

At event time 0 using Dilma's runoff share, the raw correlations are: Low-ed revealed cost: r=0.091, n=1845, p=<0.001; High-ed revealed cost: r=0.005, n=1845, p=0.839; High-low compliance gap: r=0.271, n=1845, p=<0.001.

At event time 2, the same correlations are Low-ed revealed cost: r=-0.034, n=528, p=0.432; High-ed revealed cost: r=-0.106, n=528, p=0.015; High-low compliance gap: r=0.176, n=528, p=<0.001. The gap measure is the most stable raw signal: municipalities where high-ed compliance exceeds low-ed compliance by more also lean more toward Dilma in the pre-BVR runoff.

## Regression-Based Estimates

The main regressions include state fixed effects, controls for log 2010 population and log 2010 GDP per capita, and state-clustered standard errors. At event time 0, the estimates are: Low-ed revealed cost: beta=-0.002, SE=0.041, 95% CI [-0.089, 0.086], p=0.969; High-ed revealed cost: beta=-0.022, SE=0.029, 95% CI [-0.085, 0.042], p=0.470; High-low compliance gap: beta=0.215, SE=0.100, 95% CI [-0.001, 0.430], p=0.051.

After adding state fixed effects and controls, the separate low- and high-ed revealed-cost proxies are close to zero, slightly negative, and imprecise. The compliance-gap coefficient remains positive and is near the conventional 5 percent threshold, which matches the raw-correlation evidence that differential compliance costs are larger in more left-leaning hybrid municipalities.

## Robustness

The event-time-2 gap coefficient remains positive, beta=0.093 with SE=0.094, though the confidence interval is wide. For event-time-0 alternative political outcomes, the gap coefficient is beta=0.204 for Dilma first-round share and beta=0.182 for the broader left-coalition first-round share. With region rather than state fixed effects, the gap coefficient is beta=0.186. In the active-only hybrid sample, the gap coefficient is beta=0.211. These checks preserve the positive sign for the gap-based measure, although precision varies across specifications.

## Implication For The Welfare Framework

The best single empirical analog for rho_bar is the event-time-0 compliance-gap result, because it uses the within-municipality high-low compliance differential in the voluntary hybrid regime. On the raw correlation scale, this value is 0.271; on the regression slope scale with state fixed effects and controls, it is 0.215, with 95% CI [-0.001, 0.430]. The sign is positive: in Brazil, hybrid municipalities with larger revealed education-based compliance gaps are also more left-leaning before BVR. In Corollary 1's threshold inequality, this pushes the welfare assessment toward greater concern about BVR when excluded or high-cost citizens are politically non-random rather than ideologically neutral.

## Limitations

The cross-municipality correlation is not the within-individual correlation between compliance cost and ideal policy that the model defines. Hybrid assignment is not random, voluntary compliance can reflect information, trust, civic engagement, administrative capacity, and outreach rather than only cost, and the 2010 presidential vote share is an aggregate political-preference proxy. The state-fixed-effect specification is therefore best read as a disciplined descriptive calibration of the sign and scale of rho_bar, not as a causal estimate.

## Output Files

The raw presidential data are saved under `data/raw/tse_2010_president/`, and cleaned municipality-level presidential files are saved under `data/clean/tse/`. The rho datasets, configs, regression outputs, raw correlations, main regression summary, and robustness summary are all saved in `resources/regressions/reg_fe_compare/rho_estimation/`.
