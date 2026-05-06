# Additive Identity Check

The normalized outcomes use a common denominator, each municipality's 2006 registered electorate.
The event-study specification and sample are identical across the four outcomes.

Identity checked at each event time:

```text
gamma_N = gamma_L + gamma_H + gamma_U
```

Result: PASS

Maximum absolute residual: `1.152e-15`

Threshold used for pass/fail: `1e-10`.

If this check passes, downstream decomposition can be computed directly from
the level-normalized coefficients without the residual created by separately
transformed log-count semi-elasticities.
