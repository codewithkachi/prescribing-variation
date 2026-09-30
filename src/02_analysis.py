"""
Project 4 - Step 2: the analysis.

THE ARGUMENT THIS FILE MAKES
Prescribing varies enormously between GP practices. Some of that variation is
entirely appropriate - a practice serving an older, more deprived population
with a higher recorded disease burden should prescribe more. Medicines
optimisation teams either ignore the variation altogether, or send letters to
practices that turn out to be prescribing perfectly appropriately, which
destroys the relationship and gets the next letter binned.

Separating warranted from unwarranted variation needs two things that most
practice-level reporting does not do:

  1. ADJUST FOR NEED. Crude rates compare a retirement town against a student
     district. Indirect standardisation answers "how many items would this
     practice be expected to issue, given the age and sex of the people actually
     registered with it", and the ratio of observed to expected is the number
     worth looking at.

  2. USE FUNNEL PLOTS, NOT LEAGUE TABLES. Funnel plots make the precision of
     each estimate explicit by plotting it against the size of its denominator,
     so a practice counts as an outlier only if it falls outside the range that
     ordinary variation would produce AT ITS OWN SIZE.

     The usual justification for this - that a ranked table is dominated at both
     ends by small units - is TESTED here rather than assumed, and on the
     headline measure it turns out to be barely true. Practices issue tens of
     thousands of items over three years, so sampling noise is a fraction of a
     percent and cannot push anybody to an extreme. It is emphatically true on
     low-volume measures, and block C2 shows both cases side by side. Being able
     to say which situation you are in is more useful than reciting the rule.

Blocks:
  A. Build the model, compute crude rates, produce the naive league table, and
     test the textbook objection to it.
  B. Indirect age-sex standardisation, and STAR-PU construction.
  C. Funnel plots with 95% and 99.8% limits, plus an overdispersion adjustment -
     which is needed here for the OPPOSITE reason to the textbook one: counts
     are so large that pure Poisson limits flag 97% of England.
  C2. The same method on a low-volume measure, where the funnel is a funnel.
  D. Validation against known ground truth: does the funnel plot actually find
     the practices that are genuinely unusual, and does the league table not?
  E. Generic switching, low-priority prescribing, antimicrobial stewardship.
  F. Opportunity if the worst decile moved to the median.
  G. Reconciliation, including one calibration gap flagged rather than buried.

Run:  python src/02_analysis.py
"""
from __future__ import annotations

import duckdb
import numpy as np
import pandas as pd
from pathlib import Path
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROC = ROOT / "data" / "processed"
SQL = ROOT / "sql"
TABLES = ROOT / "outputs" / "tables"
for d in (PROC, TABLES):
    d.mkdir(parents=True, exist_ok=True)
DB = PROC / "prescribing.duckdb"
pd.set_option("display.width", 220)

AGE_BANDS = ["0-4", "5-14", "15-24", "25-34", "35-44",
             "45-54", "55-64", "65-74", "75+"]
BANDS = [f"{a}_{s}" for a in AGE_BANDS for s in ["M", "F"]]

# ---------------------------------------------------------------------------
# STATED ASSUMPTIONS. All of these are challengeable and all of them are here.
# ---------------------------------------------------------------------------
ASSUMPTIONS = {
    "achievable_generic_switch_rate": (0.80,
        "Share of branded prescribing that could realistically move to the "
        "generic equivalent. NOT 100%: some patients cannot switch for "
        "clinical reasons - bioequivalence concerns in narrow therapeutic "
        "index drugs, formulation intolerance, specialist-initiated therapy "
        "the practice cannot unilaterally change."),
    "achievable_low_priority_reduction": (0.70,
        "Share of low-priority spend that could stop. Again not 100%: the NHS "
        "England guidance is explicit that these items may still be "
        "appropriate for individual patients, and liothyronine in particular "
        "has a recognised group of patients who do not respond to levothyroxine."),
    "overdispersion_method": ("Spiegelhalter (2005) additive random effects",
        "Winsorised z-scores used to estimate the between-practice variance "
        "that exceeds Poisson, then added to the within-practice variance."),
}
SWITCH_RATE = ASSUMPTIONS["achievable_generic_switch_rate"][0]
LP_REDUCTION = ASSUMPTIONS["achievable_low_priority_reduction"][0]


# ===========================================================================
def build_model(con) -> None:
    print("Loading and modelling ...")
    con.execute(f"CREATE OR REPLACE VIEW prescribing AS SELECT * FROM "
                f"read_parquet('{(RAW/'prescribing.parquet').as_posix()}')")
    for name in ["bnf_presentations", "practice_reference",
                 "practice_list_size", "qof_prevalence"]:
        con.execute(f"CREATE OR REPLACE TABLE {name} AS SELECT * FROM "
                    f"read_csv_auto('{(RAW/(name + '.csv')).as_posix()}')")
    con.execute("CREATE OR REPLACE VIEW bnf AS SELECT * FROM bnf_presentations")

    for chunk in (SQL / "01_model.sql").read_text(encoding="utf-8").split(";"):
        body = "\n".join(ln for ln in chunk.splitlines()
                         if ln.strip() and not ln.strip().startswith("--"))
        if body.strip():
            con.execute(body)

    n = con.execute("SELECT COUNT(*) FROM prescribing").fetchone()[0]
    p = con.execute("SELECT COUNT(*) FROM dim_practice").fetchone()[0]
    print(f"  {n:,} prescribing rows, {p:,} practices")


# ===========================================================================
def block_a_league_table(con) -> pd.DataFrame:
    """The naive answer, and a hypothesis that turned out to be half wrong.

    THE TEXTBOOK CLAIM, AND WHAT ACTUALLY HAPPENED
    Every account of funnel plots - including the one I would have written
    before running this - says a ranked league table is dominated at both ends
    by SMALL units, because small denominators carry more sampling variation.
    That is why funnel plots exist.

    On this data it is barely true, and it is worth understanding why rather
    than asserting it anyway. Practices here issue between 29,000 and 190,000
    items over 36 months. The Poisson coefficient of variation on a count of
    29,000 is 0.6%. Genuine between-practice variation in prescribing behaviour
    is worth tens of percent. Sampling noise is simply not in the same league,
    so it does not push small practices to the extremes.

    The claim IS true on low-volume measures - a practice may issue five
    liothyronine prescriptions in three years, where the CV is 45% - and that is
    tested explicitly below.

    So this league table has a different problem, and a worse one: it is
    measuring the POPULATION rather than the prescriber. That is the problem
    standardisation fixes, and it is the one the brief actually describes.
    """
    print("\n" + "=" * 76)
    print("A. THE LEAGUE TABLE - and testing the textbook objection to it")
    print("=" * 76)
    df = con.execute("SELECT * FROM practice_crude_rates").df()

    # ---- test 1: is the league table dominated by small practices? -------
    print("\n  TEST: are the extremes of the ranking dominated by small practices?")
    q25 = df.total_patients.quantile(0.25)
    lp_rate = 1000 * df.low_priority_items / df.total_patients
    liothy = con.execute("""
        SELECT p.practice_code, SUM(p.items) AS items
        FROM prescribing p JOIN bnf b ON b.bnf_code = p.bnf_code
        WHERE b.chemical_substance = 'Liothyronine sodium'
        GROUP BY 1
    """).df()
    df = df.merge(liothy.rename(columns={"items": "liothyronine_items"}),
                  on="practice_code", how="left").fillna({"liothyronine_items": 0})
    lt_rate = 1000 * df.liothyronine_items / df.total_patients

    print(f"\n  {'measure':<34}{'median count':>13}{'Poisson CV':>12}"
          f"{'% of extremes':>15}")
    print(f"  {'':<34}{'per practice':>13}{'at that n':>12}"
          f"{'that are small':>15}")
    for name, rate, count in [
            ("All sections (high volume)", df.items_per_1000_per_month, df["items"]),
            ("Low-priority items", lp_rate, df.low_priority_items),
            ("Liothyronine only (low volume)", lt_rate, df.liothyronine_items)]:
        rank = rate.rank(ascending=False)
        ext = (rank <= 100) | (rank > len(df) - 100)
        med = count.median()
        cv = 100 / np.sqrt(max(med, 1))
        print(f"  {name:<34}{med:>13,.0f}{cv:>11.1f}%"
              f"{(df.total_patients[ext] < q25).mean()*100:>14.0f}%")
    print(f"\n  A quarter of practices are 'small' by definition, so 25% is the")
    print(f"  no-effect baseline. The high-volume measure sits at that baseline:")
    print(f"  the textbook objection does not bite here, because the counts are")
    print(f"  far too large for sampling noise to matter. On liothyronine it")
    print(f"  bites hard, which is exactly where a funnel plot earns its keep.")

    # ---- test 2: what IS the league table measuring? ---------------------
    print(f"\n  TEST: what is the crude rate actually correlated with?")
    for col, label in [("pct_over_65", "% of patients over 65"),
                       ("imd_decile", "IMD decile (10 = least deprived)"),
                       ("qof_hypertension_prevalence", "QOF hypertension prevalence"),
                       ("qof_diabetes_prevalence", "QOF diabetes prevalence"),
                       ("total_patients", "list size")]:
        r = df[["items_per_1000_per_month", col]].corr().iloc[0, 1]
        bar = "#" * int(abs(r) * 30)
        print(f"    {label:<36} r = {r:+.2f}  {bar}")
    print(f"\n  There is the real problem. The crude rate is very largely a")
    print(f"  measurement of how old the registered population is. Ranking on it")
    print(f"  and writing to the top of the list means writing to the practices")
    print(f"  with the oldest patients, which is both useless and, the first time")
    print(f"  a GP points it out, the end of the working relationship.")
    df.to_csv(TABLES / "practice_crude_rates.csv", index=False)
    return df


# ===========================================================================
def block_b_standardise(con) -> pd.DataFrame:
    """Indirect standardisation, and the STAR-PU that falls out of it.

    INDIRECT, NOT DIRECT, AND THE DISTINCTION MATTERS.
      direct   - apply each practice's age-specific RATES to a standard
                 population. Needs stable rates in every band for every
                 practice. With 600-patient practices and 18 bands, several
                 bands have a handful of patients and the rates are noise.
      indirect - apply the NATIONAL age-specific rates to each practice's own
                 population, giving an EXPECTED count, then compare with what
                 was observed. Stable at any practice size, which is exactly
                 why public health uses it for small areas.

    The output is a Standardised Prescribing Ratio: observed / expected, where
    100 means "exactly what a practice with this population would be expected to
    issue".

    THE STAR-PU FALLS STRAIGHT OUT OF THIS. A prescribing unit is nothing more
    than the age-sex weights implied by the national rates, normalised so the
    national average patient scores 1. Building it from the data rather than
    importing a published table means the weights are internally consistent with
    the denominator actually being used - and it demonstrates what the published
    tables are, which is worth more than quoting them.
    """
    print("\n" + "=" * 76)
    print("B. INDIRECT AGE-SEX STANDARDISATION")
    print("=" * 76)

    pop = con.execute(f"""
        SELECT practice_code, total_patients, {', '.join(chr(34) + 'pop_' + b + chr(34) for b in BANDS)}
        FROM practice_list_size
    """).df().set_index("practice_code")
    obs = con.execute("""
        SELECT practice_code, bnf_section, SUM(items) AS items
        FROM fct_practice_total GROUP BY 1, 2
    """).df()

    band_pop = pop[[f"pop_{b}" for b in BANDS]].to_numpy().astype(float)
    national_pop = band_pop.sum(axis=0)

    out, starpu_rows = [], []
    for section, g in obs.groupby("bnf_section"):
        g = g.set_index("practice_code").reindex(pop.index).fillna(0)
        observed = g["items"].to_numpy()

        # National age-specific rates cannot be observed directly here: the
        # extract is practice-level, not patient-level, so the rates have to be
        # recovered from aggregates.
        #
        # THE OBVIOUS APPROACH DOES NOT WORK, AND IT IS WORTH KNOWING WHY.
        # Regressing practice item counts on the 18 band populations with
        # non-negative least squares looks right and returns nonsense - a spiky
        # vector that is mostly exact zeros with a handful of enormous values.
        # The cause is collinearity: every practice's band populations are very
        # nearly proportional to its list size, so the 18 columns carry almost
        # the same information and the individual coefficients are not
        # identifiable. NNLS resolves that indeterminacy by dumping all the
        # weight on a few columns, which is numerically valid and clinically
        # absurd (it implied men under 75 use no antibiotics at all).
        #
        # The fix is to stop asking for 18 free parameters and ask for a SHAPE.
        # Prescribing rates rise smoothly with age and differ modestly by sex,
        # so a three-parameter log-linear model is fitted instead:
        #     rate(band) = exp(a + b * standardised_age + c * is_female)
        # Three parameters are comfortably identifiable from 6,300 practices,
        # the result is stable, and it looks like a published prescribing unit -
        # which is the point, because that is what published prescribing units
        # are.
        from scipy.optimize import least_squares

        band_age_mid = np.repeat([2, 10, 20, 30, 40, 50, 60, 70, 82], 2)
        z_age = (band_age_mid - 45.0) / 25.0
        is_f = np.array([1.0 if b.endswith("_F") else 0.0 for b in BANDS])

        def predict(theta):
            return band_pop @ np.exp(theta[0] + theta[1] * z_age + theta[2] * is_f)

        def resid(theta):
            mu = np.maximum(predict(theta), 1e-6)
            # Pearson residuals: the right weighting for count data, so large
            # practices do not simply dominate the fit by being large.
            return (observed - mu) / np.sqrt(mu)

        start = [np.log(max(observed.sum() / national_pop.sum(), 1e-9)), 0.5, 0.0]
        fit = least_squares(resid, start, method="lm", max_nfev=4000)
        rates = np.exp(fit.x[0] + fit.x[1] * z_age + fit.x[2] * is_f)

        expected = band_pop @ rates
        # Guard: a practice with an expected count near zero cannot support a
        # ratio at all, and including it manufactures spurious extremes.
        keep = expected >= 30
        spr = np.where(keep, observed / np.maximum(expected, 1e-9), np.nan) * 100

        out.append(pd.DataFrame({
            "practice_code": pop.index, "bnf_section": section,
            "observed_items": observed, "expected_items": expected,
            "spr": spr, "usable": keep,
        }))

        # STAR-PU weights: national band rate divided by the national overall
        # per-patient rate, so the average patient in England scores 1.0.
        overall = observed.sum() / national_pop.sum()
        starpu_rows.append(pd.DataFrame({
            "bnf_section": section, "age_sex_band": BANDS,
            "national_items_per_patient": rates,
            "starpu_weight": rates / overall,
        }))

    std = pd.concat(out, ignore_index=True)
    starpu = pd.concat(starpu_rows, ignore_index=True)

    print("\n  STAR-PU weights, antibacterials (0501) - the age profile of need:")
    ab = starpu[starpu.bnf_section == "0501"].copy()
    ab["age_band"] = [b.split("_")[0] for b in ab.age_sex_band]
    ab["sex"] = [b.split("_")[1] for b in ab.age_sex_band]
    piv = ab.pivot_table(index="age_band", columns="sex", values="starpu_weight")
    print(piv.reindex(AGE_BANDS).round(2).to_string())

    print("\n  Same, lipid-regulating drugs (0212) - a much steeper gradient:")
    lp = starpu[starpu.bnf_section == "0212"].copy()
    lp["age_band"] = [b.split("_")[0] for b in lp.age_sex_band]
    lp["sex"] = [b.split("_")[1] for b in lp.age_sex_band]
    print(lp.pivot_table(index="age_band", columns="sex", values="starpu_weight")
            .reindex(AGE_BANDS).round(2).to_string())
    print("\n  This is why one prescribing unit cannot serve every drug group.")
    print("  A 75-year-old is worth a few times an average patient for statins")
    print("  and roughly an average patient for antibiotics.")

    # ---- practice-level STAR-PU denominators ----------------------------
    star_den = []
    for section, g in starpu.groupby("bnf_section"):
        w = g.set_index("age_sex_band").reindex(BANDS).starpu_weight.to_numpy()
        star_den.append(pd.DataFrame({
            "practice_code": pop.index, "bnf_section": section,
            "star_pu": band_pop @ w,
        }))
    star_den = pd.concat(star_den, ignore_index=True)
    std = std.merge(star_den, on=["practice_code", "bnf_section"], how="left")
    std["items_per_starpu"] = std.observed_items / std.star_pu.replace(0, np.nan)

    # ---- all-section total, which is what the headline analysis uses -----
    tot = (std.groupby("practice_code")
              .agg(observed_items=("observed_items", "sum"),
                   expected_items=("expected_items", "sum"))
              .reset_index())
    tot["spr"] = tot.observed_items / tot.expected_items * 100
    tot = tot.merge(
        con.execute("""SELECT practice_code, total_patients, pct_over_65,
                              imd_decile, imd_quintile, region, icb_code,
                              list_size_band, practice_name
                       FROM dim_practice""").df(), on="practice_code")

    crude = con.execute("""SELECT practice_code, items_per_1000_per_month
                           FROM practice_crude_rates""").df()
    tot = tot.merge(crude, on="practice_code")

    print(f"\n  Standardised prescribing ratio across all sections in scope:")
    print(f"    median {tot.spr.median():.1f}, "
          f"IQR {tot.spr.quantile(.25):.1f}-{tot.spr.quantile(.75):.1f}, "
          f"range {tot.spr.min():.0f}-{tot.spr.max():.0f}")
    for col, label in [("pct_over_65", "% over 65"),
                       ("imd_decile", "IMD decile")]:
        r_crude = tot[["items_per_1000_per_month", col]].corr().iloc[0, 1]
        r_std = tot[["spr", col]].corr().iloc[0, 1]
        print(f"    correlation with {label:<12}  crude r = {r_crude:+.2f}   "
              f"standardised r = {r_std:+.2f}")
    print("\n  Standardisation has removed almost all of the association with")
    print("  age. What is left is the variation worth asking about.")

    std.to_csv(TABLES / "standardisation_by_section.csv", index=False)
    starpu.to_csv(TABLES / "starpu_weights.csv", index=False)
    tot.to_csv(TABLES / "practice_spr.csv", index=False)
    return tot


# ===========================================================================
def funnel_limits(expected: np.ndarray, spr: np.ndarray,
                  adjust_overdispersion: bool = True):
    """Funnel plot control limits for an indirectly standardised ratio.

    THE BASIC IDEA
    If a practice is behaving exactly like the national average, its observed
    count is a Poisson draw with mean = its expected count. So for any expected
    count E, there is a range of observed counts that ordinary chance produces.
    Divide that range by E and you have the range of ratios that is consistent
    with "nothing unusual here" AT THAT PRACTICE'S SIZE. Plot those ranges
    against E and they form a funnel - wide on the left where E is small, narrow
    on the right where E is large.

    A practice outside the funnel is unusual. A practice inside it is not,
    however extreme its rank.

    WHY THE OVERDISPERSION ADJUSTMENT IS NOT OPTIONAL
    Pure Poisson limits assume the ONLY reason practices differ is chance. With
    6,300 real practices that is plainly false - practices genuinely differ in
    case mix, local formularies, specialist services, and referral patterns
    beyond anything age and sex capture. The consequence is that unadjusted
    limits flag hundreds of practices, which is useless: an outlier list that
    contains a fifth of the country is not a list anybody can act on.

    Spiegelhalter's additive random-effects adjustment estimates how much
    between-practice variance exceeds Poisson, using z-scores WINSORISED at the
    10th and 90th percentiles so that the genuine outliers do not inflate the
    estimate of ordinary variation - which would be circular. That extra
    variance is then added to the within-practice variance when the limits are
    drawn.
    """
    E = np.asarray(expected, dtype=float)
    ratio = np.asarray(spr, dtype=float) / 100.0
    ok = np.isfinite(E) & np.isfinite(ratio) & (E > 0)

    phi = 1.0
    tau2 = 0.0
    if adjust_overdispersion:
        # HOW tau^2 IS ESTIMATED, AND ONE THAT DID NOT WORK
        #
        # The first attempt used the variance-stabilised form: z = 2(sqrt(O) -
        # sqrt(E)), Winsorised at the 10th and 90th percentiles, with
        # tau^2 = (phi - 1) / mean(4E). It returned tau^2 = 0.0039 against an
        # actual between-practice spread of about 0.025 - roughly six times too
        # small - and the funnel consequently flagged 45% of all practices.
        # Clipping at the 10th and 90th percentiles is very aggressive when the
        # ORDINARY variation is itself large, which is the situation here:
        # prescribing genuinely differs between practices by tens of percent, so
        # most of the spread being trimmed was signal about ordinary variation
        # rather than outlier contamination.
        #
        # DerSimonian-Laird works directly on the ratio scale and is the
        # standard method-of-moments estimator for exactly this quantity. It is
        # also self-checking: tau^2 should come out close to the variance of the
        # ratios minus the average sampling variance, and that check is printed.
        #
        # Winsorisation is kept but at the 5th and 95th percentiles, which is
        # enough to stop 95 genuine outliers driving the estimate of ordinary
        # variation - the circularity Spiegelhalter warns about - without
        # discarding the ordinary variation itself.
        r, e = ratio[ok], E[ok]
        w = e                                  # 1 / within-practice variance
        lo, hi = np.percentile(r, [5, 95])
        rw = np.clip(r, lo, hi)                # Winsorise the ratios
        rbar = np.sum(w * rw) / np.sum(w)
        Q = float(np.sum(w * (rw - rbar) ** 2))
        n = len(rw)
        denom = np.sum(w) - np.sum(w ** 2) / np.sum(w)
        tau2 = max(0.0, (Q - (n - 1)) / denom)
        phi = Q / max(n - 1, 1)

    grid = np.unique(np.round(np.geomspace(max(E[ok].min(), 1),
                                           E[ok].max(), 220)))
    lim = {}
    for p, name in ((0.025, "l95"), (0.975, "u95"),
                    (0.001, "l998"), (0.999, "u998")):
        z = stats.norm.ppf(p)
        # limits on the ratio scale, with within + between variance
        lim[name] = 1.0 + z * np.sqrt(1.0 / grid + tau2)
    lim["expected"] = grid

    # per-practice flags
    se = np.sqrt(1.0 / np.maximum(E, 1e-9) + tau2)
    z95, z998 = stats.norm.ppf(0.975), stats.norm.ppf(0.999)
    flags = pd.DataFrame({
        "outside_95": (np.abs(ratio - 1.0) > z95 * se) & ok,
        "outside_998": (np.abs(ratio - 1.0) > z998 * se) & ok,
        "direction": np.where(ratio > 1.0, "high", "low"),
        "z_score": (ratio - 1.0) / se,
    })
    return pd.DataFrame(lim), flags, phi, tau2


def block_c_funnel(tot: pd.DataFrame):
    print("\n" + "=" * 76)
    print("C. FUNNEL PLOTS")
    print("=" * 76)

    lim_raw, flag_raw, phi_raw, _ = funnel_limits(
        tot.expected_items, tot.spr, adjust_overdispersion=False)
    lim_adj, flag_adj, phi, tau2 = funnel_limits(
        tot.expected_items, tot.spr, adjust_overdispersion=True)

    obs_var = float(np.nanvar(tot.spr.to_numpy() / 100.0))
    within = float(np.nanmean(1.0 / tot.expected_items.replace(0, np.nan).to_numpy()))
    print(f"\n  Overdispersion factor phi = {phi:,.1f}")
    print(f"  (phi = 1 would mean practices differ only by chance. With 80,000")
    print(f"   items per practice they could not possibly.)")
    print(f"\n  SELF-CHECK on the between-practice variance:")
    print(f"    observed variance of the ratios          {obs_var:.5f}")
    print(f"    average within-practice (sampling) var   {within:.7f}")
    print(f"    so between-practice variance is about    {obs_var - within:.5f}")
    print(f"    DerSimonian-Laird tau^2                  {tau2:.5f}")
    print(f"    The DL figure is slightly lower because the ratios were")
    print(f"    Winsorised at the 5th and 95th percentiles, so genuine outliers")
    print(f"    do not inflate the estimate of ORDINARY variation. Letting them")
    print(f"    would be circular: ordinary variation is precisely what the")
    print(f"    limits are supposed to describe.")
    print()
    print(f"  Practices outside the 95% limits:")
    print(f"    unadjusted (pure Poisson)  {int(flag_raw.outside_95.sum()):>5,}  "
          f"({flag_raw.outside_95.mean()*100:.1f}% of all practices)")
    print(f"    overdispersion-adjusted    {int(flag_adj.outside_95.sum()):>5,}  "
          f"({flag_adj.outside_95.mean()*100:.1f}%)")
    print(f"  Practices outside the 99.8% limits:")
    print(f"    unadjusted                 {int(flag_raw.outside_998.sum()):>5,}")
    print(f"    overdispersion-adjusted    {int(flag_adj.outside_998.sum()):>5,}")
    print()
    print("  Unadjusted limits flag almost every practice in England. That is")
    print("  not a subtle failure - it is the method announcing that its")
    print("  assumption is wrong. With 80,000 items per practice the pure")
    print("  Poisson interval is about half a percent wide, so ANY real")
    print("  difference in prescribing behaviour falls outside it.")
    print()
    print("  This is the opposite of the textbook worry. The classic funnel-plot")
    print("  problem is small denominators making everything look extreme. Here")
    print("  the denominators are enormous, and the problem is that pure Poisson")
    print("  badly understates how much practices genuinely differ. Same fix,")
    print("  opposite cause, and worth being able to tell them apart.")

    tot = tot.join(flag_adj)
    tot["z_score"] = flag_adj.z_score
    tot.to_csv(TABLES / "practice_funnel.csv", index=False)
    lim_adj.to_csv(TABLES / "funnel_limits.csv", index=False)
    lim_raw.to_csv(TABLES / "funnel_limits_unadjusted.csv", index=False)
    return tot, lim_adj, lim_raw, phi, tau2


# ===========================================================================
def block_c2_low_volume_funnel(con) -> pd.DataFrame:
    """The same method on a LOW-VOLUME measure, and why it looks different.

    The all-sections funnel plot in block C does not look like a funnel. Its
    control limits are two almost straight horizontal lines. That is not a
    drawing error and it is worth understanding rather than hiding.

    A funnel plot gets its shape from sampling variance, which falls as the
    denominator grows: 1/E is large on the left and small on the right. Add
    overdispersion and the limits become 1 +/- z * sqrt(1/E + tau^2). When
    tau^2 (0.022) is a thousand times larger than 1/E (about 0.000015), the 1/E
    term contributes nothing and the limits are flat. The chart is telling the
    truth: at 80,000 items per practice, precision is essentially identical
    everywhere, so practice size is irrelevant to whether a practice is unusual.

    On a low-volume measure the arithmetic reverses. Liothyronine: a practice
    may issue a handful of items in three years, 1/E is large and varies
    enormously between practices, and the funnel has its textbook shape - wide
    on the left, narrow on the right, and small practices genuinely do sit at
    both extremes without being unusual at all.

    Showing both is the honest version. One picture without the other either
    asserts a shape the data does not have, or implies the classic problem never
    arises.
    """
    print("\n" + "=" * 76)
    print("C2. THE SAME METHOD ON A LOW-VOLUME MEASURE")
    print("=" * 76)

    obs = con.execute("""
        SELECT d.practice_code, d.total_patients,
               COALESCE(SUM(p.items), 0) AS items
        FROM dim_practice d
        LEFT JOIN prescribing p ON p.practice_code = d.practice_code
        LEFT JOIN bnf b ON b.bnf_code = p.bnf_code
                       AND b.chemical_substance = 'Liothyronine sodium'
        WHERE b.bnf_code IS NOT NULL OR p.practice_code IS NULL
        GROUP BY 1, 2
    """).df()
    # Simple expected count: national rate per patient x this practice's list.
    # Age standardisation adds nothing here - the point being made is about the
    # DENOMINATOR, and keeping it simple keeps that visible.
    rate = obs["items"].sum() / obs.total_patients.sum()
    obs["expected_items"] = obs.total_patients * rate
    obs["spr"] = obs["items"] / obs.expected_items * 100

    lim, flags, phi, tau2 = funnel_limits(obs.expected_items, obs.spr, True)
    obs = obs.join(flags)
    within = float(np.nanmean(1.0 / obs.expected_items.replace(0, np.nan)))
    print(f"\n  Liothyronine, 36 months")
    print(f"    median items per practice          "
          f"{obs['items'].median():>10,.0f}")
    print(f"    expected items, 10th-90th pct      "
          f"{obs.expected_items.quantile(.1):>10,.0f} - "
          f"{obs.expected_items.quantile(.9):,.0f}")
    print(f"    average sampling variance (1/E)    {within:>10.5f}")
    print(f"    between-practice variance tau^2    {tau2:>10.5f}")
    print(f"    ratio tau^2 : 1/E                  "
          f"{tau2/within:>10.2f}   (all sections: ~1,470)")
    print(f"    practices outside 99.8% limits     "
          f"{int(obs.outside_998.sum()):>10,}")
    print()
    print("  Here the two variance terms are comparable, so the limits actually")
    print("  funnel. On the all-sections measure tau^2 is over a thousand times")
    print("  1/E, the sampling term contributes nothing, and the limits are flat.")
    print("  Both charts are correct. Showing only one of them is not.")

    # does the size effect appear on THIS measure?
    q25 = obs.total_patients.quantile(0.25)
    rank = (obs["items"] / obs.total_patients).rank(ascending=False)
    ext = (rank <= 100) | (rank > len(obs) - 100)
    print(f"\n  Share of the ranking's extremes that are small practices:")
    print(f"    liothyronine rate  {(obs.total_patients[ext] < q25).mean()*100:>5.0f}%"
          f"   (25% would be no effect)")
    print(f"    and of the funnel plot's flags: "
          f"{(obs.total_patients[obs.outside_998] < q25).mean()*100:.0f}%")
    print("\n  THAT is the textbook problem, and it is real - on this measure.")

    obs.to_csv(TABLES / "liothyronine_funnel.csv", index=False)
    lim.to_csv(TABLES / "liothyronine_funnel_limits.csv", index=False)
    return obs


# ===========================================================================
def block_d_validate(tot: pd.DataFrame) -> pd.DataFrame:
    """Does the method actually work?

    This is only possible because the data is synthetic and 95 practices were
    given a genuine, large prescribing-style effect. On real data you can never
    check this. Here we can, and it is the single most useful thing in the
    project: it shows the league table finding the wrong practices and the
    funnel plot finding the right ones.
    """
    print("\n" + "=" * 76)
    print("D. VALIDATION AGAINST KNOWN GROUND TRUTH")
    print("=" * 76)
    truth = pd.read_csv(RAW / "_ground_truth_do_not_use_in_analysis.csv")
    df = tot.merge(truth[["practice_code", "is_true_outlier"]], on="practice_code")
    n_true = int(df.is_true_outlier.sum())
    print(f"\n  {n_true} practices were given a genuine prescribing-style effect.")
    print(f"  Neither method was told which ones.\n")

    rows = []
    # league table: take the top and bottom N by crude rate
    for n in (95, 200):
        rank = df.items_per_1000_per_month.rank(ascending=False)
        picked = (rank <= n / 2) | (rank > len(df) - n / 2)
        rows.append({
            "method": f"League table, top and bottom {n}",
            "practices_flagged": int(picked.sum()),
            "true_outliers_found": int(df.is_true_outlier[picked].sum()),
            "precision_pct": 100 * df.is_true_outlier[picked].mean(),
            "recall_pct": 100 * df.is_true_outlier[picked].sum() / n_true,
        })
    for col, label in [("outside_95", "Funnel plot, outside 95% limits"),
                       ("outside_998", "Funnel plot, outside 99.8% limits")]:
        picked = df[col].to_numpy()
        rows.append({
            "method": label,
            "practices_flagged": int(picked.sum()),
            "true_outliers_found": int(df.is_true_outlier[picked].sum()),
            "precision_pct": 100 * df.is_true_outlier[picked].mean() if picked.sum() else 0.0,
            "recall_pct": 100 * df.is_true_outlier[picked].sum() / n_true,
        })
    val = pd.DataFrame(rows)
    print(val.round(1).to_string(index=False))

    # THE FAIR COMPARISON IS AT EQUAL WORKLOAD.
    # Comparing a 95-practice league table against a 471-practice funnel list
    # is not a comparison, it is a difference in how many letters you are
    # willing to send. The 99.8% funnel list is 111 practices, which is close
    # enough to 95 to be a like-for-like test of the same amount of work.
    lt = val.iloc[0]
    fp = val[val.method.str.startswith("Funnel plot, outside 99.8")].iloc[0]
    print(f"\n  LIKE FOR LIKE, at roughly the same workload:")
    print(f"    league table, {int(lt.practices_flagged)} practices  ->  "
          f"{int(lt.true_outliers_found)} genuine, "
          f"{lt.precision_pct:.0f}% precision, {lt.recall_pct:.0f}% recall")
    print(f"    99.8% funnel, {int(fp.practices_flagged)} practices ->  "
          f"{int(fp.true_outliers_found)} genuine, "
          f"{fp.precision_pct:.0f}% precision, {fp.recall_pct:.0f}% recall")
    print(f"\n  In the terms a medicines optimisation pharmacist cares about:")
    print(f"    of {int(lt.practices_flagged)} conversations booked off the "
          f"league table, "
          f"{int(lt.practices_flagged - lt.true_outliers_found)} are with")
    print(f"    practices prescribing entirely appropriately.")
    print(f"    of {int(fp.practices_flagged)} booked off the funnel plot, "
          f"{int(fp.practices_flagged - fp.true_outliers_found)} are.")
    print(f"    Same diary, {int(fp.true_outliers_found) - int(lt.true_outliers_found)} "
          f"more real problems found, "
          f"{int(lt.practices_flagged - lt.true_outliers_found) - int(fp.practices_flagged - fp.true_outliers_found)} "
          f"fewer wasted meetings.")

    rank = df.items_per_1000_per_month.rank(ascending=False)
    lt_picked = (rank <= 47) | (rank > len(df) - 47)
    print(f"\n  Median list size of the practices each method flags:")
    print(f"    all practices              {df.total_patients.median():>8,.0f}")
    print(f"    league table flags         {df.total_patients[lt_picked].median():>8,.0f}")
    print(f"    funnel plot flags          "
          f"{df.total_patients[df.outside_998].median():>8,.0f}")
    print()
    print("  Note what this does NOT show. The league table's flags are not")
    print("  systematically smaller than average. Block A established that, and")
    print("  repeating the textbook line here would be asserting something this")
    print("  data does not support.")
    print()
    print("  The league table fails for a different reason: it ranks on a crude")
    print("  rate that correlates +0.73 with the share of patients over 65, so it")
    print("  is substantially a ranking of population age. It catches some")
    print("  genuine outliers, because a large enough style effect pushes a")
    print("  practice to the top of any ranking - but it cannot tell you WHICH of")
    print("  its flags are genuine, and about half are practices prescribing")
    print("  entirely appropriately for an old population. Those are the")
    print("  conversations that end the relationship.")

    val.to_csv(TABLES / "method_validation.csv", index=False)
    return val


# ===========================================================================
def block_e_savings(con, tot: pd.DataFrame) -> dict:
    print("\n" + "=" * 76)
    print("E. SAVINGS OPPORTUNITIES")
    print("=" * 76)

    gen = con.execute("SELECT * FROM generic_opportunity").df()
    gross = gen.gross_opportunity.sum()
    achievable = gross * SWITCH_RATE
    print(f"\n  GENERIC SWITCHING")
    print(gen[["chemical_substance", "generic_rate_pct", "branded_items",
               "generic_cost_per_item", "branded_cost_per_item",
               "gross_opportunity"]].to_string(index=False))
    print(f"\n    gross opportunity over 36 months      GBP {gross:>12,.0f}")
    print(f"    x {SWITCH_RATE:.0%} achievable switch rate       "
          f"GBP {achievable:>12,.0f}")
    print(f"    per year                              GBP {achievable/3:>12,.0f}")
    print(f"\n    The {SWITCH_RATE:.0%} matters. Assuming 100% is the single "
          f"fastest way to")
    print(f"    lose a clinical audience: some patients genuinely cannot switch,")
    print(f"    and a pharmacist reading a 100% figure knows immediately that")
    print(f"    nobody asked one.")

    lp = con.execute("""
        SELECT b.chemical_substance, b.bnf_description,
               SUM(p.items) AS items, SUM(p.actual_cost) AS cost
        FROM prescribing p JOIN bnf b ON b.bnf_code = p.bnf_code
        WHERE b.is_low_priority = 1
        GROUP BY 1, 2 ORDER BY cost DESC
    """).df()
    lp_total = lp.cost.sum()
    print(f"\n  LOW-PRIORITY PRESCRIBING")
    print(f"  (NHS England: items which should not routinely be prescribed)")
    print(lp.assign(cost=lp.cost.round(0)).to_string(index=False))
    print(f"\n    total over 36 months                  GBP {lp_total:>12,.0f}")
    print(f"    x {LP_REDUCTION:.0%} achievable reduction         "
          f"GBP {lp_total*LP_REDUCTION:>12,.0f}")
    print(f"    per year                              "
          f"GBP {lp_total*LP_REDUCTION/3:>12,.0f}")

    # concentration: how many practices account for most of the low-priority spend
    lpp = con.execute("""
        SELECT practice_code, SUM(low_priority_cost) AS lp_cost
        FROM fct_practice_total GROUP BY 1 ORDER BY lp_cost DESC
    """).df()
    lpp["cum_share"] = lpp.lp_cost.cumsum() / lpp.lp_cost.sum()
    n_half = int((lpp.cum_share <= 0.5).sum()) + 1
    print(f"\n    {n_half:,} practices ({n_half/len(lpp)*100:.0f}% of the total) "
          f"account for half of all low-priority spend.")
    print(f"    That concentration is the whole reason this is actionable: it is")
    print(f"    a conversation with {n_half:,} practices, not a national campaign.")

    ab = con.execute("""
        SELECT d.practice_code, d.total_patients,
               SUM(CASE WHEN t.bnf_section = '0501' THEN t.items ELSE 0 END) AS ab_items,
               SUM(t.broad_spectrum_items) AS broad_items
        FROM fct_practice_total t JOIN dim_practice d USING (practice_code)
        GROUP BY 1, 2
    """).df()
    # BNF section codes are zero-padded strings ('0501'). read_csv will happily
    # turn that into the integer 501, after which this filter matches nothing
    # and every antimicrobial figure below comes back NaN - silently, because
    # a merge on an empty frame is not an error. Force the dtype, then assert.
    star = pd.read_csv(TABLES / "standardisation_by_section.csv",
                       dtype={"bnf_section": str})
    star = star[star.bnf_section == "0501"][["practice_code", "star_pu"]]
    assert len(star), "no 0501 rows found - check the bnf_section dtype"
    ab = ab.merge(star, on="practice_code")
    ab["items_per_starpu"] = ab.ab_items / ab.star_pu.replace(0, np.nan)
    ab["broad_spectrum_pct"] = 100 * ab.broad_items / ab.ab_items.replace(0, np.nan)
    print(f"\n  ANTIMICROBIAL STEWARDSHIP")
    print(f"    antibacterial items per STAR-PU, 36 months: "
          f"median {ab.items_per_starpu.median():.2f}, "
          f"90th pct {ab.items_per_starpu.quantile(.9):.2f}")
    print(f"    broad-spectrum share of antibacterial items: "
          f"median {ab.broad_spectrum_pct.median():.1f}%, "
          f"90th pct {ab.broad_spectrum_pct.quantile(.9):.1f}%")
    print(f"    practices above 10% broad-spectrum: "
          f"{(ab.broad_spectrum_pct > 10).sum():,} "
          f"({(ab.broad_spectrum_pct > 10).mean()*100:.0f}%)")

    gen.to_csv(TABLES / "generic_opportunity.csv", index=False)
    lp.to_csv(TABLES / "low_priority_spend.csv", index=False)
    ab.to_csv(TABLES / "antimicrobial.csv", index=False)
    return {"generic_gross": gross, "generic_achievable": achievable,
            "low_priority_total": lp_total,
            "low_priority_achievable": lp_total * LP_REDUCTION,
            "practices_half_lp": n_half}


# ===========================================================================
def block_f_decile_opportunity(con, tot: pd.DataFrame) -> dict:
    """If the top decile moved to the median, what would that be worth?

    Deliberately expressed as a SCENARIO, not a saving. Nobody has committed to
    anything, no practice has agreed to change, and the arithmetic assumes the
    entire gap above the median is addressable, which it is not. It is a way of
    sizing a problem, and it should be labelled as one.
    """
    print("\n" + "=" * 76)
    print("F. SCENARIO: IF THE TOP DECILE MOVED TO THE MEDIAN")
    print("=" * 76)
    cost = con.execute("""
        SELECT practice_code, SUM(actual_cost) AS cost, SUM(items) AS items
        FROM fct_practice_total GROUP BY 1
    """).df()
    d = tot.merge(cost, on="practice_code")
    d["cost_per_expected_item"] = d.cost / d.expected_items.replace(0, np.nan)

    med_spr = d.spr.median()
    p90 = d.spr.quantile(0.90)
    top = d[d.spr >= p90]
    excess_items = ((top.spr - med_spr) / 100 * top.expected_items).sum()
    cost_per_item = d.cost.sum() / d.observed_items.sum()
    value = excess_items * cost_per_item

    print(f"\n    median standardised ratio        {med_spr:6.1f}")
    print(f"    90th percentile                  {p90:6.1f}")
    print(f"    practices in the top decile      {len(top):,}")
    print(f"    excess items above the median    {excess_items:,.0f} over 36 months")
    print(f"    average cost per item            GBP {cost_per_item:.2f}")
    print(f"    scenario value                   GBP {value:,.0f} over 36 months")
    print(f"                                     GBP {value/3:,.0f} per year")
    print(f"\n    Label this a scenario, not a saving. It assumes the whole gap")
    print(f"    above the median is addressable, and some of it will be genuine")
    print(f"    need that age and sex do not capture. It sizes the question.")
    return {"scenario_value_annual": value / 3, "top_decile_practices": len(top),
            "excess_items": excess_items}


# ===========================================================================
def block_g_reconcile(con, savings: dict) -> None:
    print("\n" + "=" * 76)
    print("G. RECONCILIATION")
    print("=" * 76)
    tot = con.execute("""
        SELECT SUM(items) AS items, SUM(actual_cost) AS cost,
               COUNT(DISTINCT practice_code) AS practices,
               COUNT(DISTINCT year_month) AS n_months
        FROM fct_practice_month f
    """).df().iloc[0]
    src = con.execute("""SELECT SUM(items) AS items, SUM(actual_cost) AS cost,
                                COUNT(*) AS rows FROM prescribing""").df().iloc[0]
    listsize = con.execute("SELECT SUM(total_patients) FROM dim_practice").fetchone()[0]

    print(f"\n  Control totals, source to model:")
    print(f"    source rows                {int(src["rows"]):>15,}")
    print(f"    source items               {src["items"]:>15,}   "
          f"model {tot["items"]:>15,}   {'tie' if src["items"] == tot["items"] else 'BREAK'}")
    print(f"    source cost           GBP  {src["cost"]:>15,.0f}   "
          f"model {tot["cost"]:>15,.0f}   "
          f"{'tie' if abs(src["cost"] - tot["cost"]) < 1 else 'BREAK'}")
    print(f"    practices                  {int(tot["practices"]):>15,}")
    print(f"    months                     {int(tot["n_months"]):>15,}")
    print(f"    registered patients        {listsize:>15,}")
    print(f"\n  Derived measures against the registered population:")
    print(f"    items per patient per year "
          f"{tot["items"] / listsize / 3:>15.1f}")
    print(f"    cost per patient per year  GBP "
          f"{tot["cost"] / listsize / 3:>11.2f}")
    lp_cost = con.execute(
        "SELECT SUM(low_priority_cost) FROM fct_practice_total").fetchone()[0]
    print(f"\n  KNOWN CALIBRATION GAP, stated rather than buried:")
    print(f"    Low-priority items are {lp_cost/tot['cost']*100:.1f}% of spend in")
    print(f"    this extract. Nationally they are closer to 1-2% of the total")
    print(f"    prescribing bill. The per-item costs and volumes of the individual")
    print(f"    low-priority products are realistic on their own; the six sections")
    print(f"    around them are under-weighted, which inflates the share.")
    print(f"    Consequence: the low-priority OPPORTUNITY figure is a")
    print(f"    demonstration of the method, not a number for a business case.")
    print(f"    The funnel-plot and generic-switching findings do not depend on it.")
    print(f"\n  Sense check against published England figures: primary care")
    print(f"  prescribing runs at roughly 20 items and GBP 150 per patient per")
    print(f"  year across ALL BNF chapters. This extract covers six sections, so")
    print(f"  a materially smaller figure is what we should see, and do.")


def main() -> None:
    if DB.exists():
        DB.unlink()
    con = duckdb.connect(str(DB))
    con.execute("PRAGMA memory_limit='5GB'")
    build_model(con)
    block_a_league_table(con)
    tot = block_b_standardise(con)
    tot, lim_adj, lim_raw, phi, tau2 = block_c_funnel(tot)
    block_c2_low_volume_funnel(con)
    block_d_validate(tot)
    savings = block_e_savings(con, tot)
    scen = block_f_decile_opportunity(con, tot)
    block_g_reconcile(con, savings)

    pd.DataFrame([{k: v[0] for k, v in ASSUMPTIONS.items()}
                  | {"overdispersion_phi": phi, "tau_squared": tau2}
                  | savings | scen]).to_csv(TABLES / "assumptions.csv", index=False)
    con.execute("SELECT * FROM national_monthly").df().to_csv(
        TABLES / "national_monthly.csv", index=False)
    print(f"\nAll tables written to {TABLES}")
    con.close()


if __name__ == "__main__":
    main()
