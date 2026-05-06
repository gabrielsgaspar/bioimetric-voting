from __future__ import annotations

import pandas as pd

from parse_lapop_brazil import read_wave
from utils import CORE_WAVES, normalize_code_for_lookup, normalize_state_name, normalize_text, safe_numeric


CANONICAL_SPECS = {
    "survey_year": {"type": "constant"},
    "wave_label": {"type": "constant"},
    "country": {"type": "constant"},
    "weight": {
        "raw": {2008: None, 2010: "wt", 2012: "wt", 2014: "wt", 2017: "wt", 2019: "wt", 2021: "wt"},
        "transform": "single-country weight from wt when available; missing in 2008 public file",
        "comparable_core": False,
    },
    "upm": {
        "raw": {2008: "upm", 2010: "upm", 2012: "upm", 2014: "upm", 2017: "upm", 2019: "upm", 2021: "upm"},
        "transform": "preserve raw UPM/primary sampling unit",
        "comparable_core": True,
    },
    "cluster": {
        "raw": {2008: "cluster", 2010: "cluster", 2012: None, 2014: "cluster", 2017: "cluster", 2019: "cluster", 2021: None},
        "transform": "preserve raw cluster field when available",
        "comparable_core": False,
    },
    "state_name_raw": {
        "raw": {2008: "prov", 2010: "prov", 2012: "prov", 2014: "prov", 2017: "prov", 2019: "prov", 2021: "prov1t"},
        "transform": "decode state labels from LAPOP value labels",
        "comparable_core": True,
    },
    "municipality_name_raw": {
        "raw": {2008: "municipio", 2010: "bramunicipio", 2012: "municipio", 2014: "municipio", 2017: "municipio", 2019: "municipio", 2021: "municipio1t"},
        "transform": "use string municipality field when present, otherwise decode labels from coded municipality field",
        "comparable_core": True,
    },
    "bairro_raw": {
        "raw": {2008: None, 2010: "bradistrito", 2012: "bradistrito", 2014: None, 2017: None, 2019: None, 2021: None},
        "transform": "preserve bairro/district field when available",
        "comparable_core": False,
    },
    "interview_date": {
        "raw": {2008: "data", 2010: "data", 2012: "data", 2014: "fecha", 2017: "fecha", 2019: "fecha", 2021: "fecha"},
        "transform": "preserve interview date as provided by LAPOP",
        "comparable_core": True,
    },
    "respondent_gender_raw": {
        "raw": {2008: "q1", 2010: "q1", 2012: "q1", 2014: "q1", 2017: "q1", 2019: "q1", 2021: "q1tb"},
        "transform": "decode labeled respondent gender categories",
        "comparable_core": True,
    },
    "age_raw": {
        "raw": {2008: "q2", 2010: "q2", 2012: "q2", 2014: "q2", 2017: "q2", 2019: "q2", 2021: "q2"},
        "transform": "preserve reported age as raw numeric",
        "comparable_core": True,
    },
    "birth_year_raw": {
        "raw": {2008: None, 2010: None, 2012: "q2y", 2014: "q2y", 2017: None, 2019: None, 2021: None},
        "transform": "preserve birth year when available",
        "comparable_core": False,
    },
    "married_raw": {
        "raw": {2008: "q11", 2010: "q11", 2012: "q11", 2014: "q11n", 2017: "q11n", 2019: "q11n", 2021: "q11n"},
        "transform": "decode labeled marital-status categories",
        "comparable_core": True,
    },
    "urban_raw": {
        "raw": {2008: "ur", 2010: "ur", 2012: "ur", 2014: "ur", 2017: "ur", 2019: "ur", 2021: "ur1new"},
        "transform": "decode urban/rural field; 2021 uses a four-category settlement scale",
        "comparable_core": False,
    },
    "education_raw": {
        "raw": {2008: "ed", 2010: "ed", 2012: "ed", 2014: "ed", 2017: "ed", 2019: "ed", 2021: "edr"},
        "transform": "preserve raw education coding or categories",
        "comparable_core": False,
    },
    "education_years_raw": {
        "raw": {2008: "ed", 2010: "ed", 2012: "ed", 2014: "ed", 2017: "ed", 2019: "ed", 2021: None},
        "transform": "treat ed as years-of-schooling in the 2008-2019 core",
        "comparable_core": True,
    },
    "white_raw": {
        "raw": {2008: "etid", 2010: "etid", 2012: "etid", 2014: "etid", 2017: "etid", 2019: "etid", 2021: "etid"},
        "transform": "decode labeled race/self-identification categories",
        "comparable_core": True,
    },
    "working_raw": {
        "raw": {2008: "ocup4a", 2010: "ocup4a", 2012: "ocup4a", 2014: "ocup4a", 2017: "ocup4a", 2019: "ocup4a", 2021: "ocup4a"},
        "transform": "decode labeled employment-status categories",
        "comparable_core": True,
    },
    "trust_inst_respect": {"raw": {year: "b2" for year in [2008, 2010, 2012, 2014, 2017, 2019, 2021]}, "transform": "preserve numeric LAPOP item", "comparable_core": True},
    "trust_rights_protected": {"raw": {year: "b3" for year in [2008, 2010, 2012, 2014, 2017, 2019, 2021]}, "transform": "preserve numeric LAPOP item", "comparable_core": True},
    "trust_proud_system": {"raw": {year: "b4" for year in [2008, 2010, 2012, 2014, 2017, 2019, 2021]}, "transform": "preserve numeric LAPOP item", "comparable_core": True},
    "trust_support_system": {"raw": {year: "b6" for year in [2008, 2010, 2012, 2014, 2017, 2019, 2021]}, "transform": "preserve numeric LAPOP item", "comparable_core": True},
    "trust_parties": {"raw": {2008: "b21", 2010: "b21", 2012: "b21", 2014: "b21", 2017: "b21", 2019: "b21", 2021: None}, "transform": "preserve numeric LAPOP item", "comparable_core": True},
    "trust_president": {"raw": {2008: "b21a", 2010: "b21a", 2012: "b21a", 2014: "b21a", 2017: "b21a", 2019: "b21a", 2021: None}, "transform": "preserve numeric LAPOP item", "comparable_core": True},
    "trust_municipal_gov": {"raw": {year: "b32" for year in [2008, 2010, 2012, 2014, 2017, 2019, 2021]}, "transform": "preserve numeric LAPOP item", "comparable_core": True},
    "trust_elections": {"raw": {2008: "b47", 2010: "b47", 2012: "b47a", 2014: "b47a", 2017: "b47a", 2019: "b47a", 2021: "b47a"}, "transform": "harmonize b47 in 2008/2010 and b47a from 2012 onward into trust_elections", "comparable_core": True},
    "democracy_best_form": {"raw": {year: "ing4" for year in [2008, 2010, 2012, 2014, 2017, 2019, 2021]}, "transform": "preserve numeric LAPOP item", "comparable_core": True},
    "democracy_satisfaction": {"raw": {year: "pn4" for year in [2008, 2010, 2012, 2014, 2017, 2019, 2021]}, "transform": "preserve numeric LAPOP item", "comparable_core": True},
    "democracy_voice_matters": {"raw": {2008: "eff1", 2010: "eff1", 2012: "eff1", 2014: "eff1", 2017: "eff1", 2019: "eff1", 2021: None}, "transform": "preserve numeric LAPOP item", "comparable_core": True},
    "democracy_understands_politics": {"raw": {2008: "eff2", 2010: "eff2", 2012: "eff2", 2014: "eff2", 2017: "eff2", 2019: "eff2", 2021: None}, "transform": "preserve numeric LAPOP item; not part of preferred 3-item democracy index", "comparable_core": False},
    "ideology_raw": {"raw": {year: "l1" for year in [2008, 2010, 2012, 2014, 2017, 2019]}, "transform": "preserve raw ideology item", "comparable_core": False},
    "ideology_scale": {"raw": {year: "l1" for year in [2008, 2010, 2012, 2014, 2017, 2019]}, "transform": "coerce ideology scale to numeric where possible", "comparable_core": False},
    "interest_politics_raw": {"raw": {year: "pol1" for year in [2008, 2010, 2012, 2014, 2017, 2019]}, "transform": "decode labeled political interest item", "comparable_core": False},
    "interest_politics": {"raw": {year: "pol1" for year in [2008, 2010, 2012, 2014, 2017, 2019]}, "transform": "standardize political interest so higher means more interest", "comparable_core": False},
}


EXCLUDED_CANONICAL = {
    "strata": "Not available in the 2008-2019 core waves; appears in 2021 only.",
    "has_voter_title_raw": "Notebook alias could not be verified in the official Brazil wave files as a comparable voter-title item.",
    "has_voter_title": "Notebook alias could not be verified in the official Brazil wave files as a comparable voter-title item.",
}


def label_lookup(meta, variable: str) -> dict[str, str]:
    labelset = meta.variable_to_label.get(variable)
    values = meta.value_labels.get(labelset, {})
    return {normalize_code_for_lookup(k): str(v) for k, v in values.items()}


def decode_labeled(raw: pd.Series, meta, variable: str) -> pd.Series:
    lookup = label_lookup(meta, variable)
    if not lookup:
        return raw.astype("string")
    keys = raw.map(normalize_code_for_lookup)
    return keys.map(lookup).astype("string")


def recode_gender(raw_codes: pd.Series) -> pd.Series:
    numeric = safe_numeric(raw_codes)
    out = pd.Series(pd.NA, index=raw_codes.index, dtype="string")
    out.loc[numeric == 1] = "male"
    out.loc[numeric == 2] = "female"
    out.loc[numeric == 3] = "other"
    return out


def recode_married(raw_codes: pd.Series) -> pd.Series:
    numeric = safe_numeric(raw_codes)
    out = pd.Series(pd.NA, index=raw_codes.index, dtype="Float64")
    out.loc[numeric.isin([2, 3, 7])] = 1
    out.loc[numeric.isin([1, 4, 5, 6])] = 0
    return out


def recode_urban(raw_codes: pd.Series, year: int) -> pd.Series:
    numeric = safe_numeric(raw_codes)
    out = pd.Series(pd.NA, index=raw_codes.index, dtype="Float64")
    if year == 2021:
        out.loc[numeric.isin([1, 2])] = 1
        out.loc[numeric.isin([3, 4])] = 0
    else:
        out.loc[numeric == 1] = 1
        out.loc[numeric == 2] = 0
    return out


def recode_white(raw_codes: pd.Series) -> pd.Series:
    numeric = safe_numeric(raw_codes)
    out = pd.Series(pd.NA, index=raw_codes.index, dtype="Float64")
    out.loc[numeric == 1] = 1
    out.loc[numeric.isin([3, 4, 5, 6, 7, 1506, 2])] = 0
    return out


def recode_working(raw_codes: pd.Series) -> pd.Series:
    numeric = safe_numeric(raw_codes)
    out = pd.Series(pd.NA, index=raw_codes.index, dtype="Float64")
    out.loc[numeric.isin([1, 2])] = 1
    out.loc[numeric.isin([3, 4, 5, 6, 7])] = 0
    return out


def education_category_from_years(years: pd.Series) -> pd.Series:
    out = pd.Series("unknown", index=years.index, dtype="string")
    out.loc[years.notna() & (years <= 10)] = "less_than_secondary"
    out.loc[years.notna() & years.isin([11, 12])] = "secondary"
    out.loc[years.notna() & (years >= 13)] = "tertiary"
    out.loc[years.isna()] = pd.NA
    return out


def education_category_from_edr(raw_codes: pd.Series) -> pd.Series:
    numeric = safe_numeric(raw_codes)
    out = pd.Series(pd.NA, index=raw_codes.index, dtype="string")
    out.loc[numeric == 1] = "less_than_secondary"
    out.loc[numeric == 2] = "secondary"
    out.loc[numeric == 3] = "tertiary"
    return out


def recode_interest(raw_codes: pd.Series) -> pd.Series:
    numeric = safe_numeric(raw_codes)
    out = pd.Series(pd.NA, index=raw_codes.index, dtype="Float64")
    out.loc[numeric == 1] = 3
    out.loc[numeric == 2] = 2
    out.loc[numeric == 3] = 1
    out.loc[numeric == 4] = 0
    return out


def harmonize_wave(year: int) -> pd.DataFrame:
    wanted_raw = sorted({raw for spec in CANONICAL_SPECS.values() if isinstance(spec, dict) for raw in spec.get("raw", {}).values() if raw})
    df, meta = read_wave(year, usecols=wanted_raw, apply_value_formats=False)

    out = pd.DataFrame(index=df.index)
    out["survey_year"] = year
    out["wave_label"] = f"brazil_{year}"
    out["country"] = "brazil"

    weight_var = CANONICAL_SPECS["weight"]["raw"].get(year)
    out["weight"] = safe_numeric(df[weight_var]) if weight_var and weight_var in df.columns else pd.NA
    out["upm"] = df["upm"] if "upm" in df.columns else pd.NA
    cluster_var = CANONICAL_SPECS["cluster"]["raw"].get(year)
    out["cluster"] = df[cluster_var] if cluster_var and cluster_var in df.columns else pd.NA

    state_var = CANONICAL_SPECS["state_name_raw"]["raw"].get(year)
    out["state_name_raw"] = decode_labeled(df[state_var], meta, state_var) if state_var in df.columns else pd.NA
    out["state_name"] = out["state_name_raw"].map(normalize_state_name)

    muni_var = CANONICAL_SPECS["municipality_name_raw"]["raw"].get(year)
    if muni_var in df.columns:
        if muni_var == "bramunicipio":
            out["municipality_name_raw"] = df[muni_var].astype("string")
        else:
            out["municipality_name_raw"] = decode_labeled(df[muni_var], meta, muni_var)
    else:
        out["municipality_name_raw"] = pd.NA
    out["municipality_name"] = out["municipality_name_raw"].map(normalize_text)

    bairro_var = CANONICAL_SPECS["bairro_raw"]["raw"].get(year)
    if bairro_var and bairro_var in df.columns:
        if year == 2010:
            out["bairro_raw"] = df[bairro_var].astype("string")
        else:
            out["bairro_raw"] = df[bairro_var].astype("string")
    else:
        out["bairro_raw"] = pd.NA

    date_var = CANONICAL_SPECS["interview_date"]["raw"].get(year)
    out["interview_date"] = pd.to_datetime(df[date_var], errors="coerce") if date_var in df.columns else pd.NaT

    gender_var = CANONICAL_SPECS["respondent_gender_raw"]["raw"].get(year)
    out["respondent_gender_raw"] = decode_labeled(df[gender_var], meta, gender_var) if gender_var in df.columns else pd.NA
    out["respondent_gender"] = recode_gender(df[gender_var]) if gender_var in df.columns else pd.NA
    out["female"] = out["respondent_gender"].map({"female": 1, "male": 0, "other": pd.NA}).astype("Float64")

    out["age_raw"] = safe_numeric(df["q2"]) if "q2" in df.columns else pd.NA
    out["age"] = out["age_raw"]
    birth_var = CANONICAL_SPECS["birth_year_raw"]["raw"].get(year)
    out["birth_year_raw"] = safe_numeric(df[birth_var]) if birth_var and birth_var in df.columns else pd.NA
    if out["age"].isna().all() and out["birth_year_raw"].notna().any():
        out["age"] = year - out["birth_year_raw"]

    married_var = CANONICAL_SPECS["married_raw"]["raw"].get(year)
    out["married_raw"] = decode_labeled(df[married_var], meta, married_var) if married_var in df.columns else pd.NA
    out["married"] = recode_married(df[married_var]) if married_var in df.columns else pd.NA

    urban_var = CANONICAL_SPECS["urban_raw"]["raw"].get(year)
    out["urban_raw"] = decode_labeled(df[urban_var], meta, urban_var) if urban_var in df.columns else pd.NA
    out["urban"] = recode_urban(df[urban_var], year) if urban_var in df.columns else pd.NA

    edu_var = CANONICAL_SPECS["education_raw"]["raw"].get(year)
    out["education_raw"] = df[edu_var].astype("string") if edu_var and edu_var in df.columns else pd.NA
    if year in CORE_WAVES and edu_var == "ed" and edu_var in df.columns:
        out["education_years_raw"] = safe_numeric(df[edu_var])
        out["education_category"] = education_category_from_years(out["education_years_raw"])
    elif year == 2021 and edu_var == "edr" and edu_var in df.columns:
        out["education_years_raw"] = pd.NA
        out["education_category"] = education_category_from_edr(df[edu_var])
    else:
        out["education_years_raw"] = pd.NA
        out["education_category"] = pd.NA

    race_var = CANONICAL_SPECS["white_raw"]["raw"].get(year)
    out["white_raw"] = decode_labeled(df[race_var], meta, race_var) if race_var in df.columns else pd.NA
    out["white"] = recode_white(df[race_var]) if race_var in df.columns else pd.NA

    work_var = CANONICAL_SPECS["working_raw"]["raw"].get(year)
    out["working_raw"] = decode_labeled(df[work_var], meta, work_var) if work_var in df.columns else pd.NA
    out["working"] = recode_working(df[work_var]) if work_var in df.columns else pd.NA

    for raw_var, canon in [
        ("b2", "trust_inst_respect"),
        ("b3", "trust_rights_protected"),
        ("b4", "trust_proud_system"),
        ("b6", "trust_support_system"),
        ("b21", "trust_parties"),
        ("b21a", "trust_president"),
        ("b32", "trust_municipal_gov"),
        ("ing4", "democracy_best_form"),
        ("pn4", "democracy_satisfaction"),
        ("eff1", "democracy_voice_matters"),
        ("eff2", "democracy_understands_politics"),
    ]:
        out[canon] = safe_numeric(df[raw_var]) if raw_var in df.columns else pd.NA

    out["trust_elections"] = safe_numeric(df["b47"]) if year in [2008, 2010] and "b47" in df.columns else safe_numeric(df["b47a"]) if "b47a" in df.columns else pd.NA

    out["ideology_raw"] = df["l1"].astype("string") if "l1" in df.columns else pd.NA
    out["ideology_scale"] = safe_numeric(df["l1"]) if "l1" in df.columns else pd.NA
    out["interest_politics_raw"] = decode_labeled(df["pol1"], meta, "pol1") if "pol1" in df.columns else pd.NA
    out["interest_politics"] = recode_interest(df["pol1"]) if "pol1" in df.columns else pd.NA

    return out


def build_crosswalk_df() -> pd.DataFrame:
    rows = []
    for canon, spec in CANONICAL_SPECS.items():
        if spec.get("type") == "constant":
            continue
        for year in sorted(spec["raw"].keys()):
            rows.append(
                {
                    "canonical_variable": canon,
                    "survey_year": year,
                    "raw_variable": spec["raw"].get(year),
                    "transform_rule": spec["transform"],
                    "comparable_core": spec["comparable_core"] and year in CORE_WAVES,
                    "notes": "" if spec["raw"].get(year) else "Missing in this wave or not used for this year.",
                }
            )
    for canon, note in EXCLUDED_CANONICAL.items():
        for year in CORE_WAVES:
            rows.append(
                {
                    "canonical_variable": canon,
                    "survey_year": year,
                    "raw_variable": None,
                    "transform_rule": "excluded",
                    "comparable_core": False,
                    "notes": note,
                }
            )
    return pd.DataFrame(rows)
