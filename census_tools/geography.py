def clean_pa_municipality_name(name: str) -> str:
    """
    Converts:
    'Upper Makefield township, Bucks County, Pennsylvania'
    into:
    'Upper Makefield'
    """
    first_part = name.split(",")[0].strip()

    suffixes = [
        " township",
        " borough",
        " city",
        " town",
        " municipality",
    ]

    cleaned = first_part

    for suffix in suffixes:
        if cleaned.lower().endswith(suffix):
            cleaned = cleaned[: -len(suffix)]

    return cleaned.strip()


def extract_county_from_name(name: str) -> str | None:
    """
    Converts:
    'Upper Makefield township, Bucks County, Pennsylvania'
    into:
    'Bucks County'
    """
    parts = [part.strip() for part in name.split(",")]

    if len(parts) >= 2:
        return parts[1]

    return None