"""
Fuzzy scoring utilities for room suitability and comfort / preferences.
These scores feed into GA and evaluators.
"""

from typing import Dict, Any
import math


def fuzzy_membership(x: float, a: float, b: float, c: float) -> float:
    """
    Simple triangular membership function:
       a --- b --- c
    Returns value in [0, 1].
    """
    if x <= a or x >= c:
        return 0.0
    if x == b:
        return 1.0
    if x < b:
        return (x - a) / (b - a)
    return (c - x) / (c - b)


def room_comfort_score(room: Dict[str, Any], teacher_pref: Dict[str, Any]) -> float:
    """
    Example fuzzy score:
      - room capacity closeness to target size
      - building / tag matching
    """
    target_size = float(teacher_pref.get("target_size", 30))
    cap = float(room["capacity"])

    # Capacity: peak score when cap ~ target_size
    cap_score = fuzzy_membership(
        x=cap,
        a=0.5 * target_size,
        b=1.2 * target_size,
        c=2.0 * target_size,
    )

    # Building preference (if given)
    desired_building = teacher_pref.get("preferred_building")
    if desired_building and room.get("building") == desired_building:
        build_score = 1.0
    else:
        build_score = 0.5

    # Tag preference (example: prefers lab / near-CS)
    desired_tag = teacher_pref.get("preferred_tag")
    if desired_tag and desired_tag in room.get("tags", []):
        tag_score = 1.0
    else:
        tag_score = 0.5

    return 0.5 * cap_score + 0.3 * build_score + 0.2 * tag_score