This project ranks Pennsylvania municipalities using 2024 American Community Survey 5-year Data Profile estimates.

Primary ranking variable:
DP03_0061PE — Percent of households with income of $200,000 or more.

Context variable:
DP03_0062E — Median household income.
DP03_0062M — Margin of error for median household income.

Geography:
Pennsylvania county subdivisions, which include townships, boroughs, cities and other municipal-level Census geographies.

The `county` column is kept as a writing-friendly county name, such as "Bucks County."
The Census geography IDs are stored separately as `state_fips`, `county_fips` and `county_subdivision_fips`.