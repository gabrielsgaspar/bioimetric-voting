# SICONFI Base dos Dados Schema Exploration

This note records the mandatory schema discovery pass for `basedosdados.br_me_siconfi` before building the extended fiscal panel.

## Setup

- BigQuery authentication used `credentials/gcp-key.json` with the project inferred from the service-account key.
- All exploratory queries were run through a dry-run guard with a hard stop above 10 GB scanned per query.
- Municipality coverage gaps are benchmarked against the crosswalk universe of `5570` IBGE municipalities in `data/raw/ibge/bd-tse_mun_ids.csv`.

## Step 1.1 — Table inventory

```text
                            table_name  row_count  size_mb
                brasil_despesas_funcao       9527     1.33
         brasil_despesas_orcamentarias       8165     1.39
          brasil_execucao_restos_pagar      10245     1.28
   brasil_execucao_restos_pagar_funcao      13742     1.36
         brasil_receitas_orcamentarias       6450     1.29
         brasil_variacoes_patrimoniais       5728     0.48
         municipio_balanco_patrimonial   17073607  1375.04
             municipio_despesas_funcao   21206103  2663.04
      municipio_despesas_orcamentarias   27054412  4081.54
       municipio_execucao_restos_pagar    5904831   758.09
municipio_execucao_restos_pagar_funcao    7825473   862.83
      municipio_receitas_orcamentarias   19402392  3099.67
      municipio_variacoes_patrimoniais    7885721   720.97
                    uf_despesas_funcao     175894    24.66
             uf_despesas_orcamentarias     134352    22.71
              uf_execucao_restos_pagar     124869    15.91
       uf_execucao_restos_pagar_funcao     184664     18.8
             uf_receitas_orcamentarias      79647    16.03
             uf_variacoes_patrimoniais      84826     7.16
```

## Step 1.2 — Columns by table

### `brasil_despesas_funcao`

```text
column_name data_type is_nullable is_partitioning_column  clustering_ordinal_position
        ano     INT64         YES                    YES                         <NA>
    estagio    STRING         YES                     NO                         <NA>
   portaria    STRING         YES                     NO                         <NA>
      conta    STRING         YES                     NO                         <NA>
 estagio_bd    STRING         YES                     NO                         <NA>
id_conta_bd    STRING         YES                     NO                         <NA>
   conta_bd    STRING         YES                     NO                         <NA>
      valor   FLOAT64         YES                     NO                         <NA>
```

### `brasil_despesas_orcamentarias`

```text
column_name data_type is_nullable is_partitioning_column  clustering_ordinal_position
        ano     INT64         YES                    YES                         <NA>
    estagio    STRING         YES                     NO                         <NA>
   portaria    STRING         YES                     NO                         <NA>
      conta    STRING         YES                     NO                         <NA>
 estagio_bd    STRING         YES                     NO                         <NA>
id_conta_bd    STRING         YES                     NO                         <NA>
   conta_bd    STRING         YES                     NO                         <NA>
      valor   FLOAT64         YES                     NO                         <NA>
```

### `brasil_execucao_restos_pagar`

```text
column_name data_type is_nullable is_partitioning_column  clustering_ordinal_position
        ano     INT64         YES                    YES                         <NA>
    estagio    STRING         YES                     NO                         <NA>
   portaria    STRING         YES                     NO                         <NA>
      conta    STRING         YES                     NO                         <NA>
 estagio_bd    STRING         YES                     NO                         <NA>
id_conta_bd    STRING         YES                     NO                         <NA>
   conta_bd    STRING         YES                     NO                         <NA>
      valor   FLOAT64         YES                     NO                         <NA>
```

### `brasil_execucao_restos_pagar_funcao`

```text
column_name data_type is_nullable is_partitioning_column  clustering_ordinal_position
        ano     INT64         YES                    YES                         <NA>
    estagio    STRING         YES                     NO                         <NA>
   portaria    STRING         YES                     NO                         <NA>
      conta    STRING         YES                     NO                         <NA>
 estagio_bd    STRING         YES                     NO                         <NA>
id_conta_bd    STRING         YES                     NO                         <NA>
   conta_bd    STRING         YES                     NO                         <NA>
      valor   FLOAT64         YES                     NO                         <NA>
```

### `brasil_receitas_orcamentarias`

```text
column_name data_type is_nullable is_partitioning_column  clustering_ordinal_position
        ano     INT64         YES                    YES                         <NA>
    estagio    STRING         YES                     NO                         <NA>
   portaria    STRING         YES                     NO                         <NA>
      conta    STRING         YES                     NO                         <NA>
 estagio_bd    STRING         YES                     NO                         <NA>
id_conta_bd    STRING         YES                     NO                         <NA>
   conta_bd    STRING         YES                     NO                         <NA>
      valor   FLOAT64         YES                     NO                         <NA>
```

### `brasil_variacoes_patrimoniais`

```text
column_name data_type is_nullable is_partitioning_column  clustering_ordinal_position
        ano     INT64         YES                    YES                         <NA>
   portaria    STRING         YES                     NO                         <NA>
      conta    STRING         YES                     NO                         <NA>
id_conta_bd    STRING         YES                     NO                         <NA>
   conta_bd    STRING         YES                     NO                         <NA>
      valor   FLOAT64         YES                     NO                         <NA>
```

### `municipio_balanco_patrimonial`

```text
 column_name data_type is_nullable is_partitioning_column  clustering_ordinal_position
         ano     INT64         YES                    YES                         <NA>
    sigla_uf    STRING         YES                     NO                         <NA>
id_municipio    STRING         YES                     NO                         <NA>
    portaria    STRING         YES                     NO                         <NA>
       conta    STRING         YES                     NO                         <NA>
 id_conta_bd    STRING         YES                     NO                         <NA>
    conta_bd    STRING         YES                     NO                         <NA>
       valor   FLOAT64         YES                     NO                         <NA>
```

### `municipio_despesas_funcao`

```text
 column_name data_type is_nullable is_partitioning_column  clustering_ordinal_position
         ano     INT64         YES                    YES                         <NA>
    sigla_uf    STRING         YES                     NO                         <NA>
id_municipio    STRING         YES                     NO                         <NA>
     estagio    STRING         YES                     NO                         <NA>
    portaria    STRING         YES                     NO                         <NA>
       conta    STRING         YES                     NO                         <NA>
  estagio_bd    STRING         YES                     NO                         <NA>
 id_conta_bd    STRING         YES                     NO                         <NA>
    conta_bd    STRING         YES                     NO                         <NA>
       valor   FLOAT64         YES                     NO                         <NA>
```

### `municipio_despesas_orcamentarias`

```text
 column_name data_type is_nullable is_partitioning_column  clustering_ordinal_position
         ano     INT64         YES                    YES                         <NA>
    sigla_uf    STRING         YES                     NO                         <NA>
id_municipio    STRING         YES                     NO                         <NA>
     estagio    STRING         YES                     NO                         <NA>
    portaria    STRING         YES                     NO                         <NA>
       conta    STRING         YES                     NO                         <NA>
  estagio_bd    STRING         YES                     NO                         <NA>
 id_conta_bd    STRING         YES                     NO                         <NA>
    conta_bd    STRING         YES                     NO                         <NA>
       valor   FLOAT64         YES                     NO                         <NA>
```

### `municipio_execucao_restos_pagar`

```text
 column_name data_type is_nullable is_partitioning_column  clustering_ordinal_position
         ano     INT64         YES                    YES                         <NA>
    sigla_uf    STRING         YES                     NO                         <NA>
id_municipio    STRING         YES                     NO                         <NA>
     estagio    STRING         YES                     NO                         <NA>
    portaria    STRING         YES                     NO                         <NA>
       conta    STRING         YES                     NO                         <NA>
  estagio_bd    STRING         YES                     NO                         <NA>
 id_conta_bd    STRING         YES                     NO                         <NA>
    conta_bd    STRING         YES                     NO                         <NA>
       valor   FLOAT64         YES                     NO                         <NA>
```

### `municipio_execucao_restos_pagar_funcao`

```text
 column_name data_type is_nullable is_partitioning_column  clustering_ordinal_position
         ano     INT64         YES                    YES                         <NA>
    sigla_uf    STRING         YES                     NO                         <NA>
id_municipio    STRING         YES                     NO                         <NA>
     estagio    STRING         YES                     NO                         <NA>
    portaria    STRING         YES                     NO                         <NA>
       conta    STRING         YES                     NO                         <NA>
  estagio_bd    STRING         YES                     NO                         <NA>
 id_conta_bd    STRING         YES                     NO                         <NA>
    conta_bd    STRING         YES                     NO                         <NA>
       valor   FLOAT64         YES                     NO                         <NA>
```

### `municipio_receitas_orcamentarias`

```text
 column_name data_type is_nullable is_partitioning_column  clustering_ordinal_position
         ano     INT64         YES                    YES                         <NA>
    sigla_uf    STRING         YES                     NO                         <NA>
id_municipio    STRING         YES                     NO                         <NA>
     estagio    STRING         YES                     NO                         <NA>
    portaria    STRING         YES                     NO                         <NA>
       conta    STRING         YES                     NO                         <NA>
  estagio_bd    STRING         YES                     NO                         <NA>
 id_conta_bd    STRING         YES                     NO                         <NA>
    conta_bd    STRING         YES                     NO                         <NA>
       valor   FLOAT64         YES                     NO                         <NA>
```

### `municipio_variacoes_patrimoniais`

```text
 column_name data_type is_nullable is_partitioning_column  clustering_ordinal_position
         ano     INT64         YES                    YES                         <NA>
    sigla_uf    STRING         YES                     NO                         <NA>
id_municipio    STRING         YES                     NO                         <NA>
    portaria    STRING         YES                     NO                         <NA>
       conta    STRING         YES                     NO                         <NA>
 id_conta_bd    STRING         YES                     NO                         <NA>
    conta_bd    STRING         YES                     NO                         <NA>
       valor   FLOAT64         YES                     NO                         <NA>
```

### `uf_despesas_funcao`

```text
column_name data_type is_nullable is_partitioning_column  clustering_ordinal_position
        ano     INT64         YES                    YES                         <NA>
   sigla_uf    STRING         YES                     NO                         <NA>
    estagio    STRING         YES                     NO                         <NA>
   portaria    STRING         YES                     NO                         <NA>
      conta    STRING         YES                     NO                         <NA>
 estagio_bd    STRING         YES                     NO                         <NA>
id_conta_bd    STRING         YES                     NO                         <NA>
   conta_bd    STRING         YES                     NO                         <NA>
      valor   FLOAT64         YES                     NO                         <NA>
```

### `uf_despesas_orcamentarias`

```text
column_name data_type is_nullable is_partitioning_column  clustering_ordinal_position
        ano     INT64         YES                    YES                         <NA>
   sigla_uf    STRING         YES                     NO                         <NA>
    estagio    STRING         YES                     NO                         <NA>
   portaria    STRING         YES                     NO                         <NA>
      conta    STRING         YES                     NO                         <NA>
 estagio_bd    STRING         YES                     NO                         <NA>
id_conta_bd    STRING         YES                     NO                         <NA>
   conta_bd    STRING         YES                     NO                         <NA>
      valor   FLOAT64         YES                     NO                         <NA>
```

### `uf_execucao_restos_pagar`

```text
column_name data_type is_nullable is_partitioning_column  clustering_ordinal_position
        ano     INT64         YES                    YES                         <NA>
   sigla_uf    STRING         YES                     NO                         <NA>
    estagio    STRING         YES                     NO                         <NA>
   portaria    STRING         YES                     NO                         <NA>
      conta    STRING         YES                     NO                         <NA>
 estagio_bd    STRING         YES                     NO                         <NA>
id_conta_bd    STRING         YES                     NO                         <NA>
   conta_bd    STRING         YES                     NO                         <NA>
      valor   FLOAT64         YES                     NO                         <NA>
```

### `uf_execucao_restos_pagar_funcao`

```text
column_name data_type is_nullable is_partitioning_column  clustering_ordinal_position
        ano     INT64         YES                    YES                         <NA>
   sigla_uf    STRING         YES                     NO                         <NA>
    estagio    STRING         YES                     NO                         <NA>
   portaria    STRING         YES                     NO                         <NA>
      conta    STRING         YES                     NO                         <NA>
 estagio_bd    STRING         YES                     NO                         <NA>
id_conta_bd    STRING         YES                     NO                         <NA>
   conta_bd    STRING         YES                     NO                         <NA>
      valor   FLOAT64         YES                     NO                         <NA>
```

### `uf_receitas_orcamentarias`

```text
column_name data_type is_nullable is_partitioning_column  clustering_ordinal_position
        ano     INT64         YES                    YES                         <NA>
   sigla_uf    STRING         YES                     NO                         <NA>
    estagio    STRING         YES                     NO                         <NA>
   portaria    STRING         YES                     NO                         <NA>
      conta    STRING         YES                     NO                         <NA>
 estagio_bd    STRING         YES                     NO                         <NA>
id_conta_bd    STRING         YES                     NO                         <NA>
   conta_bd    STRING         YES                     NO                         <NA>
      valor   FLOAT64         YES                     NO                         <NA>
```

### `uf_variacoes_patrimoniais`

```text
column_name data_type is_nullable is_partitioning_column  clustering_ordinal_position
        ano     INT64         YES                    YES                         <NA>
   sigla_uf    STRING         YES                     NO                         <NA>
   portaria    STRING         YES                     NO                         <NA>
      conta    STRING         YES                     NO                         <NA>
id_conta_bd    STRING         YES                     NO                         <NA>
   conta_bd    STRING         YES                     NO                         <NA>
      valor   FLOAT64         YES                     NO                         <NA>
```

## Step 1.3 — 1,000-row samples

The full 1,000-row samples for the three primary municipality tables were cached under `data/interim/siconfi_bdd/schema/` as both CSV and Parquet:

- `municipio_despesas_funcao_sample_1000.csv` and `municipio_despesas_funcao_sample_1000.parquet`
- `municipio_despesas_orcamentarias_sample_1000.csv` and `municipio_despesas_orcamentarias_sample_1000.parquet`
- `municipio_receitas_orcamentarias_sample_1000.csv` and `municipio_receitas_orcamentarias_sample_1000.parquet`

## Step 1.4 — Coverage, stage coding, and category coding

### `municipio_despesas_funcao` year coverage

```text
 ano  row_count  n_muni  n_nonnull  missing_vs_5570
1996      54432    4535      54432             1035
1997      92844    5157      92844              413
1998      64050    4270      64050             1300
1999      64830    4322      64830             1248
2000      79560    5304      79560              266
2001      81765    5451      81765              119
2002     151060    5395     151060              175
2003     151228    5401     151228              169
2004     858386    5171     858384              399
2005     870670    5245     870670              325
2006     900384    5424     900384              146
2007     878970    5295     878970              275
2008     838300    5050     838300              520
2009     911838    5493     911838               77
2010    1203405    5495     923619               75
2011     904512    5384     904512              186
2012     869400    5175     869400              395
2013     939920    5423     939920              147
2014     926683    5196     926683              374
2015     971547    5442     971547              128
2016     928054    5447     928054              123
2017     996147    5556     996147               14
2018    1027949    5540    1027949               30
2019    1020955    5557    1020955               13
2020     979840    5559     979840               11
2021    1019335    5565    1019335                5
2022    1061175    5554    1061175               16
2023    1093916    5551    1093916               19
2024    1057091    5533    1057091               37
2025     207857    1030     207857             4540
```

### `municipio_despesas_funcao` stage labels

```text
                                 estagio_bd  row_count
                        Despesas Empenhadas   11792083
                        Despesas Liquidadas    3088954
                             Despesas Pagas    3080925
    Inscrição de Restos a Pagar Processados    1693992
Inscrição de Restos a Pagar Não Processados    1264733
                                       None     285416
```

- Full account dictionary cached at `data/interim/siconfi_bdd/schema/municipio_despesas_funcao_accounts.csv`.

### `municipio_despesas_orcamentarias` year coverage

```text
 ano  row_count  n_muni  n_nonnull  missing_vs_5570
1989      42450    4245      42450             1325
1990      43370    4337      43370             1233
1991      42600    4260      42600             1310
1992      42310    4231      42310             1339
1993      47320    4731      47320              839
1994      56496    4708      56496              862
1995      56640    4715      56640              855
1996      55560    4629      55560              941
1997      61896    5157      61896              413
1998     183610    4270     183610             1300
1999     121016    4322     121016             1248
2000     148512    5304     148512              266
2001     234393    5451     234393              119
2002     393835    5395     393835              175
2003     388872    5401     388872              169
2004     708491    5327     708491              243
2005     708075    5245     708075              325
2006     748512    5424     748512              146
2007     773070    5295     773070              275
2008     742350    5050     742350              520
2009    2768472    5493    2768472               77
2010    2785965    5495    2785865               75
2011    2729688    5384    2729688              186
2012    2594995    5175    2594995              395
2013     784480    5472     784480               98
2014     791450    5196     791450              374
2015     835011    5442     835011              128
2016     801758    5447     801758              123
2017     848518    5556     848518               14
2018     870664    5540     870664               30
2019     882153    5557     882153               13
2020     870296    5559     870296               11
2021     901721    5565     901721                5
2022     921169    5554     921169               16
2023     950424    5551     950424               19
2024     935371    5533     935371               37
2025     182899    1030     182899             4540
```

### `municipio_despesas_orcamentarias` stage labels

```text
                                 estagio_bd  row_count
                        Despesas Empenhadas   12042784
                        Despesas Liquidadas    6438536
                             Despesas Pagas    6403404
    Inscrição de Restos a Pagar Processados    1281286
Inscrição de Restos a Pagar Não Processados     888402
```

- Full account dictionary cached at `data/interim/siconfi_bdd/schema/municipio_despesas_orcamentarias_accounts.csv`.

### `municipio_receitas_orcamentarias` year coverage

```text
 ano  row_count  n_muni  n_nonnull  missing_vs_5570
1989     127370    4246     127370             1324
1990     130080    4337     130080             1233
1991     132039    4261     127780             1309
1992     128910    4298     128910             1272
1993     141960    4731     141960              839
1994     169500    4709     169500              861
1995     169812    4715     169812              855
1996     164712    4629     164712              941
1997     170214    5157     170214              413
1998     222040    4270     222040             1300
1999     224744    4322     224744             1248
2000     275808    5304     275808              266
2001     283452    5451     283452              119
2002     485550    5395     485550              175
2003     486090    5401     486090              169
2004     777742    5327     777742              243
2005     791995    5245     791993              325
2006     840720    5424     840720              146
2007     900150    5295     900150              275
2008     858500    5050     858500              520
2009    1087614    5493    1087614               77
2010    1203405    5495    1203274               75
2011    1179096    5384    1179096              186
2012    1133325    5175    1133325              395
2013     452321    5481     452321               89
2014     462750    5191     462750              379
2015     521355    5441     521355              129
2016     544844    5442     544844              128
2017     557858    5555     557858               15
2018     571908    5536     571908               34
2019     637215    5554     637215               16
2020     656060    5558     656060               12
2021     660766    5562     660766                8
2022     692192    5552     692192               18
2023     711084    5549     711084               21
2024     711337    5530     711337               40
2025     137874    1029     137874             4541
```

### `municipio_receitas_orcamentarias` stage labels

```text
                               estagio_bd  row_count
               Receitas Brutas Realizadas   18029730
                        Deduções - FUNDEB     799640
               Outras Deduções da Receita     501140
Deduções - Transferências Constitucionais      71438
                      Deduções da Receita        444
```

- Full account dictionary cached at `data/interim/siconfi_bdd/schema/municipio_receitas_orcamentarias_accounts.csv`.

### Top-level function codes (`municipio_despesas_funcao`)

```text
id_conta_bd                           conta_bd  row_count
   3.00.000 Despesas Exceto Intraorçamentárias     356061
   3.01.000                        Legislativa     264070
   3.02.000                         Judiciária     104971
   3.03.000                Essencial à Justiça      72041
   3.04.000                      Administração     351443
   3.05.000                    Defesa Nacional      60883
   3.06.000                  Segurança Pública     169287
   3.07.000                Relações Exteriores      48221
   3.08.000                 Assistência Social     340973
   3.09.000                 Previdência Social     177982
   3.10.000                              Saúde     352038
   3.11.000                           Trabalho      91883
   3.12.000                           Educação     349560
   3.13.000                            Cultura     294616
   3.14.000              Direitos da Cidadania      82200
   3.15.000                          Urbanismo     332233
   3.16.000                          Habitação     111223
   3.17.000                         Saneamento     200545
   3.18.000                   Gestão Ambiental     227554
   3.19.000               Ciência e Tecnologia      58369
   3.20.000                        Agricultura     293976
   3.21.000                Organização Agrária      49455
   3.22.000                          Indústria      89147
   3.23.000                Comércio e Serviços     152245
   3.24.000                       Comunicações      90766
   3.25.000                            Energia     128958
   3.26.000                         Transporte     255609
   3.27.000                   Desporto e Lazer     293820
   3.28.000                 Encargos Especiais     236436
```

### Top-level economic spending categories (`municipio_despesas_orcamentarias`)

```text
   id_conta_bd                   conta_bd  row_count
2.0.0.00.00.00     Despesas Orçamentárias     479948
2.3.0.00.00.00         Despesas Correntes     477377
2.3.1.00.00.00 Pessoal e Encargos Sociais     436290
2.3.2.00.00.00 Juros e Encargos da Dívida     120500
2.3.3.00.00.00  Outras Despesas Correntes     440401
2.4.0.00.00.00        Despesas de Capital     458688
2.4.4.00.00.00              Investimentos     457668
2.4.5.00.00.00      Inversões Financeiras     183000
2.4.6.00.00.00      Amortização da Dívida     294569
```

### Key revenue categories (`municipio_receitas_orcamentarias`)

```text
       id_conta_bd                                                        conta_bd  row_count
              None      Transferências de Recursos do Sistema Único de Saúde - SUS     301391
1.0.0.0.0.00.00.00                                          Receitas Orçamentárias     273508
1.1.0.0.0.00.00.00                                              Receitas Correntes     273303
1.1.1.0.0.00.00.00                     Impostos, Taxas e Contribuições de Melhoria     216773
1.1.1.1.8.01.01.00 Imposto sobre a Propriedade Predial e Territorial Urbana - IPTU     175877
1.1.1.1.8.02.03.00                     Imposto sobre Serviços de Qualquer Natureza       1752
1.1.1.1.8.02.03.00             Imposto sobre Serviços de Qualquer Natureza - ISSQN     172194
1.1.7.1.1.51.00.00        Cota-Parte do Fundo de Participação dos Municípios - FPM     136496
```

## Units and coding interpretation

- `valor` behaves like current Brazilian reais rather than thousands of reais or pre-deflated units.
- The expenditure stage labels needed for the downstream panel are present directly in `estagio_bd`; the executed-spending stage is `Despesas Liquidadas`.
- Municipality identifiers are stored as seven-digit IBGE municipality codes in string form (`id_municipio`).
- Pre-2013 and post-2013 coverage differ in row counts because the account dictionaries change, but municipality coverage remains high through the election years used in the paper.

## Step 1.5 — São Paulo 2018 sanity check

```text
 ano id_municipio                                  estagio_bd id_conta_bd conta_bd  total_valor
2018      3550308                         Despesas Empenhadas    3.10.000    Saúde 1.013974e+10
2018      3550308                         Despesas Liquidadas    3.10.000    Saúde 9.637595e+09
2018      3550308                              Despesas Pagas    3.10.000    Saúde 9.588775e+09
2018      3550308 Inscrição de Restos a Pagar Não Processados    3.10.000    Saúde 5.021485e+08
2018      3550308     Inscrição de Restos a Pagar Processados    3.10.000    Saúde 4.882010e+07
```

- The `Despesas Liquidadas` total for São Paulo (`id_municipio = 3550308`) in the top-level health function (`id_conta_bd = 3.10.000`, `conta_bd = Saúde`) is approximately `R$ 9.64 billion` in 2018.
- This lands in the expected public-budget range for São Paulo and supports the interpretation that `valor` is reported in current reais at the municipality-year-function level.

## Practical takeaways for panel construction

- Restrict the fiscal build to `ano BETWEEN 2000 AND 2022`; 2025 is clearly incomplete and 2023–2024 are outside the paper window.
- Use `municipio_despesas_funcao` for function-based spending outcomes and select the `Despesas Liquidadas` stage consistently.
- Use top-level function rows such as `3.10.000` (Saúde), `3.12.000` (Educação), and `3.08.000` (Assistência Social) rather than subfunctions to avoid double counting.
- Use `municipio_despesas_orcamentarias` for economic-category outcomes such as `Pessoal e Encargos Sociais`, `Outras Despesas Correntes`, `Investimentos`, and `Amortização da Dívida`.
- Use `municipio_receitas_orcamentarias` for total revenue, tax revenue, IPTU, ISS, FPM, and SUS-transfer outcomes.
