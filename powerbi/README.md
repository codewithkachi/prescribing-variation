# Rebuilding this in Power BI

The live artefact is `dashboard/index.html`. This is the spec for rebuilding it
natively — with one honest warning up front, because it is the single most important
thing to know before starting.

## Read this before modelling anything

**Do not compute the funnel control limits in DAX.** It is possible, and it is a trap.

The limits depend on τ², the between-practice variance, which is estimated across the
**whole** practice population by DerSimonian–Laird. The moment a user clicks an ICB or
a region slicer, a DAX implementation recomputes τ² over the filtered subset — and the
control limits silently move. A practice that was an outlier nationally stops being one
when you filter to its own ICB, for no reason a clinician could ever be told.

Pre-compute the limits in `src/02_analysis.py` (which already writes
`outputs/tables/funnel_limits.csv` and the per-practice flags), load them as a
disconnected table, and let Power BI do what it is good at: filtering, drill-through
and distribution.

The same warning applies to the standardised ratio itself. Expected counts come from
national age-specific rates; recomputing them inside a filter context gives you a ratio
against the filtered subset's average, which is a different and much less useful
quantity.

## Star schema

```
                    dim_date
                        |
   dim_practice ─── fct_prescribing ─── dim_bnf
        │
        ├── fct_practice_funnel   (1:1, pre-computed SPR and outlier flags)
        └── dim_funnel_limits     (disconnected, for the reference lines)
```

| Table | Grain | Rows |
|---|---|---|
| `fct_prescribing` | practice × month × presentation | 8.8m |
| `fct_practice_funnel` | one practice | 6,300 |
| `dim_practice` | one practice, with list size, IMD, QOF | 6,300 |
| `dim_bnf` | one presentation | 45 |
| `dim_date` | one month | 36 |
| `dim_funnel_limits` | one point on the control-limit curve | 220 |

`dim_practice` carries the need attributes (list size, % over 65, IMD decile, QOF
prevalences) so they can slice everything without a second join.

## Measures

```dax
Items       = SUM ( fct_prescribing[items] )
Cost        = SUM ( fct_prescribing[actual_cost] )
List Size   = SUM ( dim_practice[total_patients] )

-- ALWAYS a rate. A raw item count ranks practices by list size.
Items per 1000 per Month =
DIVIDE ( [Items], [List Size] ) * 1000 / DISTINCTCOUNT ( dim_date[year_month] )

Cost per Patient = DIVIDE ( [Cost], [List Size] )
```

### Standardised ratio — read from the pre-computed table

```dax
Observed Items = SUM ( fct_practice_funnel[observed_items] )
Expected Items = SUM ( fct_practice_funnel[expected_items] )

-- Correct at every level of aggregation, because both numerator and
-- denominator are additive. This is the reason indirect standardisation is
-- used for small areas: SPRs roll up, age-specific rates do not.
SPR = DIVIDE ( [Observed Items], [Expected Items] ) * 100
```

That additivity is worth dwelling on. `SPR` computed this way is correct for one
practice, for a PCN, for an ICB and for England, with no change to the measure. A
"rate per 1,000 patients" measure does not have that property once age structures
differ between the groups being compared.

### Outlier flags

```dax
Outliers 99.8 =
CALCULATE ( DISTINCTCOUNT ( dim_practice[practice_code] ),
            fct_practice_funnel[outside_998] = TRUE )

Outliers High =
CALCULATE ( [Outliers 99.8], fct_practice_funnel[spr] > 100 )

Outliers Low =
CALCULATE ( [Outliers 99.8], fct_practice_funnel[spr] < 100 )
```

Report `Outliers Low` next to `Outliers High` on the front page. Under-prescribing of
secondary prevention is a patient safety question, and a savings-led dashboard that
only looks upwards will miss it every time.

### Savings, with the achievability assumption as a parameter

```dax
Switch Rate = SELECTEDVALUE ( 'Achievable Switch'[Value], 0.80 )

Branded Spend = CALCULATE ( [Cost], dim_bnf[is_generic] = 0 )

Generic Opportunity =
SUMX (
    VALUES ( dim_bnf[chemical_substance] ),
    VAR Branded  = CALCULATE ( [Items], dim_bnf[is_generic] = 0 )
    VAR BCost    = DIVIDE ( CALCULATE ( [Cost], dim_bnf[is_generic] = 0 ), Branded )
    VAR GCost    = DIVIDE ( CALCULATE ( [Cost], dim_bnf[is_generic] = 1 ),
                            CALCULATE ( [Items], dim_bnf[is_generic] = 1 ) )
    RETURN Branded * ( BCost - GCost ) * [Switch Rate]
)
```

`SUMX` over chemical substance is not optional. The opportunity has to be computed
**per chemical** and then summed — the question is whether a practice used the cheap
version of a drug it had already chosen, and averaging cost per item across chemicals
compares statins with antibiotics and produces a meaningless number.

Expose `Achievable Switch` as a what-if parameter defaulting to 80%, so the first
question in the room — *"is that assuming everyone switches?"* — is answered by moving
a slider rather than by rebuilding the model.

## Page layout

| Page | Visuals |
|---|---|
| **ICB overview** | KPI row (practices, items per 1,000, cost per patient, outliers high, outliers low) · SPR distribution histogram · map by ICB |
| **Funnel plot** | Scatter of SPR (y) against expected items (x, **log scale**) with the four pre-computed limit lines as a line-and-scatter combo · slicers for region and ICB that filter the POINTS but not the LIMITS |
| **Savings** | Generic opportunity by chemical · low-priority concentration curve · what-if slider on achievable rate |
| **Trend** | Items per 1,000 by month, small-multipled by BNF section |
| **Practice drill-through** | Everything for one practice, laid out as the one-page report in `outputs/practice_report_example.md` |

## Getting the funnel visual right

Power BI has no native funnel-plot visual, so:

1. Build it as a **scatter chart** with SPR on Y and expected items on X.
2. Set the X axis to **logarithmic**. Expected counts span 8,000 to 500,000; on a
   linear axis 90% of practices sit in the left tenth of the plot.
3. Add the limits as four **analytics-pane constant lines** if you are using the flat
   overdispersion-adjusted limits (they genuinely are near-flat at these counts, so
   constant lines are not an approximation), or as a combined line-and-scatter visual
   if you also want the pure-Poisson comparison.
4. Colour by the outlier flag, not by SPR. A continuous colour scale invites the
   reader to treat 103 as meaningfully different from 99, which is precisely what the
   control limits exist to prevent.
5. **Do not let the region/ICB slicer filter the limit lines.** Put the limits table
   outside the relationship graph so it cannot be filtered by accident.

## One thing to leave out

Resist adding a "rank" column. Somebody will sort by it, screenshot it, and circulate
it, and the entire argument of this analysis is that the ranking is the thing that was
wrong in the first place.
