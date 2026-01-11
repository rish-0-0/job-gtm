-- Normalize all salaries to USD
-- This query converts salaries from various currencies to USD
-- It's idempotent - only processes rows that haven't been normalized (currency_conversion_date IS NULL)
--
-- SPECIAL HANDLING FOR INDIAN SALARIES:
-- Indian salaries are in monthly rupees. This query:
-- 1. Updates min_salary_raw and max_salary_raw: multiplies by 12 (monthly → annual INR)
-- 2. Updates min_salary_usd and max_salary_usd: divides by 80 (annual INR → annual USD)
-- Example: 25,000 INR/month → 300,000 INR/year → $3,750 USD/year

-- Exchange rates (approximate, as of 2024)
-- INR to USD: 1 USD = ~80 INR (for Indian salaries: multiply by 12 first, then divide by 80)
-- EUR to USD: 1 USD = ~0.92 EUR
-- GBP to USD: 1 USD = ~0.79 GBP
-- CAD to USD: 1 USD = ~1.36 CAD
-- AUD to USD: 1 USD = ~1.52 AUD
-- SGD to USD: 1 USD = ~1.35 SGD

WITH currency_rates AS (
    SELECT 'INR' AS currency, 80.0 AS rate_to_usd, true AS is_monthly
    UNION ALL SELECT 'USD', 1.0, false
    UNION ALL SELECT 'EUR', 0.92, false
    UNION ALL SELECT 'GBP', 0.79, false
    UNION ALL SELECT 'CAD', 1.36, false
    UNION ALL SELECT 'AUD', 1.52, false
    UNION ALL SELECT 'SGD', 1.35, false
    UNION ALL SELECT 'JPY', 149.0, false
    UNION ALL SELECT 'CNY', 7.24, false
),
-- Detect currency from raw data or location if currency_raw is not set
detected_currency AS (
    SELECT
        id,
        CASE
            -- If currency_raw is already set and valid, use it
            WHEN currency_raw IN ('INR', 'USD', 'EUR', 'GBP', 'CAD', 'AUD', 'SGD', 'JPY', 'CNY') THEN currency_raw
            -- If currency_raw looks like array notation, extract it
            WHEN currency_raw LIKE '{%}' THEN TRIM(BOTH '{}' FROM currency_raw)
            -- Detect from location_country
            WHEN location_country IN ('India', 'india') THEN 'INR'
            WHEN location_country IN ('USA', 'United States', 'US', 'United States of America') THEN 'USD'
            WHEN location_country IN ('UK', 'United Kingdom', 'England', 'Scotland', 'Wales', 'Great Britain') THEN 'GBP'
            WHEN location_country IN ('Canada') THEN 'CAD'
            WHEN location_country IN ('Australia') THEN 'AUD'
            WHEN location_country IN ('Singapore') THEN 'SGD'
            WHEN location_country IN ('Japan') THEN 'JPY'
            WHEN location_country IN ('China') THEN 'CNY'
            -- Check for currency symbols in salary_range_raw
            WHEN salary_range_raw LIKE '%₹%' OR salary_range_raw LIKE '%Rs%' OR salary_range_raw LIKE '%INR%' THEN 'INR'
            WHEN salary_range_raw LIKE '%$%' OR salary_range_raw LIKE '%USD%' THEN 'USD'
            WHEN salary_range_raw LIKE '%€%' OR salary_range_raw LIKE '%EUR%' THEN 'EUR'
            WHEN salary_range_raw LIKE '%£%' OR salary_range_raw LIKE '%GBP%' THEN 'GBP'
            -- Default to USD if we can't determine
            ELSE 'USD'
        END AS detected_currency
    FROM job_listings_golden
    WHERE enrichment_status = 'completed'
      AND min_salary_raw IS NOT NULL
      -- Only process rows that haven't been normalized yet
      AND currency_conversion_date IS NULL
)
UPDATE job_listings_golden
SET
    -- Update raw salary fields for Indian jobs (monthly to annual)
    min_salary_raw = CASE
        WHEN dc.detected_currency = 'INR' AND cr.is_monthly = true
        THEN job_listings_golden.min_salary_raw * 12
        ELSE job_listings_golden.min_salary_raw
    END,
    max_salary_raw = CASE
        WHEN dc.detected_currency = 'INR' AND cr.is_monthly = true
        THEN job_listings_golden.max_salary_raw * 12
        ELSE job_listings_golden.max_salary_raw
    END,
    -- For Indian salaries (monthly in INR): multiply by 12 to get annual, then divide by rate
    -- For other currencies: just divide by rate
    min_salary_usd = ROUND(
        CASE
            WHEN dc.detected_currency = 'INR' AND cr.is_monthly = true
            THEN (job_listings_golden.min_salary_raw * 12) / cr.rate_to_usd
            ELSE job_listings_golden.min_salary_raw / cr.rate_to_usd
        END, 2
    ),
    max_salary_usd = ROUND(
        CASE
            WHEN dc.detected_currency = 'INR' AND cr.is_monthly = true
            THEN (job_listings_golden.max_salary_raw * 12) / cr.rate_to_usd
            ELSE job_listings_golden.max_salary_raw / cr.rate_to_usd
        END, 2
    ),
    currency_conversion_rate = cr.rate_to_usd,
    currency_conversion_date = NOW(),
    -- Update currency_raw if it was null or malformed
    currency_raw = CASE
        WHEN job_listings_golden.currency_raw IS NULL OR job_listings_golden.currency_raw LIKE '{%}'
        THEN dc.detected_currency
        ELSE job_listings_golden.currency_raw
    END,
    updated_at = NOW()
FROM detected_currency dc
JOIN currency_rates cr ON cr.currency = dc.detected_currency
WHERE job_listings_golden.id = dc.id;

-- Return statistics
SELECT
    'Salary normalization complete' AS status,
    COUNT(*) AS rows_updated
FROM job_listings_golden
WHERE enrichment_status = 'completed'
  AND min_salary_raw IS NOT NULL
  AND currency_conversion_date IS NOT NULL
  AND DATE(currency_conversion_date) = CURRENT_DATE;
