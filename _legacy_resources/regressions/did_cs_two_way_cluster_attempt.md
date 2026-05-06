# Callaway-Sant'Anna Two-Way Cluster Attempt

Date: 2026-04-27

Requested change: rerun the Callaway-Sant'Anna specifications for `log_num_voters`, `pct_voters_high_ed`, and `pct_voters_low_ed` with standard errors clustered by both `municipality_id` and election year.

Attempted cluster specification:

```yaml
cluster_var:
  - municipality_id
  - year_election
```

Outcome: not rerun. The R `did::att_gt()` implementation used by the `reg-did` skill does not support time-varying cluster variables for this panel setup. Directly passing both variables produced:

```text
Error in mboot(inffunc, DIDparams = dp, pl = pl, cores = cores) :
  can't handle that many cluster variables
```

After translating `municipality_id` to the internal panel id used by `did::att_gt()`, the package then produced:

```text
Error in mboot(inffunc, DIDparams = dp, pl = pl, cores = cores) :
  can't handle time-varying cluster variables
```

Interpretation: the current Callaway-Sant'Anna implementation can cluster at the municipality level for this panel, but it cannot add calendar-year clustering without changing the estimator path or implementing a separate custom variance estimator from suitable observation-level influence functions. The saved C&S outputs therefore remain municipality-clustered only.
