"""Harmonizes manufacturer-specific location quality codes into a universal
quality tier (high / medium / low / unusable / unknown), while the raw code
is always preserved alongside it. Extend the per-manufacturer maps below as
new parsers are added.
"""

# Argos Location Class accuracy, per CLS Argos User's Manual:
# 3: <250m, 2: 250-500m, 1: 500-1500m, 0: >1500m (estimate available),
# A/B: no accuracy estimate, Z: invalid/rejected location.
ARGOS_QUALITY_MAP = {
    "3": "high",
    "2": "high",
    "1": "medium",
    "0": "medium",
    "A": "low",
    "B": "low",
    "Z": "unusable",
}


def harmonize(location_type: str, quality_raw: str | None) -> str:
    if not quality_raw:
        if location_type in ("GPS", "FastGPS"):
            return "high"
        return "unknown"

    q = quality_raw.strip().upper()

    if location_type == "Argos":
        return ARGOS_QUALITY_MAP.get(q, "unknown")
    if location_type in ("GPS", "FastGPS"):
        return "high"
    if location_type in ("GPE", "GPE2", "GPE3"):
        return "low"
    return "unknown"
