import pandas as pd


def clean_census_number(series: pd.Series) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce")

    # Census uses negative sentinel values for missing/unavailable data.
    values = values.mask(values < 0)

    return values