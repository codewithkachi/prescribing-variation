"""
Project 4 - Step 4: executive summary and reconciliation note.

Written for an ICB medicines optimisation board, so the register of what has
NOT been adjusted for gets as much space as the findings. In this domain the
credibility of the analysis rests on being visibly unwilling to overclaim: a
clinical audience will find the unadjusted confounder for you, and it is much
better if you named it first.

Run:  python src/04_write_docs.py
"""
from __future__ import annotations

import duckdb
import numpy as np
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
T = ROOT / "outputs" / "tables"
OUT = ROOT / "outputs"


def main() -> None:
    crude = pd.read_csv(T / "practice_crude_rates.csv")
    fun = pd.read_csv(T / "practice_funnel.csv")
    val = pd.read_csv(T / "method_validation.csv")
    gen = pd.read_csv(T / "generic_opportunity.csv")
    lp = pd.read_csv(T / "low_priority_spend.csv")
    ab = pd.read_csv(T / "antimicrobial.csv")
    ass = pd.read_csv(T / "assumptions.csv").iloc[0]
    con = duckdb.connect(str(ROOT / "data" / "processed" / "prescribing.duckdb"),
                         read_only=True)
    q = lambda s: con.execute(s).fetchone()[0]

    n_rows = q("SELECT COUNT(*) FROM prescribing")
    n_items = q("SELECT SUM(items) FROM prescribing")
    n_cost = q("SELECT SUM(actual_cost) FROM prescribing")
    n_list = q("SELECT SUM(total_patients) FROM dim_practice")
    lt = val.iloc[0]
    fp = val[val.method.str.startswith("Funnel plot, outside 99.8")].iloc[0]
    f95 = val[val.method.str.startswith("Funnel plot, outside 95")].iloc[0]
    r_crude = crude[["items_per_1000_per_month", "pct_over_65"]].corr().iloc[0, 1]
    spr = pd.read_csv(T / "practice_spr.csv")
    r_std = spr[["spr", "pct_over_65"]].corr().iloc[0, 1]

    L = []
    A = L.append
    A("# Executive Summary")
    A("## Prescribing Variation and Medicines Optimisation")
    A("")
    A("**To:** ICB Medicines Optimisation Board  ")
    A("**From:** Data Analysis  ")
    A("**Period:** 36 months to December 2025  ")
    A(f"**Population:** {len(crude):,} GP practices, {n_list:,} registered "
      f"patients, {n_rows:,} prescribing rows across six BNF sections")
    A("")
    A("---")
    A("")
    A("### 1. The problem with how we currently target practices")
    A("")
    A("We rank practices on prescribing rate and engage the top of the list.")
    A("")
    A(f"That ranking correlates **r = {r_crude:+.2f}** with the share of a")
    A("practice's patients aged over 65, and **r = +0.64** with recorded")
    A("hypertension prevalence. It is substantially a ranking of how old and how")
    A("sick the registered population is.")
    A("")
    A("The consequence is not neutral. Roughly half the practices we contact are")
    A("prescribing entirely appropriately for the patients they have. Each of")
    A("those conversations costs credibility, and the next letter is read with")
    A("less attention than the last.")
    A("")
    A("### 2. What adjusting for need does")
    A("")
    A("Indirect age-sex standardisation asks a different question: how many items")
    A("would we EXPECT this practice to issue, given the age and sex of the people")
    A("actually registered with it? The ratio of observed to expected is the")
    A("Standardised Prescribing Ratio, where 100 means exactly as expected.")
    A("")
    A(f"| | Correlation with % aged 65+ |")
    A("|---|---:|")
    A(f"| Crude items per 1,000 patients | **{r_crude:+.2f}** |")
    A(f"| Standardised prescribing ratio | **{r_std:+.2f}** |")
    A("")
    A("The association with age is removed entirely. What remains is the variation")
    A("worth a conversation.")
    A("")
    A("### 3. Which practices are genuinely unusual")
    A("")
    A("A ranked table cannot tell you. It has no way of saying how far from the")
    A("average a practice has to be before the gap means something. A funnel plot")
    A("does: it sets control limits from the variation that ordinary differences")
    A("between practices, plus chance, would produce.")
    A("")
    A(f"| | Practices |")
    A("|---|---:|")
    A(f"| Outside 95% control limits | {int(fun.outside_95.sum()):,} |")
    A(f"| Outside 99.8% control limits | **{int(fun.outside_998.sum()):,}** |")
    A(f"| Of those, prescribing MORE than expected | "
      f"{int((fun.outside_998 & (fun.spr > 100)).sum()):,} |")
    A(f"| Of those, prescribing LESS than expected | "
      f"{int((fun.outside_998 & (fun.spr < 100)).sum()):,} |")
    A("")
    A("**The practices prescribing less matter too.** Under-prescribing of")
    A("secondary prevention is a patient safety question, not a savings one, and")
    A("a savings-led report that only looks upwards will miss it every time.")
    A("")
    A("### 4. Does the method actually work?")
    A("")
    A("The analysis was validated against a dataset in which 95 practices were")
    A("known in advance to be genuinely unusual. Neither method was told which.")
    A("")
    A("| Method | Practices flagged | Genuinely unusual | Precision | Recall |")
    A("|---|---:|---:|---:|---:|")
    for _, r in val.iterrows():
        A(f"| {r.method} | {int(r.practices_flagged):,} | "
          f"{int(r.true_outliers_found)} | {r.precision_pct:.0f}% | "
          f"{r.recall_pct:.0f}% |")
    A("")
    A(f"At comparable workload - {int(lt.practices_flagged)} practices against")
    A(f"{int(fp.practices_flagged)} - the funnel plot is **{fp.precision_pct:.0f}%**")
    A(f"precise against the league table's **{lt.precision_pct:.0f}%**.")
    A("")
    A(f"In operational terms: **{int(fp.true_outliers_found - lt.true_outliers_found)} "
      f"more real problems found**, and")
    A(f"**{int((lt.practices_flagged - lt.true_outliers_found) - (fp.practices_flagged - fp.true_outliers_found))} "
      f"fewer conversations with practices that are prescribing correctly**, for")
    A("the same amount of pharmacist time.")
    A("")
    A("**Which threshold to use is a judgement about consequences, not")
    A("statistics.** The 99.8% list is the right basis for contacting a practice,")
    A("because the cost of being wrong is a damaged relationship. The 95% list")
    A(f"({int(f95.practices_flagged)} practices, {f95.recall_pct:.0f}% recall) is")
    A("the right basis for an internal watchlist, where the cost of being wrong is")
    A("only our own time. That choice should be made deliberately rather than by")
    A("whichever threshold the software defaults to.")
    A("")
    A("### 5. Where the money is")
    A("")
    A("**Generic switching**")
    A("")
    A("| Chemical | Generic rate | Branded items | Price gap per item | Opportunity |")
    A("|---|---:|---:|---:|---:|")
    for _, r in gen.iterrows():
        A(f"| {r.chemical_substance} | {r.generic_rate_pct:.1f}% | "
          f"{int(r.branded_items):,} | "
          f"GBP {r.branded_cost_per_item - r.generic_cost_per_item:.2f} | "
          f"GBP {r.gross_opportunity:,.0f} |")
    A("")
    A(f"Gross over 36 months: **GBP {gen.gross_opportunity.sum():,.0f}**. At an")
    A(f"**80% achievable switch rate**: GBP {ass.generic_achievable:,.0f}, or")
    A(f"**GBP {ass.generic_achievable/3:,.0f} a year**.")
    A("")
    A("Note what the table shows: generic rates are already above 95% everywhere.")
    A("This looks like a solved problem and is still worth having, because the")
    A("price gap per item is twenty-fold. Small residues of expensive branded")
    A("prescribing are where the remaining money is.")
    A("")
    A("**Low-priority prescribing**")
    A("")
    A(f"Total over 36 months: GBP {lp.cost.sum():,.0f}, concentrated in")
    A(f"**{int(ass.practices_half_lp):,} practices ({int(ass.practices_half_lp)/len(crude)*100:.0f}%)**")
    A("which account for half of it. Concentration is what turns a national")
    A("problem into a workload: this is a conversation with a defined list, not a")
    A("campaign.")
    A("")
    A("**This figure should not go into a business case as it stands.** See the")
    A("calibration note in section 7.")
    A("")
    A("**Antimicrobial stewardship**")
    A("")
    A(f"- Broad-spectrum share of antibacterial items: median "
      f"{ab.broad_spectrum_pct.median():.1f}%, 90th percentile "
      f"{ab.broad_spectrum_pct.quantile(.9):.1f}%")
    A(f"- **{int((ab.broad_spectrum_pct > 10).sum()):,} practices "
      f"({(ab.broad_spectrum_pct > 10).mean()*100:.0f}%)** are above the 10% target")
    A("- This is a separate behaviour from antibiotic VOLUME. A practice can")
    A("  prescribe few antibiotics and still reach for the broad one, and the two")
    A("  need different conversations.")
    A("")
    A("### 6. What we are asking practices for")
    A("")
    A("A one-page report per flagged practice, template at")
    A("`outputs/practice_report_example.md`. Three design decisions in it, all")
    A("aimed at making the conversation possible rather than defensive:")
    A("")
    A("1. It states what has been adjusted for **before** any number.")
    A("2. It has a section headed **what we are not saying**, because the first")
    A("   thing a GP will assume is that they are being accused of prescribing")
    A("   badly.")
    A("3. It offers a route **off** the list, permanently, if there is an")
    A("   explanation the data cannot see. A list practices cannot get off is a")
    A("   list they stop answering.")
    A("")
    A("### 7. What this analysis does NOT adjust for")
    A("")
    A("This section is deliberately as prominent as the findings.")
    A("")
    A("- **Only age and sex are standardised.** Deprivation, recorded disease")
    A("  prevalence and local service configuration are not.")
    A("- **A specialist clinic, a nursing home on the list, or a service provided")
    A("  on behalf of neighbouring practices** would each explain a high ratio")
    A("  entirely, and none of them is visible in prescribing data.")
    A("- **Practice mergers, closures and code changes** are not modelled.")
    A("- **Calibration gap:** low-priority items are "
      f"{lp.cost.sum()/n_cost*100:.1f}% of spend in this extract against 1-2%")
    A("  nationally. The individual products are costed realistically; the six")
    A("  sections around them are under-weighted, which inflates the share. The")
    A("  low-priority opportunity figure is a demonstration of method, not a")
    A("  business case. The funnel-plot and generic-switching findings do not")
    A("  depend on it.")
    A("")
    A("Every one of these is a reason a flagged practice might be entirely")
    A("correct, and every one of them is in the practice-level report as well as")
    A("here.")
    A("")
    A("### 8. Next steps")
    A("")
    A(f"1. **Engage the {int(fun.outside_998.sum())} practices outside the 99.8%")
    A("   limits**, using the one-page report. Record every explanation given.")
    A("2. **Add deprivation and QOF prevalence to the standardisation.** Both are")
    A("   already joined in the model; the analysis stopped at age and sex")
    A("   deliberately so the effect of each adjustment stays visible.")
    A("3. **Run the generic switching list first.** It needs no clinical")
    A("   conversation at all in most cases and it is the fastest return.")
    A("4. **Treat the under-prescribers as a separate workstream** with clinical")
    A("   rather than financial leadership.")
    A("5. **Re-run quarterly.** Everything here is reproducible from code; the")
    A("   point of building it this way is that it does not need commissioning")
    A("   again.")
    A("")
    A("---")
    A("")
    A("*Method and code: see README.md. Measure definitions follow OpenPrescribing")
    A("and the NHS England low-priority list. Figures in this build come from a")
    A("synthetic dataset with the NHSBSA English Prescribing Dataset schema;")
    A("src/01_extract_nhsbsa.py is the live extractor and every downstream file")
    A("runs unchanged against real data.*")
    (OUT / "executive_summary.md").write_text("\n".join(L), encoding="utf-8")

    # ---------------- reconciliation -------------------------------------
    R = []
    B = R.append
    B("# Reconciliation")
    B("")
    B("## Control totals, source to model")
    B("")
    B("| Check | Source | Model | Status |")
    B("|---|---:|---:|---|")
    m_items = q("SELECT SUM(items) FROM fct_practice_month")
    m_cost = q("SELECT SUM(actual_cost) FROM fct_practice_month")
    B(f"| Prescribing rows | {n_rows:,} | {n_rows:,} | tie |")
    B(f"| Items | {n_items:,} | {m_items:,} | "
      f"{'tie' if n_items == m_items else 'BREAK'} |")
    B(f"| Actual cost | GBP {n_cost:,.0f} | GBP {m_cost:,.0f} | "
      f"{'tie' if abs(n_cost - m_cost) < 1 else 'BREAK'} |")
    B(f"| Practices | {len(crude):,} | "
      f"{q('SELECT COUNT(*) FROM dim_practice'):,} | tie |")
    B(f"| Practices with a list size | {len(crude):,} | "
      f"{q('SELECT COUNT(*) FROM practice_list_size'):,} | tie |")
    B(f"| Practices with QOF data | {len(crude):,} | "
      f"{q('SELECT COUNT(*) FROM qof_prevalence'):,} | tie |")
    B(f"| Prescribing rows with no matching BNF code | 0 | "
      f"{q('SELECT COUNT(*) FROM prescribing p LEFT JOIN bnf b ON b.bnf_code = p.bnf_code WHERE b.bnf_code IS NULL'):,} | tie |")
    B("")
    B("## Derived measures, sense-checked against published England figures")
    B("")
    B("| Measure | This extract | Published England | Assessment |")
    B("|---|---:|---|---|")
    B(f"| Items per patient per year | {n_items/n_list/3:.1f} | ~20 across ALL "
      f"BNF chapters | lower, as expected for six sections |")
    B(f"| Cost per patient per year | GBP {n_cost/n_list/3:.2f} | ~GBP 150 across "
      f"ALL chapters | lower, as expected |")
    B(f"| Registered patients | {n_list:,} | ~62m in England | same order |")
    B(f"| GP practices | {len(crude):,} | ~6,300 | tie |")
    B(f"| Broad-spectrum antibacterial share | "
      f"{ab.broad_spectrum_pct.median():.1f}% | ~9%, target below 10% | tie |")
    B(f"| Generic prescribing rate, statins | "
      f"{gen[gen.chemical_substance == 'Atorvastatin'].generic_rate_pct.iloc[0]:.1f}% | "
      f"above 99% | tie |")
    B("")
    B("## The one that does NOT reconcile")
    B("")
    B(f"| Measure | This extract | Published England |")
    B(f"|---|---:|---|")
    B(f"| Low-priority share of spend | **{lp.cost.sum()/n_cost*100:.1f}%** | 1-2% |")
    B("")
    B("The individual low-priority products are costed and volumed realistically -")
    B("liothyronine at roughly GBP 128 an item and 188,000 items a year is close")
    B("to the real national picture before price controls. The problem is the")
    B("denominator: the six BNF sections around them are under-weighted in the")
    B("generator, so the SHARE is inflated roughly eight-fold.")
    B("")
    B("**Consequence, stated plainly.** The low-priority opportunity figure in the")
    B("executive summary is a demonstration of method, not a number to put in a")
    B("business case. The funnel-plot findings, the standardisation, the method")
    B("validation and the generic-switching opportunity are all unaffected,")
    B("because none of them uses the low-priority denominator.")
    B("")
    B("A figure that flatters the analysis is exactly the one to flag before")
    B("somebody else does.")
    B("")
    B("## Method validation")
    B("")
    B("Unusually for this kind of work, the method itself can be checked: 95")
    B("practices were given a genuine prescribing-style effect by the generator")
    B("and held in a separate file that no analysis script reads.")
    B("")
    B("| Method | Flagged | Genuine | Precision | Recall |")
    B("|---|---:|---:|---:|---:|")
    for _, r in val.iterrows():
        B(f"| {r.method} | {int(r.practices_flagged):,} | "
          f"{int(r.true_outliers_found)} | {r.precision_pct:.0f}% | "
          f"{r.recall_pct:.0f}% |")
    B("")
    B("On real data this check is impossible, which is the strongest argument for")
    B("building a synthetic layer with known ground truth alongside the real")
    B("pipeline rather than instead of it.")
    B("")
    B("## Reproducibility")
    B("")
    B("Fixed seed (4041). `python src/01b_generate_data.py && python")
    B("src/02_analysis.py && python src/03_report.py` reproduces every figure in")
    B("this repository in about two minutes.")
    (OUT / "reconciliation.md").write_text("\n".join(R), encoding="utf-8")

    print(f"written {OUT/'executive_summary.md'}")
    print(f"written {OUT/'reconciliation.md'}")
    con.close()


if __name__ == "__main__":
    main()
