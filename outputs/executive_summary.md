# Executive Summary
## Prescribing Variation and Medicines Optimisation

**To:** ICB Medicines Optimisation Board  
**From:** Data Analysis  
**Period:** 36 months to December 2025  
**Population:** 6,300 GP practices, 53,407,302 registered patients, 8,799,337 prescribing rows across six BNF sections

---

### 1. The problem with how we currently target practices

We rank practices on prescribing rate and engage the top of the list.

That ranking correlates **r = +0.73** with the share of a
practice's patients aged over 65, and **r = +0.64** with recorded
hypertension prevalence. It is substantially a ranking of how old and how
sick the registered population is.

The consequence is not neutral. Roughly half the practices we contact are
prescribing entirely appropriately for the patients they have. Each of
those conversations costs credibility, and the next letter is read with
less attention than the last.

### 2. What adjusting for need does

Indirect age-sex standardisation asks a different question: how many items
would we EXPECT this practice to issue, given the age and sex of the people
actually registered with it? The ratio of observed to expected is the
Standardised Prescribing Ratio, where 100 means exactly as expected.

| | Correlation with % aged 65+ |
|---|---:|
| Crude items per 1,000 patients | **+0.73** |
| Standardised prescribing ratio | **+0.00** |

The association with age is removed entirely. What remains is the variation
worth a conversation.

### 3. Which practices are genuinely unusual

A ranked table cannot tell you. It has no way of saying how far from the
average a practice has to be before the gap means something. A funnel plot
does: it sets control limits from the variation that ordinary differences
between practices, plus chance, would produce.

| | Practices |
|---|---:|
| Outside 95% control limits | 477 |
| Outside 99.8% control limits | **108** |
| Of those, prescribing MORE than expected | 77 |
| Of those, prescribing LESS than expected | 31 |

**The practices prescribing less matter too.** Under-prescribing of
secondary prevention is a patient safety question, not a savings one, and
a savings-led report that only looks upwards will miss it every time.

### 4. Does the method actually work?

The analysis was validated against a dataset in which 95 practices were
known in advance to be genuinely unusual. Neither method was told which.

| Method | Practices flagged | Genuinely unusual | Precision | Recall |
|---|---:|---:|---:|---:|
| League table, top and bottom 95 | 95 | 44 | 46% | 46% |
| League table, top and bottom 200 | 200 | 50 | 25% | 53% |
| Funnel plot, outside 95% limits | 477 | 92 | 19% | 97% |
| Funnel plot, outside 99.8% limits | 108 | 71 | 66% | 75% |

At comparable workload - 95 practices against
108 - the funnel plot is **66%**
precise against the league table's **46%**.

In operational terms: **27 more real problems found**, and
**14 fewer conversations with practices that are prescribing correctly**, for
the same amount of pharmacist time.

**Which threshold to use is a judgement about consequences, not
statistics.** The 99.8% list is the right basis for contacting a practice,
because the cost of being wrong is a damaged relationship. The 95% list
(477 practices, 97% recall) is
the right basis for an internal watchlist, where the cost of being wrong is
only our own time. That choice should be made deliberately rather than by
whichever threshold the software defaults to.

### 5. Where the money is

**Generic switching**

| Chemical | Generic rate | Branded items | Price gap per item | Opportunity |
|---|---:|---:|---:|---:|
| Atorvastatin | 99.4% | 567,880 | GBP 20.25 | GBP 11,500,096 |
| Rosuvastatin | 97.2% | 432,923 | GBP 23.12 | GBP 10,008,098 |
| Ezetimibe | 96.0% | 305,843 | GBP 24.20 | GBP 7,400,581 |
| Simvastatin | 99.5% | 216,367 | GBP 17.68 | GBP 3,824,809 |

Gross over 36 months: **GBP 32,733,584**. At an
**80% achievable switch rate**: GBP 26,186,867, or
**GBP 8,728,956 a year**.

Note what the table shows: generic rates are already above 95% everywhere.
This looks like a solved problem and is still worth having, because the
price gap per item is twenty-fold. Small residues of expensive branded
prescribing are where the remaining money is.

**Low-priority prescribing**

Total over 36 months: GBP 125,850,653, concentrated in
**1,012 practices (16%)**
which account for half of it. Concentration is what turns a national
problem into a workload: this is a conversation with a defined list, not a
campaign.

**This figure should not go into a business case as it stands.** See the
calibration note in section 7.

**Antimicrobial stewardship**

- Broad-spectrum share of antibacterial items: median 8.9%, 90th percentile 13.1%
- **2,191 practices (35%)** are above the 10% target
- This is a separate behaviour from antibiotic VOLUME. A practice can
  prescribe few antibiotics and still reach for the broad one, and the two
  need different conversations.

### 6. What we are asking practices for

A one-page report per flagged practice, template at
`outputs/practice_report_example.md`. Three design decisions in it, all
aimed at making the conversation possible rather than defensive:

1. It states what has been adjusted for **before** any number.
2. It has a section headed **what we are not saying**, because the first
   thing a GP will assume is that they are being accused of prescribing
   badly.
3. It offers a route **off** the list, permanently, if there is an
   explanation the data cannot see. A list practices cannot get off is a
   list they stop answering.

### 7. What this analysis does NOT adjust for

This section is deliberately as prominent as the findings.

- **Only age and sex are standardised.** Deprivation, recorded disease
  prevalence and local service configuration are not.
- **A specialist clinic, a nursing home on the list, or a service provided
  on behalf of neighbouring practices** would each explain a high ratio
  entirely, and none of them is visible in prescribing data.
- **Practice mergers, closures and code changes** are not modelled.
- **Calibration gap:** low-priority items are 13.5% of spend in this extract against 1-2%
  nationally. The individual products are costed realistically; the six
  sections around them are under-weighted, which inflates the share. The
  low-priority opportunity figure is a demonstration of method, not a
  business case. The funnel-plot and generic-switching findings do not
  depend on it.

Every one of these is a reason a flagged practice might be entirely
correct, and every one of them is in the practice-level report as well as
here.

### 8. Next steps

1. **Engage the 108 practices outside the 99.8%
   limits**, using the one-page report. Record every explanation given.
2. **Add deprivation and QOF prevalence to the standardisation.** Both are
   already joined in the model; the analysis stopped at age and sex
   deliberately so the effect of each adjustment stays visible.
3. **Run the generic switching list first.** It needs no clinical
   conversation at all in most cases and it is the fastest return.
4. **Treat the under-prescribers as a separate workstream** with clinical
   rather than financial leadership.
5. **Re-run quarterly.** Everything here is reproducible from code; the
   point of building it this way is that it does not need commissioning
   again.

---

*Method and code: see README.md. Measure definitions follow OpenPrescribing
and the NHS England low-priority list. Figures in this build come from a
synthetic dataset with the NHSBSA English Prescribing Dataset schema;
src/01_extract_nhsbsa.py is the live extractor and every downstream file
runs unchanged against real data.*