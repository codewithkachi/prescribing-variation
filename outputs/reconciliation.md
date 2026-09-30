# Reconciliation

## Control totals, source to model

| Check | Source | Model | Status |
|---|---:|---:|---|
| Prescribing rows | 8,799,337 | 8,799,337 | tie |
| Items | 627,731,229 | 627,731,229 | tie |
| Actual cost | GBP 931,413,885 | GBP 931,413,885 | tie |
| Practices | 6,300 | 6,300 | tie |
| Practices with a list size | 6,300 | 6,300 | tie |
| Practices with QOF data | 6,300 | 6,300 | tie |
| Prescribing rows with no matching BNF code | 0 | 0 | tie |

## Derived measures, sense-checked against published England figures

| Measure | This extract | Published England | Assessment |
|---|---:|---|---|
| Items per patient per year | 3.9 | ~20 across ALL BNF chapters | lower, as expected for six sections |
| Cost per patient per year | GBP 5.81 | ~GBP 150 across ALL chapters | lower, as expected |
| Registered patients | 53,407,302 | ~62m in England | same order |
| GP practices | 6,300 | ~6,300 | tie |
| Broad-spectrum antibacterial share | 8.9% | ~9%, target below 10% | tie |
| Generic prescribing rate, statins | 99.4% | above 99% | tie |

## The one that does NOT reconcile

| Measure | This extract | Published England |
|---|---:|---|
| Low-priority share of spend | **13.5%** | 1-2% |

The individual low-priority products are costed and volumed realistically -
liothyronine at roughly GBP 128 an item and 188,000 items a year is close
to the real national picture before price controls. The problem is the
denominator: the six BNF sections around them are under-weighted in the
generator, so the SHARE is inflated roughly eight-fold.

**Consequence, stated plainly.** The low-priority opportunity figure in the
executive summary is a demonstration of method, not a number to put in a
business case. The funnel-plot findings, the standardisation, the method
validation and the generic-switching opportunity are all unaffected,
because none of them uses the low-priority denominator.

A figure that flatters the analysis is exactly the one to flag before
somebody else does.

## Method validation

Unusually for this kind of work, the method itself can be checked: 95
practices were given a genuine prescribing-style effect by the generator
and held in a separate file that no analysis script reads.

| Method | Flagged | Genuine | Precision | Recall |
|---|---:|---:|---:|---:|
| League table, top and bottom 95 | 95 | 44 | 46% | 46% |
| League table, top and bottom 200 | 200 | 50 | 25% | 53% |
| Funnel plot, outside 95% limits | 477 | 92 | 19% | 97% |
| Funnel plot, outside 99.8% limits | 108 | 71 | 66% | 75% |

On real data this check is impossible, which is the strongest argument for
building a synthetic layer with known ground truth alongside the real
pipeline rather than instead of it.

## Reproducibility

Fixed seed (4041). `python src/01b_generate_data.py && python
src/02_analysis.py && python src/03_report.py` reproduces every figure in
this repository in about two minutes.