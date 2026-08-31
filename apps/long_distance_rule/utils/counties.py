"""
County classification for Colorado NEMT long-distance rules.

DESIGNATED_RURAL_COUNTIES sourced from HCPF NEMT Billing Manual
(125-mile daily threshold for members in designated rural counties).
Override via settings EDI_RURAL_COUNTIES (comma-separated) when needed.
Matching is case-insensitive.
"""

from __future__ import annotations

# HCPF NEMT Billing Manual — designated rural counties (125-mile edit).
# Note: manual typo "Sedwick" corrected to Sedgwick.
_HCPF_DESIGNATED_RURAL_COUNTIES = (
    "Alamosa",
    "Archuleta",
    "Bent",
    "Chaffee",
    "Cheyenne",
    "Clear Creek",
    "Conejos",
    "Costilla",
    "Crowley",
    "Custer",
    "Delta",
    "Dolores",
    "Fremont",
    "Gilpin",
    "Grand",
    "Gunnison",
    "Hinsdale",
    "Huerfano",
    "Jackson",
    "Kiowa",
    "Lake",
    "Lincoln",
    "Logan",
    "Mineral",
    "Moffat",
    "Montrose",
    "Morgan",
    "Otero",
    "Ouray",
    "Park",
    "Phillips",
    "Pitkin",
    "Rio Blanco",
    "Rio Grande",
    "Routt",
    "Saguache",
    "San Juan",
    "San Miguel",
    "Sedgwick",
    "Washington",
)

DESIGNATED_RURAL_COUNTIES = frozenset(_HCPF_DESIGNATED_RURAL_COUNTIES)


def get_designated_rural_counties():
    """
    Active rural set: env EDI_RURAL_COUNTIES if set, else HCPF seed list.
    """
    try:
        from django.conf import settings

        raw = (getattr(settings, "EDI_RURAL_COUNTIES", None) or "").strip()
        if raw:
            return frozenset(
                c.strip() for c in raw.split(",") if c and c.strip()
            )
    except Exception:
        pass
    return DESIGNATED_RURAL_COUNTIES


def normalize_county(county):
    if county is None:
        return None
    county = str(county).strip()
    return county or None


def resolve_county_type(county, rural_counties=None):
    counties = (
        get_designated_rural_counties()
        if rural_counties is None
        else frozenset(rural_counties)
    )
    county = normalize_county(county)
    if county and county.casefold() in {c.casefold() for c in counties}:
        return "DESIGNATED_RURAL"
    return "STANDARD"
