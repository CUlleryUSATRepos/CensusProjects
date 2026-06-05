from pathlib import Path
import sys

import pandas as pd

# Add project root to Python path so this script can import census_tools
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))

from census_tools.client import get_census_client


ACS_YEAR = 2024
PA_STATE_FIPS = "42"


def main():
    c = get_census_client(year=ACS_YEAR)

    rows = c.acs5dp.get(
        ("NAME", "DP03_0062E"),
        {
            "for": "county:*",
            "in": f"state:{PA_STATE_FIPS}",
        },
    )

    df = pd.DataFrame(rows)

    print("Census API key works.")
    print(f"ACS year: {ACS_YEAR}")
    print(f"Rows returned: {len(df)}")
    print()
    print(df.head())


if __name__ == "__main__":
    main()