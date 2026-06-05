from pathlib import Path
import sys

import pandas as pd

# Add project root to Python path so this script can import census_tools
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(PROJECT_ROOT))

from census_tools.client import get_census_client
from census_tools.cleaning import clean_census_number
from census_tools.geography import clean_pa_municipality_name, extract_county_from_name


ACS_YEAR = 2024
PA_STATE_FIPS = "42"

PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


FIELDS = (
    "NAME",
    "DP03_0061PE",  # Percent of households earning $200,000 or more
    "DP03_0061PM",  # MOE for percent of households earning $200,000 or more
    "DP03_0062E",   # Median household income
    "DP03_0062M",   # MOE for median household income
)


def build_municipality_rankings():
    c = get_census_client(year=ACS_YEAR)

    rows = c.acs5dp.get(
        FIELDS,
        {
            "for": "county subdivision:*",
            "in": f"state:{PA_STATE_FIPS}",
        },
    )

    towns = pd.DataFrame(rows)

    towns = towns.rename(
        columns={
            "state": "state_fips",
            "county": "county_fips",
            "county subdivision": "county_subdivision_fips",
        }
    )

    towns["municipality"] = towns["NAME"].apply(clean_pa_municipality_name)

    # Writing-friendly county name, used in story text and lists.
    towns["county"] = towns["NAME"].apply(extract_county_from_name)

    towns["pct_200k_plus"] = clean_census_number(towns["DP03_0061PE"])
    towns["pct_200k_plus_moe"] = clean_census_number(towns["DP03_0061PM"])
    towns["median_income"] = clean_census_number(towns["DP03_0062E"])
    towns["median_income_moe"] = clean_census_number(towns["DP03_0062M"])

    towns["median_income_low"] = towns["median_income"] - towns["median_income_moe"]
    towns["median_income_high"] = towns["median_income"] + towns["median_income_moe"]

    analysis = towns.dropna(
        subset=[
            "pct_200k_plus",
            "median_income",
            "median_income_moe",
        ]
    ).copy()

    analysis = analysis.sort_values("pct_200k_plus", ascending=False)
    analysis["state_rank"] = analysis["pct_200k_plus"].rank(
        method="min",
        ascending=False
    ).astype(int)

    return analysis


def build_county_income_rankings():
    c = get_census_client(year=ACS_YEAR)

    rows = c.acs5dp.get(
        ("NAME", "DP03_0062E", "DP03_0062M"),
        {
            "for": "county:*",
            "in": f"state:{PA_STATE_FIPS}",
        },
    )

    counties = pd.DataFrame(rows)

    counties = counties.rename(
        columns={
            "state": "state_fips",
            "county": "county_fips",
        }
    )

    # Writing-friendly county name, used in story text and lists.
    counties["county"] = counties["NAME"].str.replace(", Pennsylvania", "", regex=False)

    counties["median_income"] = clean_census_number(counties["DP03_0062E"])
    counties["median_income_moe"] = clean_census_number(counties["DP03_0062M"])
    counties["median_income_low"] = counties["median_income"] - counties["median_income_moe"]
    counties["median_income_high"] = counties["median_income"] + counties["median_income_moe"]

    counties = counties.dropna(subset=["median_income"]).copy()
    counties = counties.sort_values("median_income", ascending=False)
    counties["state_county_income_rank"] = counties["median_income"].rank(
        method="min",
        ascending=False
    ).astype(int)

    return counties


def main():
    analysis = build_municipality_rankings()
    counties = build_county_income_rankings()

    top_10_pa = analysis.head(10).copy()
    top_50_pa = analysis.head(50).copy()
    bucks = analysis[analysis["county"] == "Bucks County"].copy()
    top_10_bucks = bucks.head(10).copy()

    county_counts_top_50 = (
        top_50_pa.groupby("county")
        .size()
        .reset_index(name="towns_in_top_50")
        .sort_values("towns_in_top_50", ascending=False)
    )

    analysis.to_csv(OUTPUT_DIR / "pa_municipal_income_rankings.csv", index=False)
    top_10_pa.to_csv(OUTPUT_DIR / "top_10_pa_wealthiest_towns.csv", index=False)
    top_50_pa.to_csv(OUTPUT_DIR / "top_50_pa_wealthiest_towns.csv", index=False)
    top_10_bucks.to_csv(OUTPUT_DIR / "top_10_bucks_wealthiest_towns.csv", index=False)
    county_counts_top_50.to_csv(OUTPUT_DIR / "county_counts_in_top_50.csv", index=False)
    counties.to_csv(OUTPUT_DIR / "pa_county_median_income_rankings.csv", index=False)

    with pd.ExcelWriter(OUTPUT_DIR / "acs_income_story_outputs.xlsx") as writer:
        top_10_pa.to_excel(writer, sheet_name="Top 10 PA", index=False)
        top_10_bucks.to_excel(writer, sheet_name="Top 10 Bucks", index=False)
        top_50_pa.to_excel(writer, sheet_name="Top 50 PA", index=False)
        county_counts_top_50.to_excel(writer, sheet_name="Top 50 by County", index=False)
        counties.to_excel(writer, sheet_name="County Median Income", index=False)
        analysis.to_excel(writer, sheet_name="All Municipalities", index=False)

    print("Done.")
    print(f"ACS year: {ACS_YEAR}")
    print(f"Pennsylvania municipalities analyzed: {len(analysis):,}")
    print(f"Bucks County municipalities analyzed: {len(bucks):,}")
    print()
    print("Top 10 PA:")
    print(
        top_10_pa[
            [
                "state_rank",
                "municipality",
                "county",
                "pct_200k_plus",
                "median_income_low",
                "median_income_high",
            ]
        ]
    )
    print()
    print("Top 10 Bucks:")
    print(
        top_10_bucks[
            [
                "state_rank",
                "municipality",
                "county",
                "pct_200k_plus",
                "median_income_low",
                "median_income_high",
            ]
        ]
    )


if __name__ == "__main__":
    main()