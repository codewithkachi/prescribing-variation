# Prescribing Variation and Medicines Optimisation
### Finding unwarranted variation across 6,300 GP practices

**Sector:** Healthcare · **Level:** Intermediate/Advanced · **Modelling:** none

> Some practices prescribe several times as much as others. Much of that is entirely
> appropriate — an older, more deprived population needs more medicine. Medicines
> optimisation teams either ignore the variation, or write to practices that turn out
> to be prescribing correctly, which ends the working relationship and gets the next
> letter binned.

**[→ Open the live dashboard](https://onyekaogbonna.com/dashboards/prescribing/)** · [case study](https://onyekaogbonna.com/projects/prescribing-variation.html)

---

## The headline

| | |
|---|---|
| Scale | 6,300 practices · 8.8m prescribing rows · 36 months · six BNF sections |
| Crude rate vs % patients aged 65+ | **r = +0.73** — the league table ranks population age |
| After indirect standardisation | **r = +0.00** |
| Practices outside 99.8% funnel limits | **111** |
| Precision at comparable workload | **65%** funnel vs **47%** league table |
| Net effect | 27 more real problems found, 11 fewer wasted conversations |

---

## Four findings

**1. The league table is a ranking of population age.**
Crude items per 1,000 patients correlates **+0.73** with the share of patients over 65
and **+0.64** with recorded hypertension prevalence. Rank on it and write to the top
and roughly half your letters go to practices prescribing appropriately for the
patients they actually have.

**2. Indirect age-sex standardisation removes the association completely.**
r falls from +0.73 to **+0.00**. The STAR-PU weights fall straight out of the same
calculation, and they show why one prescribing unit cannot serve every drug group: a
75-year-old is worth ~3.6 average patients for statins and ~1.2 for antibiotics.

**3. The funnel plot finds the right practices; the league table finds a mixture.**
95 practices were given a genuine prescribing-style effect by the generator. Neither
method was told which.

| Method | Flagged | Genuine | Precision | Recall |
|---|---:|---:|---:|---:|
| League table, top+bottom 95 | 95 | 45 | 47% | 47% |
| League table, top+bottom 200 | 200 | 49 | 25% | 52% |
| Funnel, outside 95% | 471 | 92 | 20% | **97%** |
| **Funnel, outside 99.8%** | **111** | **72** | **65%** | **76%** |

**4. Low-priority prescribing is concentrated, which is what makes it actionable.**
**16% of practices** account for half of all low-priority spend. That is a
conversation with a defined list, not a national campaign.

---

## Where this project departs from the textbook, and why that is the point

### The usual justification for funnel plots does not apply here

Every account of funnel plots says the problem with a league table is that **small**
units sit at both extremes, because small denominators carry more sampling variation.
I set out to demonstrate that. **It is barely true on this data**, and understanding
why is more useful than repeating the rule.

| Measure | Median count per practice | Poisson CV | Share of ranking extremes that are small practices |
|---|---:|---:|---:|
| All six sections | 81,372 | 0.4% | 22% |
| Low-priority items | 403 | 5.0% | 29% |
| Liothyronine only | 57 | 13.2% | 32% |

25% is the no-effect baseline. On the headline measure the effect is absent — the
counts are far too large for sampling noise to matter. It appears on liothyronine,
where a practice may issue a handful of items in three years.

So the league table here fails for a **different** reason: it measures the population,
not the prescriber.

### The overdispersion adjustment is needed for the opposite reason to the textbook one

Pure Poisson limits at these counts are about **half a percent wide** and flag **97%
of England**. That is not a subtle failure — it is the method announcing that its
assumption is wrong. Practices genuinely differ far more than chance allows.

Estimating the real between-practice variance (DerSimonian–Laird, τ² = 0.022) and
adding it to the sampling variance brings that to 471 at 95% and 111 at 99.8%.

**A first attempt got this wrong**, and the write-up keeps it. Using the
variance-stabilised form with Winsorising at the 10th/90th percentiles returned a τ²
six times too small and flagged 45% of practices. Clipping at 10/90 is far too
aggressive when ordinary variation is itself large — most of what was being trimmed
was signal, not contamination. The self-check that caught it (compare τ̂² against the
observed variance of the ratios minus the average sampling variance) is printed in the
analysis output.

### A consequence worth showing rather than hiding: the funnel is not funnel-shaped

Once τ² dominates 1/E — by a factor of ~1,500 here — the control limits are two almost
straight lines. That is correct, and it means practice size is genuinely irrelevant to
whether a practice is unusual on this measure.

`outputs/charts/10_funnel_shapes.png` shows liothyronine under both assumptions: the
classic funnel shape on the left (flagging 3,943 practices, 66% of England) and the
honest limits on the right (flagging 205). **The textbook shape comes entirely from
assuming away real variation.**

### One modelling failure, diagnosed rather than patched

Recovering national age-specific rates from practice-level aggregates by non-negative
least squares on 18 band-population columns returns nonsense: a spiky vector, mostly
exact zeros, implying men under 75 use no antibiotics at all. The cause is
collinearity — every practice's band populations are nearly proportional to its list
size, so the columns carry the same information and individual coefficients are not
identifiable.

The fix is to stop asking for 18 free parameters and ask for a **shape**: a
three-parameter log-linear age-sex model, comfortably identifiable from 6,300
practices. The result is stable and looks like a published prescribing unit — which is
the point, because that is what published prescribing units are.

---

## The extraction, which is the other half of the skill

[`src/01_extract_nhsbsa.py`](src/01_extract_nhsbsa.py) is a **real, working extractor**
against the NHSBSA Open Data Portal. It discovers monthly resource ids, sends the
filter to the API as SQL, paginates, and writes Parquet.

The filter is the point. EPD adds ~17 million rows a month and three years is roughly
600 million. This analysis needs six BNF sections plus one published list, which cuts
it to roughly 150,000 rows a month — a factor of over a hundred.

```
WRONG:  download every month in full, then filter in pandas
RIGHT:  send the filter to the API, download only the rows you need
```

That judgement is what makes the project run on a laptop.

---

## How to run it

```bash
pip install -r requirements.txt
```

```bash
python src/01b_generate_data.py && python src/02_analysis.py && python src/03_report.py
```

About two minutes end to end.

| Step | File | What it does |
|---|---|---|
| 1 | `src/01_extract_nhsbsa.py` | Live NHSBSA API extractor with server-side filtering |
| 1b | `src/01b_generate_data.py` | Offline generator, identical schema (~10s) |
| 2 | `src/02_analysis.py` | Standardisation, STAR-PU, funnel plots, validation, savings (~60s) |
| 3 | `src/03_report.py` | Ten charts, dashboard, practice report template (~20s) |

[`sql/01_model.sql`](sql/01_model.sql) holds the model: practice-month aggregation,
the need dimension, crude rates, and the generic-switching opportunity computed **per
chemical substance** rather than per product — because the question is whether a
practice used the cheap version of a drug it had already chosen, not which drug it
chose.

---

## About the data

Figures in this build come from a **synthetic dataset with the NHSBSA EPD schema**.
Drop real extracts into `data/raw/` and everything downstream runs unchanged.

Real even though the data is synthetic: BNF codes, sections and chemical substance
names; the generic/branded product pairs; NHS England's low-priority list; practice
counts and list-size distribution; the age-sex bands used for STAR-PU construction.
Measure definitions follow OpenPrescribing rather than being invented.

**One calibration gap, flagged rather than buried.** Low-priority items are **13.2%**
of spend in this extract against 1–2% nationally. The individual products are costed
realistically; the six sections around them are under-weighted, which inflates the
share. The low-priority *opportunity* figure is therefore a demonstration of method,
not a number for a business case. The funnel-plot and generic-switching findings do
not depend on it.

| Check | Result |
|---|---|
| Source items → model items | 636,233,742 → 636,233,742, tie |
| Source cost → model cost | £955,172,641 → £955,172,641, tie |
| Broad-spectrum share (median) | 8.9% vs ~9% England |
| Practices above the 10% stewardship target | 35% |

---

## Limitations

- Only age and sex are adjusted for. Deprivation, disease prevalence and local service
  configuration are not, and any of them could explain a practice's position. This is
  why the practice report has a section headed *what we are not saying*.
- The savings figures assume 80% achievable generic switching and 70% achievable
  low-priority reduction, **never 100%** — some patients genuinely cannot switch, and
  NHS England's guidance says explicitly that low-priority items may still be right
  for individuals.
- The top-decile scenario is labelled a **scenario, not a saving**. It assumes the
  whole gap above the median is addressable, and some of it will be genuine need.
- Practice mergers, closures and code changes are not modelled here; on real EPD data
  this is fiddly and would need its own section.
- Ground-truth validation is only possible because the data is synthetic.

---

## Deliverables

| | |
|---|---|
| Live dashboard | [`dashboard/index.html`](dashboard/index.html) — 5 pages |
| Executive summary | [`outputs/executive_summary.md`](outputs/executive_summary.md) |
| Reconciliation | [`outputs/reconciliation.md`](outputs/reconciliation.md) |
| Practice report template | [`outputs/practice_report_example.md`](outputs/practice_report_example.md) |
| Live API extractor | [`src/01_extract_nhsbsa.py`](src/01_extract_nhsbsa.py) |
| Power BI rebuild spec | [`powerbi/README.md`](powerbi/README.md) |
| Charts / tables | `outputs/charts` (10) · `outputs/tables` (14) |

## Skills demonstrated

API extraction with server-side filtering · DuckDB over 8.8m rows · indirect age-sex
standardisation · STAR-PU construction from first principles · funnel plots with
DerSimonian–Laird overdispersion adjustment · diagnosing a collinearity failure and
replacing it with an identifiable model · method validation against ground truth ·
savings quantification with clinical realism · writing for a clinical audience
