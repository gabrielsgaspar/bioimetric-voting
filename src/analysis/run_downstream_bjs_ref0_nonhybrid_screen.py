#!/usr/bin/env python3
"""Run BJS ref-0 event-study screens for downstream BVR outcome panels.

The script reuses the repository's cleaned downstream panels, excludes
municipalities ever flagged as hybrid BVR, runs the imputation/BJS estimator
through the ``reg-did`` skill, and then normalizes each event-study path to
event time 0 for plotting and ranking.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import yaml


ROOT = Path(__file__).resolve().parents[2]
REG_DID_RUNNER = Path.home() / ".codex" / "skills" / "reg-did" / "scripts" / "run_estimator.R"

CLEAN_DOWNSTREAM = ROOT / "data" / "clean" / "downstream"
INTERIM_ROOT = ROOT / "data" / "interim" / "downstream_bjs_ref0_nonhybrid"
OUTPUT_ROOT = ROOT / "resources" / "did" / "downstream_bjs_ref0_nonhybrid"
FIGURE_ROOT = ROOT / "resources" / "figures" / "downstream_bjs_ref0_nonhybrid"
TABLE_ROOT = ROOT / "resources" / "tables" / "downstream_bjs_ref0_nonhybrid"

NEVER_TREATED_VALUE = 9999
REFERENCE_EVENT_TIME = 0
LEAD = 8
LAG = 8
MIN_YEAR = 2000
MAX_YEAR = 2020
SEED = 20260519

BASE_COLUMNS = [
    "municipality_id",
    "ever_hybrid_bvr",
    "year_treated_strict",
    "first_strict_bvr_year",
]

COLORS = {
    "birth_health": "#2C5A8A",
    "education": "#8D3C2F",
    "adult_eja": "#7A4B24",
    "siconfi_log_pc": "#3F6F4E",
    "siconfi_spending_shares": "#6E4A8E",
    "school_access_transport": "#B75638",
}

CATEGORY_LABELS = {
    "birth_health": "Birth and health outcomes",
    "education": "Education outcomes",
    "adult_eja": "Adult education / EJA outcomes",
    "siconfi_log_pc": "Log expenditure per capita",
    "siconfi_spending_shares": "Spending shares",
    "school_access_transport": "School access / transport",
}


@dataclass(frozen=True)
class OutcomeSpec:
    slug: str
    column: str
    label: str
    panel_path: Path
    category: str
    family: str
    frequency: str
    y_label: str
    time_col: str = "year"
    color: str | None = None
    scale: float = 1.0
    numerator_col: str | None = None
    denominator_col: str | None = None
    denominator_panel_path: Path | None = None
    cycle_window: str | None = None
    min_time: int = MIN_YEAR
    max_time: int = MAX_YEAR
    note: str = ""

    @property
    def analysis_column(self) -> str:
        if self.numerator_col or self.scale != 1.0:
            return f"bjs_{self.slug}"
        return self.column

    @property
    def sample_path(self) -> Path:
        return INTERIM_ROOT / self.category / self.frequency / f"{self.slug}.parquet"

    @property
    def output_dir(self) -> Path:
        return OUTPUT_ROOT / self.category / self.frequency / self.family / self.slug

    @property
    def config_path(self) -> Path:
        return self.output_dir / "config.yml"

    @property
    def figure_path(self) -> Path:
        return FIGURE_ROOT / self.category / self.frequency / f"{self.slug}_bjs_ref0_nonhybrid.png"

    @property
    def color_value(self) -> str:
        return self.color or COLORS.get(self.category, "#2C5A8A")


def safe_slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def relative(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


def find_rscript() -> str:
    found = shutil.which("Rscript")
    if found:
        return found
    candidates = sorted((Path.home() / "AppData" / "Local" / "Programs" / "R").glob("R-*/bin/Rscript.exe"))
    candidates.extend(sorted((Path.home() / "AppData" / "Local" / "Programs" / "R").glob("R-*/bin/x64/Rscript.exe")))
    candidates.extend(sorted(Path("C:/Program Files/R").glob("R-*/bin/Rscript.exe")))
    candidates.extend(sorted(Path("C:/Program Files/R").glob("R-*/bin/x64/Rscript.exe")))
    if candidates:
        return str(candidates[-1])
    raise FileNotFoundError("Could not find Rscript.")


def normalize_municipality_id(series: pd.Series) -> pd.Series:
    out = series.astype("string").str.replace(r"\.0$", "", regex=True).str.strip()
    out = out.mask(out.isin(["", "<NA>", "nan", "None"]))
    return out.where(out.isna(), out.str.zfill(7))


def pretty_label(column: str) -> str:
    text = column
    prefixes = [
        "sinasc_all_",
        "sinasc_lowedu_",
        "sinasc_highedu_",
        "inep_ind_",
        "inep_transition_",
        "ideb_",
        "saeb_",
        "siconfi_",
        "school_access_",
    ]
    for prefix in prefixes:
        text = text.replace(prefix, "")
    return text.replace("_", " ").title()


def y_label_for_column(column: str) -> str:
    if column.startswith("log1p") or "_log1p_" in column or column.startswith("siconfi_log1p"):
        return "log points"
    if column.endswith("_pp") or "_taxa_" in column or "share_pp" in column:
        return "percentage points"
    if "birthweight" in column and "grams" in column:
        return "grams"
    if "saeb" in column or "ideb" in column:
        return "score/index points"
    if column.endswith("_per_100k"):
        return "rate per 100k"
    if column.endswith("_per_1000") or "_per_1000_" in column:
        return "rate per 1,000"
    return "estimate"


def parquet_columns(path: Path) -> list[str]:
    return pq.read_schema(path).names


def health_specs() -> list[OutcomeSpec]:
    panel = CLEAN_DOWNSTREAM / "bdd_health_bvr_screen_panel_2000_2020.parquet"
    groups = {
        "all": ("All mothers", "#2C5A8A"),
        "lowedu": ("Low education proxy", "#2C5A8A"),
        "highedu": ("High education proxy", "#B75638"),
    }
    birth_outcomes = [
        ("mean_birthweight_grams", "Mean birthweight", "grams"),
        ("low_birthweight_share_total_pp", "Low-birthweight share", "percentage points"),
        ("very_low_birthweight_share_total_pp", "Very-low-birthweight share", "percentage points"),
        ("high_birthweight_share_total_pp", "High-birthweight share", "percentage points"),
        ("preterm_share_known_pp", "Preterm birth share", "percentage points"),
        ("very_preterm_share_known_pp", "Very-preterm birth share", "percentage points"),
        ("csection_share_known_pp", "C-section share", "percentage points"),
        ("no_prenatal_share_known_pp", "No prenatal visits share", "percentage points"),
        ("prenatal_1to3_share_known_pp", "1-3 prenatal visits share", "percentage points"),
        ("prenatal_7plus_share_known_pp", "7+ prenatal visits share", "percentage points"),
        ("prenatal_adequate_share_known_pp", "Adequate prenatal visits share", "percentage points"),
        ("low_apgar1_share_known_pp", "Low Apgar 1 share", "percentage points"),
        ("low_apgar5_share_known_pp", "Low Apgar 5 share", "percentage points"),
        ("congenital_anomaly_share_known_pp", "Congenital anomaly share", "percentage points"),
        ("teen_mother_share_known_pp", "Teen mother share", "percentage points"),
        ("mother_35plus_share_known_pp", "Mother age 35+ share", "percentage points"),
        ("multiple_pregnancy_share_known_pp", "Multiple pregnancy share", "percentage points"),
        ("hospital_birth_location_share_known_pp", "Hospital birth-location share", "percentage points"),
    ]
    specs: list[OutcomeSpec] = []
    for group, (group_label, color) in groups.items():
        for suffix, label, y_label in birth_outcomes:
            column = f"sinasc_{group}_{suffix}"
            specs.append(
                OutcomeSpec(
                    slug=safe_slug(column),
                    column=column,
                    label=f"{label}: {group_label}",
                    panel_path=panel,
                    category="birth_health",
                    family=f"sinasc_{group}",
                    frequency="annual",
                    y_label=y_label,
                    color=color,
                    note="SINASC outcomes inside the BDD health screen.",
                )
            )
    external_entries = [
        ("imun_cobertura_total_pp", "Total immunization coverage", "immunization", "percentage points"),
        ("imun_bcg_pp", "BCG coverage", "immunization", "percentage points"),
        ("imun_polio_pp", "Polio coverage", "immunization", "percentage points"),
        ("imun_triplice_viral_d1_pp", "Triple viral dose 1 coverage", "immunization", "percentage points"),
        ("imun_penta_pp", "Pentavalent coverage", "immunization", "percentage points"),
        ("imun_rotavirus_pp", "Rotavirus coverage", "immunization", "percentage points"),
        ("imun_pneumococica_pp", "Pneumococcal coverage", "immunization", "percentage points"),
        ("imun_meningococo_pp", "Meningococcal coverage", "immunization", "percentage points"),
        ("imun_hepatite_b_rn_pp", "Hepatitis B newborn coverage", "immunization", "percentage points"),
        ("ab_esf_coverage_pp", "Family Health Strategy coverage", "primary_care", "percentage points"),
        ("ab_total_coverage_pp", "Total primary-care coverage", "primary_care", "percentage points"),
        ("ieps_cob_ab_pp", "IEPS primary-care coverage", "ieps", "percentage points"),
        ("ieps_cob_acs_pp", "IEPS community health-agent coverage", "ieps", "percentage points"),
        ("ieps_cob_esf_pp", "IEPS Family Health Strategy coverage", "ieps", "percentage points"),
        ("ieps_prenatal_zero_pp", "IEPS no-prenatal share", "ieps", "percentage points"),
        ("ieps_prenatal_7plus_pp", "IEPS 7+ prenatal visits share", "ieps", "percentage points"),
        ("ieps_mortality_per_100k", "IEPS mortality", "ieps", "rate per 100k"),
        ("ieps_mortality_csap_per_100k", "IEPS CSAP mortality", "ieps", "rate per 100k"),
        ("ieps_mortality_avoidable_per_100k", "IEPS avoidable mortality", "ieps", "rate per 100k"),
        ("ieps_mortality_ill_defined_pp", "IEPS ill-defined mortality share", "ieps", "percentage points"),
        ("ieps_hospitalizations_per_100k", "IEPS hospitalizations", "ieps", "rate per 100k"),
        ("ieps_hospitalizations_csap_per_100k", "IEPS CSAP hospitalizations", "ieps", "rate per 100k"),
        ("ieps_sus_beds_per_100k", "IEPS SUS beds", "ieps", "rate per 100k"),
        ("ieps_sus_icu_beds_per_100k", "IEPS SUS ICU beds", "ieps", "rate per 100k"),
        ("ieps_doctors_per_1000", "IEPS doctors", "ieps", "rate per 1,000"),
        ("ieps_nurses_per_1000", "IEPS nurses", "ieps", "rate per 1,000"),
        ("ieps_private_plan_coverage_pp", "IEPS private plan coverage", "ieps", "percentage points"),
        ("sim_mortality_per_100k", "SIM all-cause mortality", "sim", "rate per 100k"),
        ("sim_infant_mortality_per_1000_births", "SIM infant mortality", "sim", "rate per 1,000 births"),
        ("sim_under5_mortality_per_1000_births", "SIM under-5 mortality", "sim", "rate per 1,000 births"),
    ]
    colors = {
        "immunization": "#4D7C2F",
        "primary_care": "#7A4B24",
        "ieps": "#6E4A8E",
        "sim": "#5E6C77",
    }
    for column, label, family, y_label in external_entries:
        specs.append(
            OutcomeSpec(
                slug=safe_slug(column),
                column=column,
                label=label,
                panel_path=panel,
                category="birth_health",
                family=family,
                frequency="annual",
                y_label=y_label,
                color=colors[family],
            )
        )
    return specs


def dedicated_sinasc_specs() -> list[OutcomeSpec]:
    birthweight = CLEAN_DOWNSTREAM / "sinasc_birthweight_bvr_panel_2000_2020.parquet"
    edu = CLEAN_DOWNSTREAM / "sinasc_birthweight_by_mother_education_bvr_panel_2000_2020.parquet"
    return [
        OutcomeSpec(
            "sinasc_dedicated_mean_birthweight_all",
            "mean_birthweight_grams",
            "SINASC mean birthweight: all births",
            birthweight,
            "birth_health",
            "sinasc_dedicated",
            "annual",
            "grams",
            color="#2C5A8A",
        ),
        OutcomeSpec(
            "sinasc_dedicated_mean_birthweight_low_education",
            "mean_birthweight_grams_low_education",
            "SINASC mean birthweight: low education proxy",
            edu,
            "birth_health",
            "sinasc_dedicated",
            "annual",
            "grams",
            color="#2C5A8A",
            note="Low education proxy is 0-7 completed years.",
        ),
        OutcomeSpec(
            "sinasc_dedicated_mean_birthweight_high_education",
            "mean_birthweight_grams_high_education",
            "SINASC mean birthweight: high education proxy",
            edu,
            "birth_health",
            "sinasc_dedicated",
            "annual",
            "grams",
            color="#B75638",
            note="High education proxy is 8+ completed years.",
        ),
        OutcomeSpec(
            "sinasc_dedicated_low_birthweight_low_education_share",
            "low_birthweight_share_total_low_education",
            "SINASC low-birthweight share: low education proxy",
            edu,
            "birth_health",
            "sinasc_dedicated",
            "annual",
            "share",
            color="#2C5A8A",
            note="Share is kept in 0-1 units from the dedicated SINASC panel.",
        ),
        OutcomeSpec(
            "sinasc_dedicated_low_birthweight_high_education_share",
            "low_birthweight_share_total_high_education",
            "SINASC low-birthweight share: high education proxy",
            edu,
            "birth_health",
            "sinasc_dedicated",
            "annual",
            "share",
            color="#B75638",
            note="Share is kept in 0-1 units from the dedicated SINASC panel.",
        ),
    ]


def education_specs() -> list[OutcomeSpec]:
    panel_path = CLEAN_DOWNSTREAM / "bdd_education_bvr_screen_panel_2000_2020.parquet"
    columns = parquet_columns(panel_path)
    specs: list[OutcomeSpec] = []
    for column in sorted(columns):
        if column.startswith("ideb_"):
            family = "achievement"
            frequency = "biennial"
        elif column.startswith("saeb_"):
            family = "achievement"
            frequency = "biennial"
        elif column.startswith("inep_transition_") or column.startswith("inep_ind_"):
            if any(token in column for token in ["atu_", "had_"]):
                family = "school_inputs"
            elif any(token in column for token in ["dsu_", "afd_", "ied_", "ird_"]):
                family = "teacher_profile"
            else:
                family = "dropout_flow"
            frequency = "annual"
        elif column.startswith("siconfi_"):
            family = "spending"
            frequency = "annual"
        else:
            continue
        specs.append(
            OutcomeSpec(
                slug=safe_slug(column),
                column=column,
                label=pretty_label(column),
                panel_path=panel_path,
                category="education",
                family=family,
                frequency=frequency,
                y_label=y_label_for_column(column),
                color=COLORS["education"] if family == "dropout_flow" else "#2C5A8A" if family == "achievement" else "#4D7C2F",
            )
        )
    return specs


def adult_eja_specs() -> list[OutcomeSpec]:
    panel = CLEAN_DOWNSTREAM / "bdd_adult_education_bvr_panel_2000_2020.parquet"
    rows = [
        ("log_municipal_eja_enrollment", "log1p_enrollment_municipal_eja_total", "EJA enrollment, municipal schools", "adult_enrollment", "log count"),
        ("log_public_eja_enrollment", "log1p_enrollment_public_eja_total", "EJA enrollment, public schools", "adult_enrollment", "log count"),
        ("municipal_eja_enrollment_per_1000", "enrollment_municipal_eja_total_per_1000", "EJA enrollment per 1,000 residents, municipal schools", "adult_enrollment", "per 1,000 residents"),
        ("public_eja_enrollment_per_1000", "enrollment_public_eja_total_per_1000", "EJA enrollment per 1,000 residents, public schools", "adult_enrollment", "per 1,000 residents"),
        ("municipal_eja_enrollment_share", "enrollment_municipal_eja_share_selected_pp", "EJA share of selected enrollment, municipal schools", "adult_enrollment", "percentage points"),
        ("public_eja_enrollment_share", "enrollment_public_eja_share_selected_pp", "EJA share of selected enrollment, public schools", "adult_enrollment", "percentage points"),
        ("log_municipal_child_enrollment", "log1p_enrollment_municipal_child_regular_total", "Regular child enrollment, municipal schools", "child_enrollment", "log count"),
        ("log_public_child_enrollment", "log1p_enrollment_public_child_regular_total", "Regular child enrollment, public schools", "child_enrollment", "log count"),
        ("municipal_child_enrollment_per_1000", "enrollment_municipal_child_regular_total_per_1000", "Regular child enrollment per 1,000 residents, municipal schools", "child_enrollment", "per 1,000 residents"),
        ("public_child_enrollment_per_1000", "enrollment_public_child_regular_total_per_1000", "Regular child enrollment per 1,000 residents, public schools", "child_enrollment", "per 1,000 residents"),
        ("log_municipal_eja_teachers", "log1p_teachers_municipal_eja_total", "EJA teachers, municipal schools", "adult_teachers", "log count"),
        ("log_public_eja_teachers", "log1p_teachers_public_eja_total", "EJA teachers, public schools", "adult_teachers", "log count"),
        ("municipal_eja_teacher_share", "teachers_municipal_eja_share_selected_pp", "EJA teacher share, municipal schools", "adult_teachers", "percentage points"),
        ("public_eja_teacher_share", "teachers_public_eja_share_selected_pp", "EJA teacher share, public schools", "adult_teachers", "percentage points"),
        ("log_municipal_child_teachers", "log1p_teachers_municipal_child_regular_total", "Regular child teachers, municipal schools", "child_teachers", "log count"),
        ("log_public_child_teachers", "log1p_teachers_public_child_regular_total", "Regular child teachers, public schools", "child_teachers", "log count"),
        ("log_eja_spending_pc", "log1p_spending_pc_2008_eja", "EJA spending per capita", "spending", "log per-capita 2008 BRL"),
        ("eja_spending_share", "spending_eja_share_education_pp", "EJA share of education spending", "spending", "percentage points"),
        ("eja_spending_share_clean", "spending_eja_share_education_clean_pp", "EJA share of education spending, clean denominator", "spending", "percentage points"),
        ("log_child_spending_pc", "log1p_spending_pc_2008_child_total", "Child/basic education spending per capita", "spending", "log per-capita 2008 BRL"),
        ("child_spending_share", "spending_child_share_education_pp", "Child/basic share of education spending", "spending", "percentage points"),
        ("child_spending_share_clean", "spending_child_share_education_clean_pp", "Child/basic share of education spending, clean denominator", "spending", "percentage points"),
        ("eja_to_child_spending_clean", "spending_eja_to_child_clean_pp", "EJA spending relative to child/basic spending, clean denominator", "spending", "percentage points"),
    ]
    specs = []
    for slug, column, label, family, y_label in rows:
        color = "#8D3C2F" if "eja" in slug else "#2C5A8A" if "child" in slug else COLORS["adult_eja"]
        specs.append(
            OutcomeSpec(
                slug=slug,
                column=column,
                label=label,
                panel_path=panel,
                category="adult_eja",
                family=family,
                frequency="annual",
                y_label=y_label,
                color=color,
            )
        )
    return specs


def school_access_specs() -> list[OutcomeSpec]:
    panel = CLEAN_DOWNSTREAM / "bdd_school_access_bvr_panel_2000_2020.parquet"
    rows = [
        ("public_public_transport_share", "school_access_public_public_transport_enrollment_share_pp", "Public-school students using public school transport", "transport_access"),
        ("public_municipal_transport_share", "school_access_public_municipal_transport_enrollment_share_pp", "Public-school students with municipal-responsibility transport", "transport_access"),
        ("public_state_transport_share", "school_access_public_state_transport_enrollment_share_pp", "Public-school students with state-responsibility transport", "transport_access"),
        ("public_bus_van_transport_share", "school_access_public_bus_van_transport_enrollment_share_pp", "Public-school students using bus/van transport", "transport_access"),
        ("public_boat_transport_share", "school_access_public_boat_transport_enrollment_share_pp", "Public-school students using boat transport", "transport_access"),
        ("public_rural_residence_share", "school_access_public_rural_residence_enrollment_share_pp", "Public-school students living in rural areas", "residence_access"),
        ("public_cross_municipality_share", "school_access_public_cross_municipality_residence_enrollment_share_pp", "Public-school students living outside school municipality", "residence_access"),
        ("municipal_public_transport_share", "school_access_municipal_public_transport_enrollment_share_pp", "Municipal-school students using public transport", "municipal_school_access"),
        ("municipal_municipal_transport_share", "school_access_municipal_municipal_transport_enrollment_share_pp", "Municipal-school students with municipal-responsibility transport", "municipal_school_access"),
        ("municipal_state_transport_share", "school_access_municipal_state_transport_enrollment_share_pp", "Municipal-school students with state-responsibility transport", "municipal_school_access"),
        ("municipal_bus_van_transport_share", "school_access_municipal_bus_van_transport_enrollment_share_pp", "Municipal-school students using bus/van transport", "municipal_school_access"),
        ("municipal_boat_transport_share", "school_access_municipal_boat_transport_enrollment_share_pp", "Municipal-school students using boat transport", "municipal_school_access"),
        ("municipal_rural_residence_share", "school_access_municipal_rural_residence_enrollment_share_pp", "Municipal-school students living in rural areas", "municipal_school_access"),
        ("municipal_cross_municipality_share", "school_access_municipal_cross_municipality_residence_enrollment_share_pp", "Municipal-school students living outside school municipality", "municipal_school_access"),
    ]
    specs = []
    for slug, column, label, family in rows:
        specs.append(
            OutcomeSpec(
                slug=slug,
                column=column,
                label=label,
                panel_path=panel,
                category="school_access_transport",
                family=family,
                frequency="annual",
                y_label="share",
                scale=0.01,
                color=COLORS["school_access_transport"],
                note="Original panel column is in percentage points; BJS sample divides by 100 to keep shares in 0-1 units.",
            )
        )
    return specs


def siconfi_specs() -> list[OutcomeSpec]:
    annual_spend = CLEAN_DOWNSTREAM / "siconfi_spending_categories_annual_2000_2022.parquet"
    cycle_spend = CLEAN_DOWNSTREAM / "siconfi_spending_categories_cycle2_2000_2022.parquet"
    annual_revenue = CLEAN_DOWNSTREAM / "siconfi_tax_capacity_annual_2000_2022.parquet"
    cycle_revenue = CLEAN_DOWNSTREAM / "siconfi_tax_capacity_cycle2_2000_2022.parquet"
    categories = [
        ("education", "Education"),
        ("health", "Health"),
        ("infrastructure_spending", "Infrastructure"),
        ("urbanism", "Urbanism"),
        ("transport", "Transport"),
    ]
    specs: list[OutcomeSpec] = []
    panels = [
        ("annual", annual_spend, "fiscal_year", None, annual_revenue),
        ("cycle2", cycle_spend, "cycle_year", "forward_two_year", cycle_revenue),
    ]
    for frequency, panel, time_col, cycle_window, revenue_panel in panels:
        for key, label in categories:
            specs.append(
                OutcomeSpec(
                    slug=f"siconfi_{frequency}_{key}_log_pc",
                    column=f"log1p_{key}_pc_2008",
                    label=f"{label} expenditure per capita, log(1+x), {frequency}",
                    panel_path=panel,
                    category="siconfi_log_pc",
                    family=key,
                    frequency=frequency,
                    y_label="log per-capita 2008 BRL",
                    time_col=time_col,
                    cycle_window=cycle_window,
                    color=COLORS["siconfi_log_pc"],
                )
            )
            specs.append(
                OutcomeSpec(
                    slug=f"siconfi_{frequency}_{key}_share_total_spending",
                    column=f"{key}_share_total_spending",
                    label=f"{label} share of total expenditure, {frequency}",
                    panel_path=panel,
                    category="siconfi_spending_shares",
                    family="share_total_spending",
                    frequency=frequency,
                    y_label="share",
                    time_col=time_col,
                    numerator_col=f"{key}_real_2008",
                    denominator_col="total_spending_real_2008",
                    cycle_window=cycle_window,
                    color=COLORS["siconfi_spending_shares"],
                    note="Derived as category real expenditure divided by total real expenditure; kept in 0-1 units.",
                )
            )
        for key, label in [
            ("infrastructure_spending", "Infrastructure"),
            ("urbanism", "Urbanism"),
            ("transport", "Transport"),
        ]:
            specs.append(
                OutcomeSpec(
                    slug=f"siconfi_{frequency}_{key}_share_total_revenue",
                    column=f"{key}_share_total_revenue",
                    label=f"{label} share of total revenue, {frequency}",
                    panel_path=panel,
                    category="siconfi_spending_shares",
                    family="share_total_revenue",
                    frequency=frequency,
                    y_label="share",
                    time_col=time_col,
                    numerator_col=f"{key}_real_2008",
                    denominator_col="total_revenue_real_2008",
                    denominator_panel_path=revenue_panel,
                    cycle_window=cycle_window,
                    color=COLORS["siconfi_spending_shares"],
                    note="Derived as category real expenditure divided by total real revenue; kept in 0-1 units.",
                )
            )
    return specs


def all_specs() -> list[OutcomeSpec]:
    specs = []
    specs.extend(dedicated_sinasc_specs())
    specs.extend(health_specs())
    specs.extend(education_specs())
    specs.extend(adult_eja_specs())
    specs.extend(siconfi_specs())
    specs.extend(school_access_specs())
    seen: set[tuple[str, str, str]] = set()
    deduped: list[OutcomeSpec] = []
    for spec in specs:
        key = (spec.category, spec.frequency, spec.slug)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(spec)
    return deduped


def read_panel_columns(spec: OutcomeSpec) -> list[str]:
    needed = set(BASE_COLUMNS + [spec.time_col])
    if spec.cycle_window:
        needed.add("cycle_window")
    if spec.numerator_col:
        needed.add(spec.numerator_col)
        needed.add(spec.denominator_col or "")
    else:
        needed.add(spec.column)
    existing = parquet_columns(spec.panel_path)
    return [col for col in needed if col and col in existing]


def merge_denominator(sample: pd.DataFrame, spec: OutcomeSpec) -> pd.DataFrame:
    if spec.denominator_panel_path is None:
        return sample
    if spec.denominator_col is None:
        raise ValueError(f"{spec.slug} has denominator_panel_path but no denominator_col.")
    keys = ["municipality_id", spec.time_col]
    if spec.cycle_window:
        keys.append("cycle_window")
    cols = keys + [spec.denominator_col]
    other = pd.read_parquet(spec.denominator_panel_path, columns=cols)
    if spec.cycle_window and "cycle_window" in other.columns:
        other = other.loc[other["cycle_window"].eq(spec.cycle_window)].copy()
    other["municipality_id"] = normalize_municipality_id(other["municipality_id"])
    other = other.drop_duplicates(keys)
    return sample.merge(other, on=keys, how="left", validate="many_to_one")


def build_sample(spec: OutcomeSpec) -> tuple[pd.DataFrame, dict[str, object]]:
    columns = read_panel_columns(spec)
    if spec.column not in columns and spec.numerator_col is None:
        raise KeyError(f"{spec.column} not available in {relative(spec.panel_path)}")
    if spec.numerator_col and spec.numerator_col not in columns:
        raise KeyError(f"{spec.numerator_col} not available in {relative(spec.panel_path)}")

    raw = pd.read_parquet(spec.panel_path, columns=columns)
    raw["municipality_id"] = normalize_municipality_id(raw["municipality_id"])
    raw["period"] = pd.to_numeric(raw[spec.time_col], errors="raise").astype(int)
    if spec.frequency == "biennial":
        raw["period"] = raw["period"] - 1
    if spec.cycle_window and "cycle_window" in raw.columns:
        raw = raw.loc[raw["cycle_window"].eq(spec.cycle_window)].copy()
    raw = raw.loc[raw["period"].between(spec.min_time, spec.max_time)].copy()

    hybrid_units = raw.loc[raw["ever_hybrid_bvr"].fillna(0).eq(1), "municipality_id"].nunique()
    sample = raw.loc[raw["ever_hybrid_bvr"].fillna(0).ne(1)].copy()
    if spec.denominator_panel_path is not None:
        sample = merge_denominator(sample, spec)

    if spec.numerator_col:
        numerator = pd.to_numeric(sample[spec.numerator_col], errors="coerce").astype(float)
        denominator = pd.to_numeric(sample[spec.denominator_col], errors="coerce").astype(float)
        value = numerator / denominator
        sample[spec.analysis_column] = value.where(numerator.ge(0) & denominator.gt(0) & np.isfinite(value))
    elif spec.scale != 1.0:
        sample[spec.analysis_column] = pd.to_numeric(sample[spec.column], errors="coerce") * spec.scale
    else:
        sample[spec.analysis_column] = pd.to_numeric(sample[spec.column], errors="coerce")

    treatment_source = "year_treated_strict" if "year_treated_strict" in sample.columns else "first_strict_bvr_year"
    sample["treatment_year_cs"] = pd.to_numeric(sample[treatment_source], errors="coerce")
    sample["treatment_year_cs"] = sample["treatment_year_cs"].fillna(NEVER_TREATED_VALUE).astype(int)
    sample.loc[sample["treatment_year_cs"].ge(NEVER_TREATED_VALUE), "treatment_year_cs"] = NEVER_TREATED_VALUE
    sample["event_time_cs"] = sample["period"] - sample["treatment_year_cs"]
    sample.loc[sample["treatment_year_cs"].eq(NEVER_TREATED_VALUE), "event_time_cs"] = -9999
    sample = sample.sort_values(["municipality_id", "period"]).reset_index(drop=True)

    keep = [
        "municipality_id",
        "period",
        "treatment_year_cs",
        "event_time_cs",
        "ever_hybrid_bvr",
        spec.analysis_column,
    ]
    sample = sample[keep]
    spec.sample_path.parent.mkdir(parents=True, exist_ok=True)
    sample.to_parquet(spec.sample_path, index=False, engine="pyarrow", compression="zstd")

    observed = sample.loc[sample[spec.analysis_column].notna()].copy()
    units = observed.drop_duplicates("municipality_id")
    diag = {
        "panel_path": relative(spec.panel_path),
        "analysis_sample": relative(spec.sample_path),
        "n_panel_rows": int(len(sample)),
        "n_observations": int(len(observed)),
        "n_municipalities": int(sample["municipality_id"].nunique()),
        "n_municipalities_with_nonmissing_outcome": int(observed["municipality_id"].nunique()),
        "n_treated_municipalities": int(units.loc[units["treatment_year_cs"].ne(NEVER_TREATED_VALUE), "municipality_id"].nunique()),
        "n_never_treated_municipalities": int(units.loc[units["treatment_year_cs"].eq(NEVER_TREATED_VALUE), "municipality_id"].nunique()),
        "sample_year_min": int(observed["period"].min()) if len(observed) else None,
        "sample_year_max": int(observed["period"].max()) if len(observed) else None,
        "hybrid_municipalities_excluded": int(hybrid_units),
        "hybrid_excluded": True,
        "duplicate_unit_period_rows": int(sample.duplicated(["municipality_id", "period"]).sum()),
        "event_time_step": 2 if spec.frequency in {"biennial", "cycle2"} else 1,
        "analysis_period_note": (
            "Biennial assessment years use analysis period = assessment year - 1, "
            "so the first post-BVR assessment is event time 0 and adjacent waves are two-year steps."
            if spec.frequency == "biennial"
            else ""
        ),
    }
    return sample, diag


def write_config(spec: OutcomeSpec) -> None:
    spec.output_dir.mkdir(parents=True, exist_ok=True)
    event_step = 2 if spec.frequency in {"biennial", "cycle2"} else 1
    horizons = list(range(0, LAG + 1, event_step))
    pretrends = list(range(-LEAD, 0, event_step))
    config = {
        "estimator": "bjs",
        "data_path": relative(spec.sample_path),
        "file_format": "parquet",
        "outcome": spec.analysis_column,
        "unit_id": "municipality_id",
        "time_id": "period",
        "group_id": "treatment_year_cs",
        "treatment_var": None,
        "controls": [],
        "cluster_var": ["municipality_id"],
        "weights_var": None,
        "event_time_var": None,
        "lead": LEAD,
        "lag": LAG,
        "reference_event_time": REFERENCE_EVENT_TIME,
        "plot_reference_event_time": REFERENCE_EVENT_TIME,
        "balanced_panel_required": False,
        "never_treated_value": NEVER_TREATED_VALUE,
        "seed": SEED,
        "horizon": horizons,
        "pretrends": pretrends,
        "event_time_step": event_step,
        "output_dir": relative(spec.output_dir),
        "output": {
            "save_csv": True,
            "save_parquet": True,
            "save_json": True,
            "save_yaml_metadata": True,
            "save_model_summary": True,
        },
        "plot": {
            "latex_figure_format": "pdf",
            "save_tight_png": True,
            "save_png": False,
            "omit_title": True,
            "x_label": "Years from strict BVR",
            "y_label": spec.y_label,
            "color": spec.color_value,
            "x_breaks": list(range(-LEAD, LAG + 1, 2)),
            "width": 8,
            "height": 5,
            "dpi": 320,
            "show_grid": True,
            "show_border": True,
            "zero_line": True,
            "reference_line": True,
            "reference_line_type": "dashed",
            "ci_geom": "linerange",
            "show_line": True,
            "show_points": True,
        },
        "notes": (
            "Borusyak-Jaravel-Spiess / imputation DID screen. Strict BVR timing, "
            "nonhybrid sample, municipality-level clustering, horizons -8..8. "
            "Post-processing normalizes the event-study path to event time 0. "
            + (
                "Biennial assessment years use analysis period = assessment year - 1, "
                "so the first post-BVR assessment is event time 0 and adjacent waves are two-year steps. "
                if spec.frequency == "biennial"
                else ""
            )
            + f"{spec.note}"
        ).strip(),
    }
    spec.config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")


def run_estimator(rscript: str, spec: OutcomeSpec, skip_existing: bool) -> tuple[int, str]:
    if skip_existing and (spec.output_dir / "event_study_estimates.csv").exists():
        return 0, "skipped_existing_output"
    if not skip_existing:
        for name in [
            "event_study_estimates.csv",
            "event_study_estimates.parquet",
            "event_study_ref0.csv",
            "event_study_plot.pdf",
            "event_study_plot.png",
            "tidy_estimates.csv",
            "tidy_estimates.parquet",
            "results.json",
            "model_summary.txt",
            "run_metadata.yml",
            "sample_diagnostics.csv",
            "sample_diagnostics.parquet",
        ]:
            (spec.output_dir / name).unlink(missing_ok=True)
    proc = subprocess.run(
        [rscript, str(REG_DID_RUNNER), str(spec.config_path.relative_to(ROOT))],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    log = (proc.stdout or "") + (proc.stderr or "")
    pd.DataFrame(
        [
            {
                "slug": spec.slug,
                "outcome": spec.analysis_column,
                "returncode": proc.returncode,
                "config_path": relative(spec.config_path),
                "output_dir": relative(spec.output_dir),
                "stdout_stderr": log[-16000:],
            }
        ]
    ).to_csv(spec.output_dir / "run_status.csv", index=False)
    return proc.returncode, log


def read_and_normalize_event(spec: OutcomeSpec) -> tuple[pd.DataFrame | None, dict[str, object]]:
    event_path = spec.output_dir / "event_study_estimates.csv"
    if not event_path.exists():
        return None, {"status": "missing_event_study"}
    event = pd.read_csv(event_path)
    if "event_time" not in event.columns or "estimate" not in event.columns:
        return None, {"status": "malformed_event_study"}
    event["event_time"] = pd.to_numeric(event["event_time"], errors="coerce")
    event = event.loc[event["event_time"].between(-LEAD, LAG)].copy()
    if event.empty:
        return None, {"status": "empty_event_study"}
    event["event_time"] = event["event_time"].astype(int)
    for col in ["estimate", "std.error", "conf.low", "conf.high", "statistic", "p.value"]:
        if col in event.columns:
            event[col] = pd.to_numeric(event[col], errors="coerce")
    ref = event.loc[event["event_time"].eq(REFERENCE_EVENT_TIME), "estimate"]
    if ref.empty or pd.isna(ref.iloc[0]):
        return event, {"status": "missing_event_time_0", "event_time0_estimate": None}
    ref_estimate = float(ref.iloc[0])
    event["reference_event_time"] = REFERENCE_EVENT_TIME
    event["event_time0_estimate"] = ref_estimate
    event["estimate_ref0"] = event["estimate"] - ref_estimate
    if "conf.low" in event.columns:
        event["conf.low_ref0"] = event["conf.low"] - ref_estimate
    if "conf.high" in event.columns:
        event["conf.high_ref0"] = event["conf.high"] - ref_estimate
    zero_mask = event["event_time"].eq(REFERENCE_EVENT_TIME)
    for col in ["estimate_ref0", "conf.low_ref0", "conf.high_ref0"]:
        if col in event.columns:
            event.loc[zero_mask, col] = 0.0
    out_path = spec.output_dir / "event_study_ref0.csv"
    event.to_csv(out_path, index=False)
    return event.sort_values("event_time"), {"status": "ok", "event_time0_estimate": ref_estimate}


def summarize_event(spec: OutcomeSpec, event: pd.DataFrame | None, diag: dict[str, object], status: str) -> dict[str, object]:
    row: dict[str, object] = {
        "slug": spec.slug,
        "outcome": spec.column,
        "analysis_outcome": spec.analysis_column,
        "label": spec.label,
        "category": spec.category,
        "category_label": CATEGORY_LABELS.get(spec.category, spec.category),
        "family": spec.family,
        "data_frequency": spec.frequency,
        "panel_path": relative(spec.panel_path),
        "output_dir": relative(spec.output_dir),
        "figure_path": relative(spec.figure_path),
        "hybrid_excluded": True,
        "cluster_var": "municipality_id",
        "reference_event_time": REFERENCE_EVENT_TIME,
        "status": status,
        "note": spec.note,
    }
    row.update(diag)
    if event is None or status != "ok":
        row.setdefault("pretrend_label", "not_estimated")
        return row
    row["event_time0_estimate"] = float(event["event_time0_estimate"].iloc[0])
    post = event.loc[event["event_time"].between(1, LAG) & event["estimate_ref0"].notna()].copy()
    pre = event.loc[event["event_time"].between(-LEAD, -1)].copy()
    pre = pre.loc[pre["std.error"].notna() if "std.error" in pre.columns else []].copy()
    row["post_mean_event_1_8_ref0"] = float(post["estimate_ref0"].mean()) if len(post) else np.nan
    row["post_abs_mean_event_1_8_ref0"] = abs(row["post_mean_event_1_8_ref0"]) if pd.notna(row["post_mean_event_1_8_ref0"]) else np.nan
    if len(pre):
        if "statistic" in pre.columns and pre["statistic"].notna().any():
            abs_t = pre["statistic"].abs()
        else:
            abs_t = (pre["estimate"] / pre["std.error"]).abs()
        row["n_pre_estimates"] = int(len(pre))
        row["max_abs_pretrend_t"] = float(abs_t.max(skipna=True))
        row["n_pre_p05"] = int((pre["p.value"] < 0.05).sum()) if "p.value" in pre.columns else np.nan
        if row["n_pre_estimates"] >= 3 and row["n_pre_p05"] == 0 and row["max_abs_pretrend_t"] <= 1.96:
            row["pretrend_label"] = "pass"
        elif row["n_pre_estimates"] >= 2 and row["n_pre_p05"] <= 1 and row["max_abs_pretrend_t"] <= 2.58:
            row["pretrend_label"] = "near"
        else:
            row["pretrend_label"] = "fail"
    else:
        row["n_pre_estimates"] = 0
        row["max_abs_pretrend_t"] = np.nan
        row["n_pre_p05"] = np.nan
        row["pretrend_label"] = "insufficient"
    row["n_post_estimates"] = int(len(post))
    return row


def finite_limits(values: pd.Series, min_abs: float = 0.05) -> tuple[float, float]:
    vals = pd.to_numeric(values, errors="coerce")
    vals = vals[np.isfinite(vals)]
    if vals.empty:
        return -min_abs, min_abs
    span = max(abs(float(vals.min())), abs(float(vals.max())), min_abs)
    span = math.ceil(span * 20) / 20
    return -span, span


def write_individual_plot(spec: OutcomeSpec, event: pd.DataFrame, summary: dict[str, object]) -> None:
    spec.figure_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(7.4, 4.6))
    ci = event.loc[event.get("conf.low_ref0", pd.Series(index=event.index)).notna()].copy()
    ax.axhline(0, color="0.25", linewidth=1.0)
    ax.axvline(REFERENCE_EVENT_TIME, color="0.55", linestyle="--", linewidth=0.9)
    if not ci.empty:
        ax.vlines(ci["event_time"], ci["conf.low_ref0"], ci["conf.high_ref0"], color=spec.color_value, linewidth=1.0)
    ax.plot(event["event_time"], event["estimate_ref0"], color=spec.color_value, linewidth=1.4)
    ax.scatter(event["event_time"], event["estimate_ref0"], color=spec.color_value, s=24, zorder=3)
    ax.set_xlim(-LEAD - 0.5, LAG + 0.5)
    ax.set_xticks(list(range(-LEAD, LAG + 1, 2)))
    limits_source = pd.concat(
        [
            event["estimate_ref0"],
            event.get("conf.low_ref0", pd.Series(dtype=float)),
            event.get("conf.high_ref0", pd.Series(dtype=float)),
        ],
        ignore_index=True,
    )
    ymin, ymax = finite_limits(limits_source)
    ax.set_ylim(ymin, ymax)
    ax.set_xlabel("Years from strict BVR")
    ax.set_ylabel(f"{spec.y_label}, normalized to event time 0")
    pre = summary.get("pretrend_label", "")
    post = summary.get("post_mean_event_1_8_ref0", np.nan)
    post_txt = "NA" if pd.isna(post) else f"{post:.3g}"
    ax.set_title(f"{spec.label}\npost mean e1..e8={post_txt}, pre={pre}", fontsize=9.5)
    ax.grid(True, alpha=0.23)
    for spine in ax.spines.values():
        spine.set_visible(True)
        spine.set_linewidth(0.8)
    fig.tight_layout()
    fig.savefig(spec.figure_path, dpi=320)
    fig.savefig(spec.figure_path.with_suffix(".pdf"))
    plt.close(fig)


def write_combined_plots(results: pd.DataFrame, events: pd.DataFrame) -> list[str]:
    paths: list[str] = []
    if results.empty or events.empty:
        return paths
    FIGURE_ROOT.mkdir(parents=True, exist_ok=True)
    pre_rank = {"pass": 0, "near": 1, "insufficient": 2, "fail": 3}
    ok = results.loc[results["status"].eq("ok")].copy()
    ok["pretrend_rank"] = ok["pretrend_label"].map(pre_rank).fillna(9)
    ok["post_abs"] = pd.to_numeric(ok["post_abs_mean_event_1_8_ref0"], errors="coerce").fillna(-1)
    for category in CATEGORY_LABELS:
        sub = ok.loc[ok["category"].eq(category)].copy()
        if sub.empty:
            continue
        sub = sub.sort_values(["pretrend_rank", "post_abs"], ascending=[True, False]).head(12)
        ncols = 3 if len(sub) > 4 else 2
        nrows = math.ceil(len(sub) / ncols)
        fig, axes = plt.subplots(nrows, ncols, figsize=(4.9 * ncols, 3.15 * nrows), squeeze=False)
        for ax in axes.ravel():
            ax.axis("off")
        for ax, (_, row) in zip(axes.ravel(), sub.iterrows()):
            ev = events.loc[events["slug"].eq(row["slug"])].sort_values("event_time")
            if ev.empty:
                continue
            ax.axis("on")
            color = COLORS.get(category, "#2C5A8A")
            ci = ev.loc[ev["conf.low_ref0"].notna() if "conf.low_ref0" in ev.columns else []]
            ax.axhline(0, color="0.25", linewidth=0.9)
            ax.axvline(0, color="0.55", linestyle="--", linewidth=0.8)
            if not ci.empty:
                ax.vlines(ci["event_time"], ci["conf.low_ref0"], ci["conf.high_ref0"], color=color, linewidth=0.85)
            ax.plot(ev["event_time"], ev["estimate_ref0"], color=color, linewidth=1.1)
            ax.scatter(ev["event_time"], ev["estimate_ref0"], color=color, s=18, zorder=3)
            ax.set_xlim(-LEAD - 0.5, LAG + 0.5)
            ax.set_xticks(list(range(-LEAD, LAG + 1, 4)))
            ax.set_title(
                f"{str(row['label'])[:60]}\npost={row['post_mean_event_1_8_ref0']:.3g}, pre={row['pretrend_label']}",
                fontsize=8.6,
            )
            ax.grid(True, alpha=0.2)
        fig.suptitle(f"BJS ref-0 screen: {CATEGORY_LABELS[category]}", fontsize=12)
        fig.tight_layout()
        out = FIGURE_ROOT / f"{category}_combined_bjs_ref0_nonhybrid.png"
        fig.savefig(out, dpi=320)
        fig.savefig(out.with_suffix(".pdf"))
        plt.close(fig)
        paths.extend([relative(out), relative(out.with_suffix(".pdf"))])
    return paths


def write_all_outcome_plot_pages(results: pd.DataFrame, events: pd.DataFrame) -> list[str]:
    paths: list[str] = []
    if results.empty or events.empty:
        return paths
    FIGURE_ROOT.mkdir(parents=True, exist_ok=True)
    ok = results.loc[results["status"].eq("ok")].copy()
    ok["post_abs"] = pd.to_numeric(ok["post_abs_mean_event_1_8_ref0"], errors="coerce").fillna(-1)
    ok = ok.sort_values(["category", "family", "data_frequency", "label"])
    per_page = 12
    for category in CATEGORY_LABELS:
        sub = ok.loc[ok["category"].eq(category)].copy()
        if sub.empty:
            continue
        for page_idx, start in enumerate(range(0, len(sub), per_page), start=1):
            page = sub.iloc[start : start + per_page].copy()
            ncols = 3 if len(page) > 4 else 2
            nrows = math.ceil(len(page) / ncols)
            fig, axes = plt.subplots(nrows, ncols, figsize=(4.9 * ncols, 3.15 * nrows), squeeze=False)
            for ax in axes.ravel():
                ax.axis("off")
            for ax, (_, row) in zip(axes.ravel(), page.iterrows()):
                ev = events.loc[events["slug"].eq(row["slug"])].sort_values("event_time")
                if ev.empty:
                    continue
                ax.axis("on")
                color = COLORS.get(category, "#2C5A8A")
                ci = ev.loc[ev["conf.low_ref0"].notna() if "conf.low_ref0" in ev.columns else []]
                ax.axhline(0, color="0.25", linewidth=0.9)
                ax.axvline(0, color="0.55", linestyle="--", linewidth=0.8)
                if not ci.empty:
                    ax.vlines(ci["event_time"], ci["conf.low_ref0"], ci["conf.high_ref0"], color=color, linewidth=0.85)
                ax.plot(ev["event_time"], ev["estimate_ref0"], color=color, linewidth=1.1)
                ax.scatter(ev["event_time"], ev["estimate_ref0"], color=color, s=18, zorder=3)
                ax.set_xlim(-LEAD - 0.5, LAG + 0.5)
                ax.set_xticks(list(range(-LEAD, LAG + 1, 4)))
                ax.set_title(
                    f"{str(row['label'])[:60]}\npost={row['post_mean_event_1_8_ref0']:.3g}, pre={row['pretrend_label']}",
                    fontsize=8.6,
                )
                ax.grid(True, alpha=0.2)
            total_pages = math.ceil(len(sub) / per_page)
            fig.suptitle(
                f"BJS ref-0 screen: {CATEGORY_LABELS[category]} ({page_idx}/{total_pages})",
                fontsize=12,
            )
            fig.tight_layout()
            out = FIGURE_ROOT / f"{category}_all_bjs_ref0_nonhybrid_page_{page_idx:02d}.png"
            fig.savefig(out, dpi=320)
            fig.savefig(out.with_suffix(".pdf"))
            plt.close(fig)
            paths.extend([relative(out), relative(out.with_suffix(".pdf"))])
    return paths


def select_specs(args: argparse.Namespace) -> list[OutcomeSpec]:
    specs = all_specs()
    if args.category:
        wanted = set(args.category)
        specs = [spec for spec in specs if spec.category in wanted]
    if args.family:
        wanted = set(args.family)
        specs = [spec for spec in specs if spec.family in wanted]
    if args.slug:
        wanted = set(args.slug)
        specs = [spec for spec in specs if spec.slug in wanted]
    if args.limit:
        specs = specs[: args.limit]
    return specs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--category", action="append", choices=sorted(CATEGORY_LABELS), help="Restrict to one combined category.")
    parser.add_argument("--family", action="append", help="Restrict to one family/subfolder.")
    parser.add_argument("--slug", action="append", help="Run one or more outcome slugs.")
    parser.add_argument("--limit", type=int, help="Run only the first N selected specs.")
    parser.add_argument("--skip-existing", action="store_true", help="Skip outcomes with existing event_study_estimates.csv.")
    parser.add_argument("--skip-estimator", action="store_true", help="Build samples/configs and summarize existing outputs only.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    for path in [INTERIM_ROOT, OUTPUT_ROOT, FIGURE_ROOT, TABLE_ROOT]:
        path.mkdir(parents=True, exist_ok=True)
    selected = select_specs(args)
    if not selected:
        raise RuntimeError("No outcome specs selected.")
    rscript = find_rscript()
    rows: list[dict[str, object]] = []
    event_frames: list[pd.DataFrame] = []
    for i, spec in enumerate(selected, start=1):
        print(f"[{i}/{len(selected)}] {spec.category}/{spec.frequency}/{spec.slug}", flush=True)
        try:
            _sample, diag = build_sample(spec)
            if diag["duplicate_unit_period_rows"]:
                raise RuntimeError(f"Duplicate municipality-period rows: {diag['duplicate_unit_period_rows']}")
            if diag["n_observations"] == 0:
                row = summarize_event(spec, None, diag, "all_missing")
                rows.append(row)
                continue
            write_config(spec)
            returncode = 0
            if not args.skip_estimator:
                returncode, _log = run_estimator(rscript, spec, args.skip_existing)
            elif not (spec.output_dir / "event_study_estimates.csv").exists():
                returncode = 999
            if returncode != 0:
                row = summarize_event(spec, None, diag, "estimator_failed")
                row["returncode"] = returncode
                rows.append(row)
                continue
            event, event_status = read_and_normalize_event(spec)
            row = summarize_event(spec, event, diag, str(event_status.get("status", "unknown")))
            row.update(event_status)
            rows.append(row)
            if event is not None and row["status"] == "ok":
                event = event.copy()
                event.insert(0, "slug", spec.slug)
                event.insert(1, "label", spec.label)
                event.insert(2, "category", spec.category)
                event.insert(3, "family", spec.family)
                event.insert(4, "data_frequency", spec.frequency)
                event_frames.append(event)
                write_individual_plot(spec, event, row)
        except Exception as exc:  # noqa: BLE001 - screen should continue and report failed outcomes.
            rows.append(
                {
                    "slug": spec.slug,
                    "outcome": spec.column,
                    "analysis_outcome": spec.analysis_column,
                    "label": spec.label,
                    "category": spec.category,
                    "category_label": CATEGORY_LABELS.get(spec.category, spec.category),
                    "family": spec.family,
                    "data_frequency": spec.frequency,
                    "panel_path": relative(spec.panel_path),
                    "output_dir": relative(spec.output_dir),
                    "hybrid_excluded": True,
                    "cluster_var": "municipality_id",
                    "reference_event_time": REFERENCE_EVENT_TIME,
                    "status": "setup_failed",
                    "error": str(exc),
                    "note": spec.note,
                }
            )
    results = pd.DataFrame(rows)
    if not results.empty:
        pre_rank = {"pass": 0, "near": 1, "insufficient": 2, "fail": 3, "not_estimated": 4}
        results["pretrend_rank"] = results["pretrend_label"].map(pre_rank).fillna(9) if "pretrend_label" in results else 9
        results["post_abs_rank_value"] = pd.to_numeric(results.get("post_abs_mean_event_1_8_ref0"), errors="coerce")
        results = results.sort_values(["status", "pretrend_rank", "post_abs_rank_value"], ascending=[True, True, False])
        results.to_csv(TABLE_ROOT / "master_bjs_ref0_nonhybrid_ranking.csv", index=False)
    events = pd.concat(event_frames, ignore_index=True) if event_frames else pd.DataFrame()
    if not events.empty:
        events.to_csv(TABLE_ROOT / "master_bjs_ref0_nonhybrid_event_study.csv", index=False)
    combined_paths = write_combined_plots(results, events)
    all_plot_pages = write_all_outcome_plot_pages(results, events)
    summary = {
        "n_selected": len(selected),
        "n_ok": int(results["status"].eq("ok").sum()) if not results.empty else 0,
        "n_failed": int((~results["status"].eq("ok")).sum()) if not results.empty else 0,
        "master_ranking": relative(TABLE_ROOT / "master_bjs_ref0_nonhybrid_ranking.csv"),
        "master_event_study": relative(TABLE_ROOT / "master_bjs_ref0_nonhybrid_event_study.csv"),
        "combined_plots": combined_paths,
        "all_outcome_plot_pages": all_plot_pages,
        "output_root": relative(OUTPUT_ROOT),
        "figure_root": relative(FIGURE_ROOT),
        "interim_root": relative(INTERIM_ROOT),
    }
    (TABLE_ROOT / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
