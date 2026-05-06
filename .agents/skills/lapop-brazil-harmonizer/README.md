# LAPOP Brazil Harmonizer

This skill provides a small Python toolkit for official LAPOP Brazil data discovery, download, harmonization, and documentation.

It is designed for the project's trust-in-institutions and democracy analysis, especially the notebook workflow that:

- builds respondent-level trust and democracy measures,
- preserves municipality and state fields for later merges,
- and documents what is truly comparable across Brazil waves.

The core harmonized panel uses the official Brazil waves:

- `2008`
- `2010`
- `2012`
- `2014`
- `2017`
- `2019`

It also supports later one-off extractions, such as `2021`, after official availability is verified.

Important:

- there is no official public Brazil `2020` wave in the LAPOP catalog
- `2019` is not relabeled as `2020`

Main entry point:

```bash
python .agents/skills/lapop-brazil-harmonizer/scripts/run_lapop_harmonizer.py path/to/config.yml
```
