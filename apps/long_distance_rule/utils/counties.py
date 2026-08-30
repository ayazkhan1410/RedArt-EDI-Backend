"""
County classification for Colorado NEMT long-distance rules.

Populate DESIGNATED_RURAL_COUNTIES from HCPF list / admin config later.
Matching is case-insensitive.
"""

DESIGNATED_RURAL_COUNTIES = frozenset()


def normalize_county(county):
    if county is None:
        return None
    county = str(county).strip()
    return county or None


def resolve_county_type(county, rural_counties=None):
    counties = (
        DESIGNATED_RURAL_COUNTIES
        if rural_counties is None
        else frozenset(rural_counties)
    )
    county = normalize_county(county)
    if county and county.casefold() in {c.casefold() for c in counties}:
        return "DESIGNATED_RURAL"
    return "STANDARD"
