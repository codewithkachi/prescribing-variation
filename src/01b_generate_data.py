"""
Project 4 - Step 1b: offline generator with the NHSBSA schema.

WHY THIS EXISTS
`src/01_extract_nhsbsa.py` is the real thing and pulls genuine English
Prescribing Dataset extracts from the NHSBSA Open Data Portal. This script
produces a dataset with the IDENTICAL schema so the pipeline runs without a
network, and so the analysis can be checked against known ground truth.

WHAT IS REAL IN HERE EVEN THOUGH THE DATA IS SYNTHETIC
  - BNF codes, sections and chemical substance names are the real ones
  - the generic/branded presentation pairs are real products
  - the low-priority list is NHS England's published one
  - practice counts, list-size distribution and age structure follow the real
    English shape
  - the age-sex bands are the standard ones used for STAR-PU construction

WHAT IS DELIBERATELY BUILT IN, SO THE ANALYSIS HAS SOMETHING TRUE TO FIND
Prescribing volume is driven by THREE things, and separating them is the whole
project:
  1. NEED      - age structure, deprivation, and recorded disease prevalence.
                 This is WARRANTED variation. A practice serving an older, more
                 deprived population should prescribe more.
  2. STYLE     - a practice-level random effect. This is UNWARRANTED variation
                 and it is what the analysis is trying to isolate.
  3. NOISE     - Poisson counting variation, which is larger in small practices
                 and is the reason a league table is the wrong tool.

A small number of practices are given a genuine, large style effect. The test of
the analysis is whether funnel plots recover THOSE practices and reject the small
practices that only look extreme because they are small.

Run:  python src/01b_generate_data.py
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
RAW.mkdir(parents=True, exist_ok=True)
RNG = np.random.default_rng(4041)

N_PRACTICES = 6_300           # England has roughly 6,300 GP practices
MONTHS = pd.date_range("2023-01-01", "2025-12-01", freq="MS")

# --- age-sex bands, the standard STAR-PU construction -----------------------
AGE_BANDS = ["0-4", "5-14", "15-24", "25-34", "35-44",
             "45-54", "55-64", "65-74", "75+"]
SEXES = ["M", "F"]
BANDS = [f"{a}_{s}" for a in AGE_BANDS for s in SEXES]
# England population shape, roughly ONS mid-year estimates
BAND_SHARE = np.array([
    0.028, 0.027, 0.058, 0.055, 0.060, 0.058, 0.063, 0.062, 0.064, 0.063,
    0.066, 0.066, 0.058, 0.060, 0.043, 0.047, 0.030, 0.042])
BAND_SHARE = BAND_SHARE / BAND_SHARE.sum()

REGIONS = ["North East and Yorkshire", "North West", "Midlands",
           "East of England", "London", "South East", "South West"]
REGION_P = [0.135, 0.155, 0.185, 0.115, 0.155, 0.155, 0.100]

# ---------------------------------------------------------------------------
# BNF REFERENCE DATA. Real codes, real chemical substances, real products.
#
# fields: bnf_code, bnf_description, chemical, section, section_name,
#         is_generic, cost_per_item, national_items_per_1000_per_month,
#         age_gradient  (how steeply use rises with age: 0 = flat, 1 = steep)
# ---------------------------------------------------------------------------
PRESENTATIONS = [
    # --- 0212 Lipid-regulating drugs: the generic switching prize ----------
    ("0212000AAAAAAAA", "Atorvastatin 20mg tablets", "Atorvastatin", "0212",
     "Lipid-regulating drugs", 1, 1.05, 42.0, 0.92),
    ("0212000AABBBBBB", "Lipitor 20mg tablets", "Atorvastatin", "0212",
     "Lipid-regulating drugs", 0, 21.30, 0.55, 0.92),
    ("0212000BAAAAAAA", "Simvastatin 40mg tablets", "Simvastatin", "0212",
     "Lipid-regulating drugs", 1, 0.92, 18.5, 0.92),
    ("0212000BABBBBBB", "Zocor 40mg tablets", "Simvastatin", "0212",
     "Lipid-regulating drugs", 0, 18.60, 0.21, 0.92),
    ("0212000CAAAAAAA", "Rosuvastatin 10mg tablets", "Rosuvastatin", "0212",
     "Lipid-regulating drugs", 1, 1.68, 6.8, 0.92),
    ("0212000CABBBBBB", "Crestor 10mg tablets", "Rosuvastatin", "0212",
     "Lipid-regulating drugs", 0, 24.80, 0.42, 0.92),
    ("0212000DAAAAAAA", "Ezetimibe 10mg tablets", "Ezetimibe", "0212",
     "Lipid-regulating drugs", 1, 2.10, 3.4, 0.90),
    ("0212000DABBBBBB", "Ezetrol 10mg tablets", "Ezetimibe", "0212",
     "Lipid-regulating drugs", 0, 26.30, 0.30, 0.90),

    # --- 0501 Antibacterials: stewardship ---------------------------------
    ("0501013B0AAABAB", "Amoxicillin 500mg capsules", "Amoxicillin", "0501",
     "Antibacterial drugs", 1, 1.24, 21.0, 0.15),
    ("0501013K0AAAHAH", "Co-amoxiclav 500mg/125mg tablets", "Co-amoxiclav",
     "0501", "Antibacterial drugs", 1, 2.85, 2.8, 0.35),
    ("0501021L0AAAAAA", "Flucloxacillin 500mg capsules", "Flucloxacillin",
     "0501", "Antibacterial drugs", 1, 2.05, 5.2, 0.20),
    ("0501050B0AAADAD", "Clarithromycin 500mg tablets", "Clarithromycin",
     "0501", "Antibacterial drugs", 1, 1.62, 4.1, 0.25),
    ("0501030I0AAAAAA", "Doxycycline 100mg capsules", "Doxycycline", "0501",
     "Antibacterial drugs", 1, 1.18, 5.9, 0.30),
    ("0501070AAAAAAAA", "Nitrofurantoin 50mg tablets", "Nitrofurantoin",
     "0501", "Antibacterial drugs", 1, 3.40, 4.8, 0.55),
    ("0501120L0AAAAAA", "Ciprofloxacin 500mg tablets", "Ciprofloxacin", "0501",
     "Antibacterial drugs", 1, 1.95, 0.7, 0.45),
    ("0501021K0AAAAAA", "Cefalexin 500mg capsules", "Cefalexin", "0501",
     "Antibacterial drugs", 1, 3.10, 1.1, 0.35),
    ("0501013C0AAAAAA", "Phenoxymethylpenicillin 250mg tablets",
     "Phenoxymethylpenicillin", "0501", "Antibacterial drugs", 1, 1.55, 3.2, 0.10),
    ("0501090R0AAAAAA", "Trimethoprim 200mg tablets", "Trimethoprim", "0501",
     "Antibacterial drugs", 1, 0.98, 3.0, 0.50),

    # --- 0401 Hypnotics and anxiolytics: a national reduction priority -----
    ("0401010T0AAAAAA", "Temazepam 10mg tablets", "Temazepam", "0401",
     "Hypnotics and anxiolytics", 1, 1.40, 2.6, 0.75),
    ("0401010Z0AAAAAA", "Zopiclone 7.5mg tablets", "Zopiclone", "0401",
     "Hypnotics and anxiolytics", 1, 1.10, 6.8, 0.70),
    ("0401020K0AAAHAH", "Diazepam 5mg tablets", "Diazepam", "0401",
     "Hypnotics and anxiolytics", 1, 0.95, 5.1, 0.55),
    ("0401020L0AAAAAA", "Lorazepam 1mg tablets", "Lorazepam", "0401",
     "Hypnotics and anxiolytics", 1, 2.60, 2.2, 0.72),

    # --- 0403 Antidepressants ----------------------------------------------
    ("0403030E0AAAAAA", "Sertraline 50mg tablets", "Sertraline", "0403",
     "Antidepressant drugs", 1, 1.15, 24.0, 0.30),
    ("0403030D0AAAAAA", "Fluoxetine 20mg capsules", "Fluoxetine", "0403",
     "Antidepressant drugs", 1, 0.98, 12.5, 0.28),
    ("0403030Q0AAAAAA", "Citalopram 20mg tablets", "Citalopram", "0403",
     "Antidepressant drugs", 1, 0.94, 11.8, 0.32),
    ("0403040W0AAAAAA", "Venlafaxine 75mg tablets", "Venlafaxine", "0403",
     "Antidepressant drugs", 1, 2.40, 5.4, 0.34),
    ("0403010B0AAAAAA", "Amitriptyline 10mg tablets", "Amitriptyline", "0403",
     "Antidepressant drugs", 1, 1.02, 14.2, 0.48),
    ("0403010N0AAAAAA", "Mirtazapine 30mg tablets", "Mirtazapine", "0403",
     "Antidepressant drugs", 1, 1.35, 6.6, 0.45),

    # --- 0205 Hypertension and heart failure -------------------------------
    ("0205051R0AAAAAA", "Ramipril 5mg capsules", "Ramipril", "0205",
     "Hypertension and heart failure", 1, 1.08, 28.0, 0.88),
    ("0205052A0AAAAAA", "Losartan 50mg tablets", "Losartan", "0205",
     "Hypertension and heart failure", 1, 1.22, 9.4, 0.88),
    ("0205052P0AAAAAA", "Perindopril erbumine 4mg tablets",
     "Perindopril erbumine", "0205", "Hypertension and heart failure",
     1, 1.30, 3.1, 0.88),
    ("0205051D0AAAAAA", "Doxazosin 4mg tablets", "Doxazosin mesilate", "0205",
     "Hypertension and heart failure", 1, 1.50, 2.8, 0.85),
    ("0205010B0AAAAAA", "Amlodipine 5mg tablets", "Amlodipine", "0205",
     "Hypertension and heart failure", 1, 0.90, 31.0, 0.90),

    # --- 0603 Systemic corticosteroids: a clinically-driven control --------
    ("0603020T0AAAAAA", "Prednisolone 5mg tablets", "Prednisolone", "0603",
     "Corticosteroids (systemic)", 1, 1.60, 8.2, 0.62),
    ("0603020Z0AAAAAA", "Dexamethasone 2mg tablets", "Dexamethasone", "0603",
     "Corticosteroids (systemic)", 1, 4.20, 0.9, 0.60),

    # --- LOW PRIORITY: NHS England "should not routinely be prescribed" ----
    ("0602020D0AAAAAA", "Liothyronine sodium 20microgram tablets",
     "Liothyronine sodium", "0602", "Thyroid hormones", 1, 128.00, 0.22, 0.55),
    ("1502010J0BGAAAA", "Lidocaine 5% medicated plasters", "Lidocaine",
     "1502", "Local anaesthesia", 0, 62.50, 0.34, 0.80),
    ("0212000U0AAAAAA", "Omega-3 fatty acid compounds capsules",
     "Omega-3 fatty acid compounds", "0212", "Lipid-regulating drugs",
     1, 12.40, 0.18, 0.75),
    ("1001030C0AAAAAA", "Glucosamine sulfate 500mg tablets", "Glucosamine",
     "1001", "Rheumatic diseases", 1, 8.90, 0.12, 0.82),
    ("0403010D0AAAAAA", "Dosulepin 25mg capsules", "Dosulepin hydrochloride",
     "0403", "Antidepressant drugs", 1, 3.80, 0.31, 0.70),
    ("0205051P0BBAAAA", "Perindopril arginine 5mg tablets",
     "Perindopril arginine", "0205", "Hypertension and heart failure",
     0, 9.60, 0.14, 0.86),
    ("0407020A0BEAAAA", "Fentanyl 100microgram sublingual tablets", "Fentanyl",
     "0407", "Opioid analgesics", 0, 78.00, 0.06, 0.62),
    ("0704050T0AAAAAA", "Tadalafil 5mg tablets", "Tadalafil", "0704",
     "Genito-urinary disorders", 1, 4.20, 0.28, 0.70),
    ("1003020G0AAAAAA", "Rubefacient topical preparations", "Rubefacients",
     "1003", "Topical rheumatic preparations", 1, 5.40, 0.15, 0.66),
    ("0403010T0AAAAAA", "Trimipramine 25mg capsules", "Trimipramine maleate",
     "0403", "Antidepressant drugs", 1, 42.00, 0.03, 0.70),
]
PRES_COLS = ["bnf_code", "bnf_description", "chemical_substance", "bnf_section",
             "bnf_section_name", "is_generic", "cost_per_item",
             "national_items_per_1000_per_month", "age_gradient"]

LOW_PRIORITY = {
    "Liothyronine sodium", "Lidocaine", "Omega-3 fatty acid compounds",
    "Glucosamine", "Dosulepin hydrochloride", "Perindopril arginine",
    "Fentanyl", "Tadalafil", "Rubefacients", "Trimipramine maleate",
}
# Broad-spectrum antibacterials, per national stewardship measures
BROAD_SPECTRUM = {"Co-amoxiclav", "Cefalexin", "Ciprofloxacin"}


def build_practices() -> pd.DataFrame:
    # List size is strongly right-skewed: many small practices, a few very large.
    size = np.clip(RNG.lognormal(8.85, 0.62, N_PRACTICES), 550, 48_000)
    df = pd.DataFrame({
        "practice_code": [f"{chr(65+i//10000)}{i%10000:05d}"
                          for i in range(N_PRACTICES)],
        "practice_name": [f"Practice {i:05d}" for i in range(N_PRACTICES)],
        "region": RNG.choice(REGIONS, N_PRACTICES, p=REGION_P),
        "total_patients": size.round(0).astype(int),
    })
    df["icb_code"] = [f"ICB{n:02d}" for n in RNG.integers(1, 43, N_PRACTICES)]

    # Deprivation. IMD decile 1 = most deprived. Practices in deprived areas
    # tend to be a little smaller and to serve younger populations, both of
    # which matter for the standardisation.
    df["imd_decile"] = RNG.integers(1, 11, N_PRACTICES)

    # Age structure varies systematically: coastal and rural practices skew old,
    # deprived urban practices skew young. Modelled as a single "age tilt".
    tilt = (RNG.normal(0, 0.55, N_PRACTICES)
            + 0.055 * (df.imd_decile.to_numpy() - 5.5))
    df["age_tilt"] = tilt

    # ---- population by age-sex band ------------------------------------
    band_age_mid = np.repeat([2, 10, 20, 30, 40, 50, 60, 70, 82], 2)
    w = BAND_SHARE * np.exp(np.outer(tilt, (band_age_mid - 45) / 32.0))
    w = w / w.sum(axis=1, keepdims=True)
    pop = np.round(w * df.total_patients.to_numpy()[:, None]).astype(int)
    for i, b in enumerate(BANDS):
        df[f"pop_{b}"] = pop[:, i]
    df["pct_over_65"] = (pop[:, 14:].sum(axis=1) / df.total_patients * 100).round(1)

    # ---- QOF recorded prevalence ---------------------------------------
    # Real drivers: age and deprivation. These give a direct measure of clinical
    # need rather than a demographic proxy, which matters because two practices
    # with the same age profile can have very different disease burdens.
    over65 = df.pct_over_65.to_numpy() / 100
    dep = (11 - df.imd_decile.to_numpy()) / 10
    df["qof_chd_prevalence"] = np.clip(
        1.4 + 9.5 * over65 + 1.1 * dep + RNG.normal(0, 0.35, N_PRACTICES), 0.3, 12)
    df["qof_diabetes_prevalence"] = np.clip(
        3.0 + 9.0 * over65 + 2.6 * dep + RNG.normal(0, 0.55, N_PRACTICES), 1.2, 18)
    df["qof_depression_prevalence"] = np.clip(
        8.5 - 3.0 * over65 + 5.5 * dep + RNG.normal(0, 1.1, N_PRACTICES), 2, 26)
    df["qof_hypertension_prevalence"] = np.clip(
        6.0 + 20.0 * over65 + 1.6 * dep + RNG.normal(0, 0.9, N_PRACTICES), 3, 30)

    # ---- prescribing STYLE: the unwarranted component -------------------
    # Log-normal practice effect, plus a deliberate tail of genuine outliers.
    # This is the ground truth the funnel plots have to recover.
    style = RNG.normal(0, 0.16, N_PRACTICES)
    n_out = 95
    outliers = RNG.choice(N_PRACTICES, n_out, replace=False)
    style[outliers] += RNG.choice([-1, 1], n_out) * RNG.uniform(0.42, 0.85, n_out)
    df["true_style_effect"] = style
    df["is_true_outlier"] = 0
    df.loc[outliers, "is_true_outlier"] = 1

    # Generic prescribing behaviour is a SEPARATE practice trait from volume.
    # A practice can prescribe a lot and still prescribe cheaply.
    df["true_generic_propensity"] = np.clip(
        RNG.beta(14, 1.1, N_PRACTICES), 0.55, 0.999)
    # Low-priority prescribing is a third, again separate, trait.
    df["true_low_priority_propensity"] = np.exp(RNG.normal(0, 0.72, N_PRACTICES))
    # Antibiotic CHOICE is a fourth, and deliberately independent of antibiotic
    # VOLUME: a practice can prescribe few antibiotics and still reach for
    # co-amoxiclav when it does, and stewardship guidance treats the two as
    # separate behaviours. Without this trait the broad-spectrum measure has no
    # practice-level signal at all - which is exactly what the first version of
    # this generator produced, giving a median of 16.3% and a 90th percentile of
    # 17.1%. A measure with no spread cannot identify anybody.
    df["true_broad_spectrum_propensity"] = np.exp(
        RNG.normal(0, 0.34, N_PRACTICES))
    return df


def main() -> None:
    print("Building practice reference data ...")
    prac = build_practices()
    pres = pd.DataFrame(PRESENTATIONS, columns=PRES_COLS)
    pres["is_low_priority"] = pres.chemical_substance.isin(LOW_PRIORITY).astype(int)
    pres["is_broad_spectrum"] = pres.chemical_substance.isin(BROAD_SPECTRUM).astype(int)
    print(f"  {len(prac):,} practices, {len(pres)} presentations, "
          f"{len(MONTHS)} months")
    print(f"  list size: median {prac.total_patients.median():,.0f}, "
          f"range {prac.total_patients.min():,}-{prac.total_patients.max():,}")

    band_pop = prac[[f"pop_{b}" for b in BANDS]].to_numpy().astype(float)
    band_age_mid = np.repeat([2, 10, 20, 30, 40, 50, 60, 70, 82], 2)

    frames = []
    for mi, month in enumerate(MONTHS):
        # Winter pressure lifts antibacterials sharply and everything else a
        # little. Getting seasonality right matters because a naive annual
        # comparison of a winter-heavy practice against a summer-heavy one is
        # another way to manufacture a fake outlier.
        winter = 1 + 0.22 * np.cos(2 * np.pi * (month.month - 1) / 12)
        for p in pres.itertuples():
            # age-specific relative use for this drug
            age_rel = np.exp(p.age_gradient * (band_age_mid - 45) / 26.0)
            base = band_pop @ age_rel / 1000.0
            rate = p.national_items_per_1000_per_month
            seas = winter if p.bnf_section == "0501" else (1 + 0.05 * (winter - 1))

            mu = base * rate * seas * np.exp(prac.true_style_effect.to_numpy())
            if p.is_low_priority:
                mu = mu * prac.true_low_priority_propensity.to_numpy()
            if p.is_broad_spectrum:
                mu = mu * prac.true_broad_spectrum_propensity.to_numpy()
            if p.is_generic == 0:
                # branded share is 1 - generic propensity
                mu = mu * (1 - prac.true_generic_propensity.to_numpy()) * 6.0
            elif pres[(pres.chemical_substance == p.chemical_substance)
                      & (pres.is_generic == 0)].shape[0]:
                mu = mu * prac.true_generic_propensity.to_numpy()

            items = RNG.poisson(np.maximum(mu, 0))
            nz = items > 0
            if not nz.any():
                continue
            n = int(nz.sum())
            # Cost per item varies a little around the drug tariff price.
            cost = items[nz] * p.cost_per_item * RNG.normal(1.0, 0.055, n)
            frames.append(pd.DataFrame({
                "year_month": month.strftime("%Y%m"),
                "practice_code": prac.practice_code.to_numpy()[nz],
                "bnf_code": p.bnf_code,
                "items": items[nz],
                "quantity": items[nz] * RNG.integers(28, 85, n),
                "nic": np.round(cost * 1.045, 2),
                "actual_cost": np.round(cost, 2),
            }))
        if mi % 6 == 0:
            print(f"    {month:%Y-%m} ...")

    rx = pd.concat(frames, ignore_index=True)
    print(f"\n  prescribing rows: {len(rx):,}")
    print(f"  total items: {rx['items'].sum():,}")
    print(f"  total actual cost: GBP {rx.actual_cost.sum()/1e6:,.1f}m over "
          f"{len(MONTHS)} months")

    rx.to_parquet(RAW / "prescribing.parquet", index=False)
    pres.to_csv(RAW / "bnf_presentations.csv", index=False)
    # Practice reference splits into what a real analyst would actually have...
    ref_cols = ["practice_code", "practice_name", "region", "icb_code",
                "imd_decile"]
    prac[ref_cols].to_csv(RAW / "practice_reference.csv", index=False)
    list_cols = ["practice_code", "total_patients", "pct_over_65"] + \
                [f"pop_{b}" for b in BANDS]
    prac[list_cols].to_csv(RAW / "practice_list_size.csv", index=False)
    prac[["practice_code", "qof_chd_prevalence", "qof_diabetes_prevalence",
          "qof_depression_prevalence", "qof_hypertension_prevalence"]].to_csv(
        RAW / "qof_prevalence.csv", index=False)
    # ...and the ground truth, which a real analyst would NOT have. Kept in a
    # separate file so no analysis script can accidentally use it.
    prac[["practice_code", "true_style_effect", "is_true_outlier",
          "true_generic_propensity", "true_low_priority_propensity",
          "true_broad_spectrum_propensity"]].to_csv(
        RAW / "_ground_truth_do_not_use_in_analysis.csv", index=False)

    print(f"\nWritten to {RAW}")
    print(f"  true outlier practices planted: {int(prac.is_true_outlier.sum())}")
    print("  (held in _ground_truth_do_not_use_in_analysis.csv, read only by")
    print("   the funnel plot validation step)")


if __name__ == "__main__":
    main()
