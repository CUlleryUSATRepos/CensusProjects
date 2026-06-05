import os

from census import Census
from dotenv import load_dotenv


def get_census_client(year: int) -> Census:
    load_dotenv()

    api_key = os.getenv("CENSUS_API_KEY")

    if not api_key:
        raise ValueError(
            "No Census API key found. Add CENSUS_API_KEY=your_key_here to your .env file."
        )

    return Census(api_key, year=year)