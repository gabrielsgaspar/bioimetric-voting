# Agent Simulation Notes

## Data construction

- Persona source: official IBGE 2010 Census sample microdata from the public FTP directory under `Resultados_Gerais_da_Amostra/Microdados`.
- Person records are read from the fixed-width `Amostra_Pessoas` files using the official layout workbook bundled in `Documentacao.zip`.
- The balanced persona design uses 2,000 sampled adults across the requested education, age, sex, region, and municipality-size cells.
- The census microdata do not include a clean direct field for whether an adult currently holds an identity document, so `has_id_document` is imputed from education, urban/rural status, income tier, region, and municipality size. This is the weakest measured persona attribute and should be treated as a modeling assumption.

## LLM design

- Main model: `gpt-5.4-mini`
- Higher-quality validation model on 200 personas: `gpt-5.4`
- Main batch prompt style: detailed baseline modeled directly on the requested prompt.
- Prompt-sensitivity variants: minimal and persona-driven.
- Language check: Portuguese translation of the baseline prompt on the 200-persona validation subsample.
- Counterfactual check: voluntary biometric update plus a small tax credit.

## Main validation numbers

- Municipalities in merged validation sample: 2,789
- Predicted-observed correlation: 0.067
- Weighted correlation: 0.297
- Scatter R^2: 0.004
- Mean predicted dropout: 0.405
- Mean observed dropout: 0.092
- Mean predicted dropout low education: 0.461
- Mean predicted dropout high education: 0.309
- Implied low-education share change: -0.039
- Observed low-education share change: -0.140
- Paper benchmark low-education share change: -0.089

## Stress tests

- Higher-quality-model agreement: 0.770
- Portuguese agreement with English baseline: 0.855
- Baseline mean dropout on validation subsample: 0.292
- Counterfactual mean dropout with tax credit: 0.438

## Coverage

- Stored persona rows: 2,000
- Stored response rows: 3,000
- Stored municipality prediction rows: 5,565
