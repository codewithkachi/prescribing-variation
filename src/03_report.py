"""
Project 4 - Step 3: charts, dashboard, practice report template.

The anchor visual is the funnel plot, and it is worth saying why it is drawn the
way it is. A funnel plot is one of the few charts that is genuinely ARGUMENTATIVE:
its whole job is to show the reader that the extremes of a ranking are not
evidence. That only works if the control limits are visible, if the horizontal
axis is the precision of the estimate rather than anything else, and if the
practices inside the funnel are drawn quietly enough that the eye goes to the
ones outside.

Run:  python src/03_report.py
"""
from __future__ import annotations

import sys
import duckdb
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from analystkit import (PALETTE, INK, STATUS, SEQ_BLUE, apply_theme, save_fig,
                        fmt_gbp, Dashboard, Kpi)         # noqa: E402
from analystkit.theme import despine, DIVERGING          # noqa: E402

DB = ROOT / "data" / "processed" / "prescribing.duckdb"
T = ROOT / "outputs" / "tables"
CH = ROOT / "outputs" / "charts"
CH.mkdir(parents=True, exist_ok=True)
apply_theme()
AGE_BANDS = ["0-4", "5-14", "15-24", "25-34", "35-44",
             "45-54", "55-64", "65-74", "75+"]


def load(n, **kw):
    return pd.read_csv(T / f"{n}.csv", **kw)


# ---------------------------------------------------------------------------
def chart_crude_problem(crude: pd.DataFrame) -> Path:
    """What the crude rate is actually measuring."""
    fig, axes = plt.subplots(1, 2, figsize=(9.4, 4.0))
    axes[0].scatter(crude.pct_over_65, crude.items_per_1000_per_month, s=5,
                    color=PALETTE[0], alpha=0.22, edgecolor="none")
    z = np.polyfit(crude.pct_over_65, crude.items_per_1000_per_month, 1)
    xs = np.linspace(crude.pct_over_65.min(), crude.pct_over_65.max(), 50)
    axes[0].plot(xs, np.polyval(z, xs), color=INK["primary"], lw=2)
    r = crude[["pct_over_65", "items_per_1000_per_month"]].corr().iloc[0, 1]
    axes[0].set_xlabel("% of registered patients aged 65+")
    axes[0].set_ylabel("Crude items per 1,000 patients per month")
    axes[0].set_title(f"Crude rate:  r = {r:+.2f}")

    spr = load("practice_spr")
    axes[1].scatter(spr.pct_over_65, spr.spr, s=5, color=PALETTE[2], alpha=0.22,
                    edgecolor="none")
    z2 = np.polyfit(spr.pct_over_65, spr.spr, 1)
    xs2 = np.linspace(spr.pct_over_65.min(), spr.pct_over_65.max(), 50)
    axes[1].plot(xs2, np.polyval(z2, xs2), color=INK["primary"], lw=2)
    r2 = spr[["pct_over_65", "spr"]].corr().iloc[0, 1]
    axes[1].axhline(100, color=INK["baseline"], ls="--", lw=1)
    axes[1].set_xlabel("% of registered patients aged 65+")
    axes[1].set_ylabel("Standardised prescribing ratio")
    axes[1].set_title(f"After standardisation:  r = {r2:+.2f}")
    for a in axes:
        despine(a)
    fig.suptitle("The crude rate is mostly a measurement of the population",
                 x=0.015, ha="left", fontsize=12.5, fontweight="600")
    fig.tight_layout(rect=[0, 0, 1, 0.92])
    return save_fig(fig, CH / "01_crude_vs_standardised.png",
                    "Left: rank practices on this and you rank them by how old "
                    "their patients are. Right: the same practices after "
                    "indirect age-sex standardisation, with the association "
                    "removed. What is left is the question worth asking.")


def chart_funnel(fun: pd.DataFrame, lim: pd.DataFrame) -> Path:
    """The anchor visual."""
    fig, ax = plt.subplots(figsize=(9.0, 5.2))
    inside = ~fun.outside_95
    ax.scatter(fun.expected_items[inside] / 1000, fun.spr[inside], s=6,
               color=INK["muted"], alpha=0.30, edgecolor="none",
               label="within control limits", zorder=2)
    hi = fun.outside_998 & (fun.spr > 100)
    lo = fun.outside_998 & (fun.spr < 100)
    mid = fun.outside_95 & ~fun.outside_998
    ax.scatter(fun.expected_items[mid] / 1000, fun.spr[mid], s=13,
               color=STATUS["warning"], alpha=0.75, edgecolor="none",
               label="outside 95%", zorder=3)
    ax.scatter(fun.expected_items[hi] / 1000, fun.spr[hi], s=26,
               color=STATUS["critical"], edgecolor=INK["surface"], linewidth=0.6,
               label="outside 99.8%, prescribing more than expected", zorder=4)
    ax.scatter(fun.expected_items[lo] / 1000, fun.spr[lo], s=26,
               color=PALETTE[0], edgecolor=INK["surface"], linewidth=0.6,
               label="outside 99.8%, prescribing less than expected", zorder=4)

    x = lim.expected / 1000
    for col, style, lab in [("u95", (0, (4, 3)), "95% limits"),
                            ("l95", (0, (4, 3)), None),
                            ("u998", "-", "99.8% limits"),
                            ("l998", "-", None)]:
        ax.plot(x, lim[col] * 100, color=INK["secondary"], lw=1.4, ls=style,
                label=lab, zorder=5)
    ax.axhline(100, color=INK["primary"], lw=1.2, zorder=5)

    ax.set_xscale("log")
    ax.set_xlabel("Expected items over 36 months, thousands (log scale) "
                  "- the precision of the estimate")
    ax.set_ylabel("Standardised prescribing ratio (100 = as expected)")
    ax.set_title("Funnel plot: which practices are genuinely unusual?")
    ax.set_ylim(40, 190)
    ax.legend(fontsize=8.4, loc="upper right", ncol=1)
    despine(ax)
    return save_fig(fig, CH / "02_funnel_plot.png",
                    "Limits include an overdispersion adjustment "
                    "(DerSimonian-Laird tau-squared = 0.022). Without it, pure "
                    "Poisson limits are about half a percent wide at these "
                    "counts and flag 97% of practices.")


def chart_funnel_compare(fun: pd.DataFrame, lim: pd.DataFrame,
                         lim_raw: pd.DataFrame) -> Path:
    fig, axes = plt.subplots(1, 2, figsize=(9.8, 4.2), sharey=True)
    for ax, L, title, n in [
            (axes[0], lim_raw, "Pure Poisson limits", int(fun.spr.notna().sum())),
            (axes[1], lim, "With overdispersion adjustment", 0)]:
        ax.scatter(fun.expected_items / 1000, fun.spr, s=4,
                   color=INK["muted"], alpha=0.25, edgecolor="none")
        x = L.expected / 1000
        for col in ("u95", "l95"):
            ax.plot(x, L[col] * 100, color=STATUS["critical"], lw=1.5)
        for col in ("u998", "l998"):
            ax.plot(x, L[col] * 100, color=INK["secondary"], lw=1.3, ls="--")
        ax.axhline(100, color=INK["primary"], lw=1.1)
        ax.set_xscale("log")
        ax.set_title(title, fontsize=10.5)
        ax.set_xlabel("Expected items, thousands (log)")
        despine(ax)
    axes[0].set_ylabel("Standardised prescribing ratio")
    axes[0].set_ylim(40, 190)
    n_raw = 6100
    n_adj = int(fun.outside_95.sum())
    axes[0].text(0.03, 0.05, f"{n_raw:,} practices flagged\n(97% of England)",
                 transform=axes[0].transAxes, fontsize=9,
                 color=STATUS["critical"], fontweight="600")
    axes[1].text(0.03, 0.05, f"{n_adj:,} practices flagged\n(7.5%)",
                 transform=axes[1].transAxes, fontsize=9,
                 color=STATUS["good"], fontweight="600")
    fig.suptitle("Why the overdispersion adjustment is not optional",
                 x=0.015, ha="left", fontsize=12.5, fontweight="600")
    fig.tight_layout(rect=[0, 0, 1, 0.9])
    return save_fig(fig, CH / "03_overdispersion.png",
                    "With 80,000 items per practice the pure Poisson interval "
                    "is about half a percent wide, so any real difference in "
                    "prescribing behaviour falls outside it. That is the method "
                    "announcing its assumption is wrong.")


def chart_starpu(star: pd.DataFrame) -> Path:
    fig, ax = plt.subplots(figsize=(8.0, 4.2))
    for i, (sec, name) in enumerate([("0212", "Lipid-regulating (statins)"),
                                     ("0501", "Antibacterials"),
                                     ("0401", "Hypnotics and anxiolytics")]):
        g = star[star.bnf_section.astype(str).str.zfill(4) == sec].copy()
        g["age_band"] = [b.split("_")[0] for b in g.age_sex_band]
        m = (g.groupby("age_band").starpu_weight.mean()
              .reindex(AGE_BANDS))
        ax.plot(range(len(AGE_BANDS)), m.to_numpy(), marker="o", lw=2,
                color=PALETTE[i], label=name, markeredgecolor=INK["surface"],
                markeredgewidth=1.5)
    ax.axhline(1.0, color=INK["baseline"], ls="--", lw=1)
    ax.text(0.15, 1.06, "average patient = 1.0", fontsize=8.4,
            color=INK["muted"])
    ax.set_xticks(range(len(AGE_BANDS)))
    ax.set_xticklabels(AGE_BANDS)
    ax.set_xlabel("Age band")
    ax.set_ylabel("Prescribing unit weight")
    ax.set_title("One prescribing unit cannot serve every drug group")
    ax.legend(fontsize=9)
    despine(ax)
    return save_fig(fig, CH / "04_starpu.png",
                    "Weights recovered from the data by fitting a smooth "
                    "age-sex model to practice aggregates. A 75-year-old is "
                    "worth three average patients for statins and about one for "
                    "antibiotics, which is why need adjustment has to be "
                    "drug-specific.")


def chart_validation(val: pd.DataFrame) -> Path:
    d = val.copy()
    d["label"] = d.method.str.replace("League table, top and bottom",
                                      "League table\ntop+bottom")
    d["label"] = d.label.str.replace("Funnel plot, outside", "Funnel plot\noutside")
    fig, ax = plt.subplots(figsize=(8.6, 4.2))
    x = np.arange(len(d))
    ax.bar(x - 0.19, d.precision_pct, width=0.36, color=PALETTE[0],
           label="precision: % of flagged practices that are genuinely unusual")
    ax.bar(x + 0.19, d.recall_pct, width=0.36, color=PALETTE[1],
           label="recall: % of the 95 genuine outliers found")
    for i, r in enumerate(d.itertuples()):
        ax.text(i - 0.19, r.precision_pct + 1.6, f"{r.precision_pct:.0f}%",
                ha="center", fontsize=8.8, color=INK["secondary"])
        ax.text(i + 0.19, r.recall_pct + 1.6, f"{r.recall_pct:.0f}%",
                ha="center", fontsize=8.8, color=INK["secondary"])
        ax.text(i, -9, f"{int(r.practices_flagged)} flagged", ha="center",
                fontsize=8.2, color=INK["muted"])
    ax.set_xticks(x)
    ax.set_xticklabels(d.label, fontsize=8.6)
    ax.set_ylabel("%")
    ax.set_ylim(-14, 112)
    ax.set_title("Does the method actually find the right practices?")
    ax.legend(fontsize=8.6, loc="upper left")
    ax.grid(axis="x", visible=False)
    despine(ax, keep=("left",))
    return save_fig(fig, CH / "05_validation.png",
                    "Only possible because the data is synthetic and 95 "
                    "practices were given a genuine prescribing-style effect. "
                    "Neither method was told which. At comparable workload the "
                    "funnel plot is 65% precise against the league table's 47%.")


def chart_generic(gen: pd.DataFrame) -> Path:
    d = gen.sort_values("gross_opportunity")
    fig, axes = plt.subplots(1, 2, figsize=(9.6, 3.8))
    axes[0].barh(d.chemical_substance, d.generic_rate_pct, color=PALETTE[2],
                 height=0.55)
    axes[0].axvline(100, color=INK["baseline"], ls="--", lw=1)
    for i, v in enumerate(d.generic_rate_pct):
        axes[0].text(v - 1.2, i, f"{v:.1f}%", va="center", ha="right",
                     fontsize=8.8, color="white", fontweight="600")
    axes[0].set_xlim(90, 101)
    axes[0].set_xlabel("Generic prescribing rate (%)")
    axes[0].set_title("Generic rates are already high")
    axes[1].barh(d.chemical_substance, d.gross_opportunity / 1e6,
                 color=PALETTE[1], height=0.55)
    for i, v in enumerate(d.gross_opportunity / 1e6):
        axes[1].text(v * 1.02, i, f"GBP {v:.1f}m", va="center", fontsize=8.8,
                     color=INK["secondary"])
    axes[1].set_xlim(0, d.gross_opportunity.max() / 1e6 * 1.3)
    axes[1].set_xlabel("Gross opportunity over 36 months (GBP m)")
    axes[1].set_title("but the residue is still worth having")
    axes[1].set_yticklabels([])
    for a in axes:
        a.grid(axis="y", visible=False)
        despine(a, keep=("bottom",))
    fig.tight_layout()
    return save_fig(fig, CH / "06_generic.png",
                    "Both panels matter. A 99.4% generic rate looks like a "
                    "solved problem, and the remaining 0.6% is still worth "
                    "GBP 11m over three years because the price gap per item is "
                    "twenty-fold.")


def chart_lp_concentration(con) -> Path:
    d = con.execute("""
        SELECT practice_code, SUM(low_priority_cost) AS cost
        FROM fct_practice_total GROUP BY 1 ORDER BY cost DESC
    """).df()
    d["cum_share"] = d.cost.cumsum() / d.cost.sum() * 100
    d["practice_share"] = (np.arange(len(d)) + 1) / len(d) * 100
    fig, ax = plt.subplots(figsize=(7.4, 4.2))
    ax.plot(d.practice_share, d.cum_share, color=PALETTE[0], lw=2.4)
    ax.plot([0, 100], [0, 100], color=INK["baseline"], ls="--", lw=1.2)
    ax.text(52, 46, "if spend were spread evenly", fontsize=8.6,
            color=INK["muted"], rotation=32)
    half = float(d.practice_share[d.cum_share >= 50].iloc[0])
    ax.axhline(50, color=INK["muted"], lw=0.9, ls=":")
    ax.axvline(half, color=INK["muted"], lw=0.9, ls=":")
    ax.scatter([half], [50], s=70, color=STATUS["critical"], zorder=4,
               edgecolor=INK["surface"], linewidth=2)
    ax.annotate(f"{half:.0f}% of practices\naccount for half the spend",
                (half, 50), textcoords="offset points", xytext=(14, -30),
                fontsize=9.2, color=INK["secondary"], fontweight="600")
    ax.set_xlabel("Practices, ranked by low-priority spend (%)")
    ax.set_ylabel("Cumulative share of low-priority spend (%)")
    ax.set_title("Low-priority prescribing is concentrated, which makes it actionable")
    despine(ax)
    return save_fig(fig, CH / "07_low_priority_concentration.png",
                    "Concentration is what turns a national problem into a "
                    "workload. This is a conversation with a defined list of "
                    "practices, not a campaign.")


def chart_broad_spectrum(ab: pd.DataFrame) -> Path:
    fig, ax = plt.subplots(figsize=(7.8, 3.8))
    ax.hist(ab.broad_spectrum_pct.dropna(), bins=60, color=PALETTE[0],
            edgecolor=INK["surface"], linewidth=0.3)
    ax.axvline(10, color=STATUS["critical"], lw=2)
    over = (ab.broad_spectrum_pct > 10).sum()
    ax.text(10.4, ax.get_ylim()[1] * 0.82,
            f"national target: 10%\n{over:,} practices above it "
            f"({over/len(ab)*100:.0f}%)",
            fontsize=9, color=STATUS["critical"], fontweight="600")
    ax.axvline(ab.broad_spectrum_pct.median(), color=INK["primary"], lw=1.4,
               ls="--")
    ax.text(ab.broad_spectrum_pct.median() - 0.3, ax.get_ylim()[1] * 0.5,
            f"median {ab.broad_spectrum_pct.median():.1f}%", ha="right",
            fontsize=8.8, color=INK["secondary"])
    ax.set_xlabel("Broad-spectrum antibacterials as % of all antibacterial items")
    ax.set_ylabel("Practices")
    ax.set_title("Antimicrobial stewardship: co-amoxiclav, cephalosporins, quinolones")
    despine(ax)
    return save_fig(fig, CH / "08_broad_spectrum.png",
                    "A separate behaviour from antibiotic VOLUME. A practice can "
                    "prescribe few antibiotics and still reach for the broad "
                    "one, and stewardship guidance treats the two as different "
                    "questions.")


def chart_trend(nat: pd.DataFrame) -> Path:
    nat["month"] = pd.to_datetime(nat.year_month.astype(str), format="%Y%m")
    ab = nat[nat.bnf_section.astype(str).str.zfill(4) == "0501"]
    ab = ab.groupby("month").agg(items=("items", "sum"),
                                 lst=("list_size", "sum")).reset_index()
    ab["rate"] = 1000 * ab["items"] / ab.lst
    other = nat[nat.bnf_section.astype(str).str.zfill(4) != "0501"]
    other = other.groupby("month").agg(items=("items", "sum"),
                                       lst=("list_size", "sum")).reset_index()
    other["rate"] = 1000 * other["items"] / other.lst

    fig, axes = plt.subplots(2, 1, figsize=(8.6, 4.6), sharex=True,
                             gridspec_kw={"hspace": 0.3})
    axes[0].plot(ab.month, ab.rate, color=PALETTE[1], lw=2)
    axes[0].set_ylabel("items per 1,000")
    axes[0].set_title("Antibacterials: strongly seasonal")
    axes[1].plot(other.month, other.rate, color=PALETTE[0], lw=2)
    axes[1].set_ylabel("items per 1,000")
    axes[1].set_title("Everything else: flat")
    for a in axes:
        despine(a)
    return save_fig(fig, CH / "09_trend.png",
                    "Two panels, never two y-axes. Seasonality matters for a "
                    "practical reason: comparing a winter-heavy month against a "
                    "summer one is another way to manufacture a fake outlier.")



def chart_funnel_shapes(fun, lim, lio, liolim) -> Path:
    """The textbook funnel next to the honest one.

    The first version of this chart tried to show a flat funnel (high volume)
    beside a properly funnel-shaped one (low volume). The second panel refused
    to cooperate: liothyronine prescribing varies so much between practices that
    overdispersion dominates there too, and its limits are only slightly curved.

    Forcing the shape would have meant picking a measure until one looked like
    the textbook picture. The honest version shows WHY the textbook picture does
    not appear: it is what you get if you assume practices differ only by
    chance, and on real prescribing data they emphatically do not.
    """
    from scipy import stats as _st
    NL = chr(10)
    fig, axes = plt.subplots(1, 2, figsize=(10.2, 4.6), sharey=True)
    E = liolim.expected.to_numpy()

    for ax, poisson_only, title, sub in [
        (axes[0], True, "If practices differed only by chance",
         "pure Poisson limits - the textbook funnel"),
        (axes[1], False, "What the data actually supports",
         "with between-practice variation included")]:
        ax.scatter(lio.expected_items, lio.spr, s=4, color=INK["muted"],
                   alpha=0.20, edgecolor="none", zorder=2)
        for p_, ls, lw in [(0.975, (0, (4, 3)), 1.4), (0.999, "-", 1.5)]:
            z = _st.norm.ppf(p_)
            if poisson_only:
                hi = (1 + z * np.sqrt(1 / E)) * 100
                lo = (1 - z * np.sqrt(1 / E)) * 100
            else:
                col_u = "u95" if p_ < 0.99 else "u998"
                col_l = "l95" if p_ < 0.99 else "l998"
                hi = liolim[col_u].to_numpy() * 100
                lo = liolim[col_l].to_numpy() * 100
            ax.plot(E, hi, color=STATUS["critical"] if poisson_only
                    else INK["secondary"], lw=lw, ls=ls, zorder=4)
            ax.plot(E, lo, color=STATUS["critical"] if poisson_only
                    else INK["secondary"], lw=lw, ls=ls, zorder=4)
        ax.axhline(100, color=INK["primary"], lw=1.1, zorder=4)
        ax.set_xscale("log")
        ax.set_xlabel("Expected items over 36 months (log scale)")
        ax.set_title(title + NL + sub, fontsize=10)
        despine(ax)

    axes[0].set_ylabel("Standardised prescribing ratio")
    axes[0].set_ylim(0, 330)
    n_pois = int((np.abs(lio.spr / 100 - 1)
                  > _st.norm.ppf(0.999) * np.sqrt(1 / lio.expected_items)).sum())
    axes[0].text(0.04, 0.90, f"{n_pois:,} practices flagged" + NL + "(66% of England)",
                 transform=axes[0].transAxes, fontsize=9.2,
                 color=STATUS["critical"], fontweight="600")
    axes[1].text(0.04, 0.90,
                 f"{int(lio.outside_998.sum()):,} practices flagged",
                 transform=axes[1].transAxes, fontsize=9.2,
                 color=STATUS["good"], fontweight="600")
    fig.suptitle("Liothyronine: the textbook funnel, and the one the data supports",
                 x=0.015, ha="left", fontsize=12.5, fontweight="600")
    fig.tight_layout(rect=[0, 0, 1, 0.9])
    return save_fig(fig, CH / "10_funnel_shapes.png",
                    "The classic funnel shape on the left comes entirely from "
                    "assuming practices differ only by sampling chance. They do "
                    "not: even on a drug where a practice issues 57 items in "
                    "three years, genuine between-practice variation is 27 times "
                    "the sampling variance. The honest limits are wider and "
                    "flatter, and they flag a list somebody can actually work.")


# ---------------------------------------------------------------------------
def practice_report(fun: pd.DataFrame, crude: pd.DataFrame, ab: pd.DataFrame,
                    con) -> str:
    """The one-page template a medicines optimisation pharmacist would take
    into a conversation. Built for the single most extreme practice."""
    p = fun.loc[fun.z_score.idxmax()]
    c = crude[crude.practice_code == p.practice_code].iloc[0]
    a = ab[ab.practice_code == p.practice_code]
    lp = con.execute(f"""
        SELECT SUM(low_priority_cost) AS lp, SUM(actual_cost) AS total
        FROM fct_practice_total WHERE practice_code = '{p.practice_code}'
    """).df().iloc[0]
    med_spr = fun.spr.median()
    L = [
        f"# Prescribing review: {p.practice_name} ({p.practice_code})",
        "",
        f"**{p.region} · {p.icb_code} · list size {int(p.total_patients):,} · "
        f"IMD decile {int(p.imd_decile)} · {p.pct_over_65:.1f}% aged 65+**",
        "",
        "## Why this practice is on the list",
        "",
        f"After adjusting for the age and sex of your registered population, this "
        f"practice issued **{p.spr:.0f} items for every 100 expected** across the "
        f"six BNF sections in scope. The median practice in England sits at "
        f"{med_spr:.0f}.",
        "",
        f"That is **outside the 99.8% control limit** on a funnel plot of all "
        f"6,300 English practices — meaning the gap is larger than random "
        f"variation and ordinary between-practice differences together would "
        f"produce at your list size.",
        "",
        "**This is not a crude ranking.** Age and sex are already accounted for. "
        "Practices with older populations are expected to prescribe more, and "
        "that expectation is built into the figure above.",
        "",
        "## The numbers",
        "",
        "| Measure | This practice | England median | |",
        "|---|---:|---:|---|",
        f"| Standardised prescribing ratio | **{p.spr:.0f}** | {med_spr:.0f} | "
        f"{p.spr/med_spr-1:+.0%} |",
        f"| Items per 1,000 patients per month | {c.items_per_1000_per_month:.1f} | "
        f"{crude.items_per_1000_per_month.median():.1f} | "
        f"{c.items_per_1000_per_month/crude.items_per_1000_per_month.median()-1:+.0%} |",
        f"| Low-priority spend, 36 months | GBP {lp.lp:,.0f} | | "
        f"{lp.lp/lp.total*100:.1f}% of your total |",
    ]
    if len(a):
        aa = a.iloc[0]
        L.append(f"| Broad-spectrum antibacterials | {aa.broad_spectrum_pct:.1f}% | "
                 f"{ab.broad_spectrum_pct.median():.1f}% | target below 10% |")
    L += [
        "",
        "## What we are NOT saying",
        "",
        "- We are not saying this prescribing is clinically wrong. We cannot see "
        "your patients.",
        "- We are not saying it is unjustified. Age and sex are adjusted for; a "
        "specialist clinic, a nursing home on your list, or a local service you "
        "provide on behalf of others are not, and any of those would explain the "
        "gap entirely.",
        "- We are not asking you to reduce prescribing to a target.",
        "",
        "## What we are asking",
        "",
        "One conversation, to establish whether there is a reason we cannot see "
        "in the data. If there is, we record it and this practice comes off the "
        "list — permanently, not until the next report.",
        "",
        "---",
        "",
        "*Method: indirect age-sex standardisation against national rates, with "
        "funnel plot control limits including an overdispersion adjustment. "
        "Measure definitions follow OpenPrescribing and the NHS England "
        "low-priority list. Full method and code in the repository.*",
    ]
    return "\n".join(L)


def main() -> None:
    con = duckdb.connect(str(DB), read_only=True)
    crude = load("practice_crude_rates")
    fun = load("practice_funnel")
    lim = load("funnel_limits")
    lim_raw = load("funnel_limits_unadjusted")
    star = load("starpu_weights", dtype={"bnf_section": str})
    val = load("method_validation")
    gen = load("generic_opportunity")
    lp = load("low_priority_spend")
    ab = load("antimicrobial")
    nat = load("national_monthly", dtype={"bnf_section": str})
    ass = load("assumptions").iloc[0]
    lio = load("liothyronine_funnel")
    liolim = load("liothyronine_funnel_limits")

    print("Rendering charts ...")
    c1 = chart_crude_problem(crude)
    c2 = chart_funnel(fun, lim)
    c3 = chart_funnel_compare(fun, lim, lim_raw)
    c4 = chart_starpu(star)
    c5 = chart_validation(val)
    c6 = chart_generic(gen)
    c7 = chart_lp_concentration(con)
    c8 = chart_broad_spectrum(ab)
    c9 = chart_trend(nat)
    c10 = chart_funnel_shapes(fun, lim, lio, liolim)

    rep = practice_report(fun, crude, ab, con)
    (ROOT / "outputs" / "practice_report_example.md").write_text(rep, encoding="utf-8")

    n_998 = int(fun.outside_998.sum())
    n_95 = int(fun.outside_95.sum())
    lt = val.iloc[0]
    fp = val[val.method.str.startswith("Funnel plot, outside 99.8")].iloc[0]

    d = Dashboard(
        "Prescribing Variation and Medicines Optimisation",
        "Separating warranted from unwarranted variation across 6,300 English "
        "GP practices. 8.8 million prescribing rows, six BNF sections, three "
        "years, filtered at source through the NHSBSA Open Data API.",
        "Figures in this build come from a synthetic dataset with the NHSBSA "
        "English Prescribing Dataset schema; src/01_extract_nhsbsa.py is the "
        "real extractor and every downstream file runs unchanged against live "
        "data. BNF codes, chemical substances, product pairs and the NHS "
        "England low-priority list are real. Measure definitions follow "
        "OpenPrescribing. Absolute pound figures are properties of the "
        "generator, not of England - see the reconciliation note.",
        eyebrow="Project 04 / Healthcare / Unwarranted variation")

    p = d.page("The problem")
    d.kpis(p, [
        Kpi("Practices", "6,300", "36 months, 8.8m rows"),
        Kpi("Crude rate vs age", "r = +0.73",
            "the league table ranks population age", "critical"),
        Kpi("After standardisation", "r = +0.00",
            "the association is gone", "good"),
        Kpi("Genuine outliers found", f"{n_998}",
            "outside 99.8% limits"),
        Kpi("Precision vs league table", f"{fp.precision_pct:.0f}% vs {lt.precision_pct:.0f}%",
            "at comparable workload", "good"),
    ])
    d.chart(p, c1, "", wide=True)
    d.note(p, "The finding in one paragraph",
           "A medicines optimisation team ranks practices on prescribing rate and "
           "writes to the top of the list. That list correlates **+0.73** with the "
           "share of patients aged over 65: it is substantially a ranking of how "
           "old the registered population is. Roughly **half** the practices on it "
           "are prescribing entirely appropriately for the patients they have, and "
           "each of those letters costs a working relationship.\n\n"
           "Indirect age-sex standardisation removes the association with age "
           "completely (r falls to **+0.00**). Funnel plots then separate the "
           "practices whose remaining variation is larger than chance and ordinary "
           "between-practice difference would produce. At the same workload the "
           f"funnel list is **{fp.precision_pct:.0f}% precise** against the league "
           f"table's **{lt.precision_pct:.0f}%** — "
           f"**{int(fp.true_outliers_found - lt.true_outliers_found)} more real "
           f"problems found and "
           f"{int((lt.practices_flagged - lt.true_outliers_found) - (fp.practices_flagged - fp.true_outliers_found))} "
           "fewer wasted conversations.**")
    d.chart(p, c4, "")
    d.chart(p, c9, "")

    p = d.page("Funnel plots")
    d.chart(p, c2, "", wide=True)
    d.chart(p, c3, "", wide=True)
    d.chart(p, c10, "", wide=True)
    d.note(p, "The overdispersion adjustment, and why the textbook reason is not the reason here",
           "Every account of funnel plots says the problem with a league table is "
           "that **small** units sit at both extremes, because small denominators "
           "carry more sampling variation.\n\n"
           "**On this data that is barely true, and it is worth knowing why.** "
           "Practices issue between 29,000 and 190,000 items over 36 months. The "
           "Poisson coefficient of variation on 29,000 is **0.6%**. Genuine "
           "differences in prescribing behaviour are worth tens of percent. "
           "Sampling noise is not in the same league, so it does not push small "
           "practices to the extremes — measured on the high-volume rate, the "
           "flagged practices are no smaller than average. It **is** true on "
           "low-volume measures: liothyronine, where a practice may issue a "
           "handful of items in three years.\n\n"
           "So the adjustment here is needed for the **opposite** reason to the "
           "textbook one. Pure Poisson limits are about half a percent wide at "
           "these counts, so they flag **97% of England**. Estimating the genuine "
           "between-practice variance (DerSimonian-Laird, tau-squared = "
           f"{ass.tau_squared:.3f}) and adding it to the sampling variance brings "
           f"that to **{n_95:,}** at 95% and **{n_998}** at 99.8%.\n\n"
           "An earlier attempt used the variance-stabilised form with Winsorising "
           "at the 10th and 90th percentiles and returned a tau-squared six times "
           "too small, flagging 45% of practices. The self-check that caught it — "
           "comparing the estimate against the observed variance of the ratios "
           "minus the average sampling variance — is printed in the analysis output.")

    p = d.page("Does it work?")
    d.chart(p, c5, "", wide=True)
    d.table(p, val.round(1), "95 practices were given a genuine prescribing-style "
                             "effect by the data generator. Neither method was "
                             "told which. This check is only possible because the "
                             "data is synthetic, and it is the most useful thing "
                             "in the project.")
    d.note(p, "Reading the table honestly",
           "The 95% funnel list has the highest recall (**97%**) and the lowest "
           "precision (**20%**), because it flags 471 practices. The 99.8% list "
           "flags 111 — a workload comparable to the league table's 95 — and is "
           "**65% precise** with **76% recall**.\n\n"
           "Which you choose depends on what the list is for. A 99.8% list is the "
           "right basis for a letter, because the cost of being wrong is a damaged "
           "relationship. A 95% list is the right basis for an internal watchlist, "
           "where the cost of being wrong is only your own time.\n\n"
           "That choice is a judgement about consequences, not a statistical one, "
           "and it should be made explicitly rather than by whichever threshold "
           "the software defaults to.")

    p = d.page("Savings")
    d.kpis(p, [
        Kpi("Generic switching", fmt_gbp(ass.generic_achievable / 3),
            "per year, at 80% achievable", "good"),
        Kpi("Low-priority", fmt_gbp(ass.low_priority_achievable / 3),
            "per year, at 70% achievable — see caveat", "warning"),
        Kpi("Concentration", f"{int(ass.practices_half_lp):,}",
            "practices hold half the low-priority spend"),
        Kpi("Top-decile scenario", fmt_gbp(ass.scenario_value_annual),
            "per year if they moved to the median", "neutral"),
    ])
    d.chart(p, c6, "", wide=True)
    d.chart(p, c7, "")
    d.chart(p, c8, "")
    d.note(p, "Two things stated rather than buried",
           "**Nothing here assumes 100% switching.** The generic figure applies an "
           "80% achievable rate and the low-priority figure 70%, because some "
           "patients genuinely cannot switch — narrow therapeutic index drugs, "
           "formulation intolerance, specialist-initiated therapy the practice "
           "cannot unilaterally change. NHS England's own guidance says explicitly "
           "that low-priority items may still be right for individual patients. A "
           "pharmacist reading a 100% figure knows immediately that nobody asked "
           "one.\n\n"
           "**The low-priority figure is a demonstration, not a business case.** "
           "Low-priority items are 13% of spend in this extract against 1-2% "
           "nationally. The individual products are costed realistically; the six "
           "sections around them are under-weighted in the generator, which "
           "inflates the share. The funnel-plot and generic-switching findings do "
           "not depend on it. This is in the reconciliation note too, because a "
           "figure that flatters the analysis is exactly the one to flag.")

    p = d.page("Practice report")
    d.note(p, "The deliverable that actually changes anything",
           "A dashboard does not change prescribing. A conversation does, and the "
           "conversation needs one page that a pharmacist can put on a desk. Below "
           "is the template, generated for the most extreme practice in the "
           "dataset.\n\n"
           "The three design decisions in it are all about the same thing — making "
           "the conversation possible rather than defensive:\n\n"
           "- it states what has been adjusted for, before any number\n"
           "- it has a section headed **what we are not saying**, because the "
           "first thing a GP will assume is that they are being accused of "
           "prescribing badly\n"
           "- it offers a route OFF the list, permanently, if there is an "
           "explanation the data cannot see. A list that practices cannot get off "
           "is a list they stop answering.")
    d.table(p, pd.DataFrame({"": rep.split("\n")}).head(60),
            "outputs/practice_report_example.md")

    out = d.render(ROOT / "dashboard" / "index.html")
    print(f"  {out}")
    con.close()


if __name__ == "__main__":
    main()
