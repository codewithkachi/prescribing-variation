-- ===========================================================================
-- Project 4 / 01_model.sql
-- Build the analytical model over the filtered prescribing extract.
--
-- ONE RULE RUNS THROUGH THIS ENTIRE FILE: never a raw count.
-- Practice list sizes here run from 586 to 48,000 patients. A raw item count
-- ranks practices by size and tells you nothing. Everything below is either a
-- rate per 1,000 patients or, better, a rate per prescribing unit that already
-- accounts for age and sex.
--
-- MEASURE DEFINITIONS ARE ADOPTED, NOT INVENTED.
-- The generic-switching, low-priority and antimicrobial measures follow the
-- definitions published by the Bennett Institute's OpenPrescribing project and
-- NHS England's "items which should not routinely be prescribed in primary
-- care" list. Where a published definition exists, using it is not laziness -
-- it is what makes your number comparable to everybody else's, and it is the
-- difference between a finding and an argument about methodology.
-- ===========================================================================

-- --- practice-month totals for the sections in scope -----------------------
CREATE OR REPLACE TABLE fct_practice_month AS
SELECT
    p.year_month,
    p.practice_code,
    b.bnf_section,
    SUM(p.items)                                              AS items,
    SUM(p.actual_cost)                                        AS actual_cost,
    SUM(p.nic)                                                AS nic,
    SUM(CASE WHEN b.is_generic = 1 THEN p.items ELSE 0 END)   AS generic_items,
    SUM(CASE WHEN b.is_generic = 0 THEN p.items ELSE 0 END)   AS branded_items,
    SUM(CASE WHEN b.is_generic = 0 THEN p.actual_cost ELSE 0 END)
                                                              AS branded_cost,
    SUM(CASE WHEN b.is_low_priority = 1 THEN p.items ELSE 0 END)
                                                              AS low_priority_items,
    SUM(CASE WHEN b.is_low_priority = 1 THEN p.actual_cost ELSE 0 END)
                                                              AS low_priority_cost,
    SUM(CASE WHEN b.is_broad_spectrum = 1 THEN p.items ELSE 0 END)
                                                              AS broad_spectrum_items
FROM prescribing p
JOIN bnf b ON b.bnf_code = p.bnf_code
GROUP BY 1, 2, 3;


-- --- the practice dimension, with need attached ----------------------------
CREATE OR REPLACE TABLE dim_practice AS
SELECT
    r.practice_code, r.practice_name, r.region, r.icb_code, r.imd_decile,
    l.total_patients, l.pct_over_65,
    q.qof_chd_prevalence, q.qof_diabetes_prevalence,
    q.qof_depression_prevalence, q.qof_hypertension_prevalence,
    -- Deprivation quintile is the unit commissioners actually use.
    CASE WHEN r.imd_decile <= 2 THEN 1 WHEN r.imd_decile <= 4 THEN 2
         WHEN r.imd_decile <= 6 THEN 3 WHEN r.imd_decile <= 8 THEN 4
         ELSE 5 END                                           AS imd_quintile,
    -- Size band, used only for presentation. Analysis never bands the
    -- denominator, because banding is how small-practice noise gets smuggled
    -- back into a comparison.
    CASE WHEN l.total_patients <  3000 THEN 'a. under 3k'
         WHEN l.total_patients <  6000 THEN 'b. 3-6k'
         WHEN l.total_patients < 10000 THEN 'c. 6-10k'
         WHEN l.total_patients < 20000 THEN 'd. 10-20k'
         ELSE                               'e. 20k+' END     AS list_size_band
FROM practice_reference r
JOIN practice_list_size l USING (practice_code)
JOIN qof_prevalence     q USING (practice_code);


-- --- practice totals over the whole period ---------------------------------
-- Twelve months would be enough for the headline measures, but three years is
-- what makes the trend and the "does improvement persist" question answerable.
CREATE OR REPLACE TABLE fct_practice_total AS
SELECT
    f.practice_code,
    f.bnf_section,
    SUM(f.items)                                              AS items,
    SUM(f.actual_cost)                                        AS actual_cost,
    SUM(f.generic_items)                                      AS generic_items,
    SUM(f.branded_items)                                      AS branded_items,
    SUM(f.branded_cost)                                       AS branded_cost,
    SUM(f.low_priority_items)                                 AS low_priority_items,
    SUM(f.low_priority_cost)                                  AS low_priority_cost,
    SUM(f.broad_spectrum_items)                               AS broad_spectrum_items,
    COUNT(DISTINCT f.year_month)                              AS months_active
FROM fct_practice_month f
GROUP BY 1, 2;


-- --- crude rates: the starting point, and the thing the project rejects ----
CREATE OR REPLACE TABLE practice_crude_rates AS
SELECT
    t.practice_code,
    d.practice_name, d.region, d.icb_code, d.imd_decile, d.imd_quintile,
    d.total_patients, d.pct_over_65, d.list_size_band,
    d.qof_chd_prevalence, d.qof_diabetes_prevalence,
    d.qof_depression_prevalence, d.qof_hypertension_prevalence,
    SUM(t.items)                                              AS items,
    SUM(t.actual_cost)                                        AS actual_cost,
    -- items per 1,000 patients per month: the standard NHS expression
    ROUND(1000.0 * SUM(t.items) / d.total_patients / 36.0, 2) AS items_per_1000_per_month,
    ROUND(SUM(t.actual_cost) / d.total_patients, 2)           AS cost_per_patient,
    SUM(t.generic_items)                                      AS generic_items,
    SUM(t.branded_items)                                      AS branded_items,
    SUM(t.branded_cost)                                       AS branded_cost,
    SUM(t.low_priority_items)                                 AS low_priority_items,
    SUM(t.low_priority_cost)                                  AS low_priority_cost,
    SUM(t.broad_spectrum_items)                               AS broad_spectrum_items,
    SUM(CASE WHEN t.bnf_section = '0501' THEN t.items ELSE 0 END)
                                                              AS antibacterial_items
FROM fct_practice_total t
JOIN dim_practice d USING (practice_code)
GROUP BY 1,2,3,4,5,6,7,8,9,10,11,12,13;


-- --- generic switching opportunity -----------------------------------------
-- The measure is per CHEMICAL SUBSTANCE, never per product: the question is
-- whether a practice used the cheap version of a drug it had already decided to
-- prescribe. Comparing across chemicals would just measure formulary choice.
CREATE OR REPLACE TABLE generic_opportunity AS
WITH chem AS (
    SELECT b.chemical_substance,
           SUM(CASE WHEN b.is_generic = 1 THEN p.items ELSE 0 END) AS generic_items,
           SUM(CASE WHEN b.is_generic = 0 THEN p.items ELSE 0 END) AS branded_items,
           SUM(CASE WHEN b.is_generic = 1 THEN p.actual_cost ELSE 0 END)
                                                                    AS generic_cost,
           SUM(CASE WHEN b.is_generic = 0 THEN p.actual_cost ELSE 0 END)
                                                                    AS branded_cost
    FROM prescribing p JOIN bnf b ON b.bnf_code = p.bnf_code
    GROUP BY 1
    HAVING SUM(CASE WHEN b.is_generic = 0 THEN p.items ELSE 0 END) > 0
       AND SUM(CASE WHEN b.is_generic = 1 THEN p.items ELSE 0 END) > 0
)
SELECT
    chemical_substance,
    generic_items, branded_items,
    ROUND(100.0 * generic_items / (generic_items + branded_items), 2)
                                                              AS generic_rate_pct,
    ROUND(generic_cost / NULLIF(generic_items, 0), 2)         AS generic_cost_per_item,
    ROUND(branded_cost / NULLIF(branded_items, 0), 2)         AS branded_cost_per_item,
    ROUND(branded_cost, 0)                                    AS branded_spend,
    -- The full theoretical prize, before any clinical realism is applied.
    ROUND(branded_items * (branded_cost / NULLIF(branded_items, 0)
                           - generic_cost / NULLIF(generic_items, 0)), 0)
                                                              AS gross_opportunity
FROM chem
ORDER BY gross_opportunity DESC;


-- --- monthly national series, for trend and reconciliation -----------------
CREATE OR REPLACE TABLE national_monthly AS
SELECT
    f.year_month,
    f.bnf_section,
    SUM(f.items)                                              AS items,
    SUM(f.actual_cost)                                        AS actual_cost,
    SUM(f.low_priority_cost)                                  AS low_priority_cost,
    SUM(f.generic_items)                                      AS generic_items,
    SUM(f.branded_items)                                      AS branded_items,
    SUM(f.broad_spectrum_items)                               AS broad_spectrum_items,
    SUM(d.total_patients)                                     AS list_size
FROM fct_practice_month f
JOIN dim_practice d USING (practice_code)
GROUP BY 1, 2;
