import re
import difflib
from datetime import datetime
from typing import Optional


def make_slug(text: str) -> str:
    """Convert a string to a URL-safe slug for matching."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    text = text.strip("-")
    return text


def fuzzy_match(candidate: str, options: list[str], threshold: float = 0.85) -> Optional[str]:
    """
    Return the best matching option if above threshold, else None.
    Compares slugified versions.
    """
    cand_slug = make_slug(candidate)
    best_score = 0.0
    best_match = None
    for opt in options:
        score = difflib.SequenceMatcher(None, cand_slug, make_slug(opt)).ratio()
        if score > best_score:
            best_score = score
            best_match = opt
    if best_score >= threshold:
        return best_match
    return None


def fuzzy_match_score(a: str, b: str) -> float:
    """
    Score similarity between two strings using slugified comparison.
    Also boosts score when one name is fully contained in the other
    (handles "Mike Hartley" vs "Mike Hartley / Hartley Realty Group").
    """
    sa, sb = make_slug(a), make_slug(b)
    base_score = difflib.SequenceMatcher(None, sa, sb).ratio()

    # Containment boost: if the shorter slug appears at the start of the longer one
    shorter, longer = (sa, sb) if len(sa) <= len(sb) else (sb, sa)
    if shorter and longer.startswith(shorter):
        containment_score = len(shorter) / len(longer)
        # Blend: give containment significant weight when it's a strong prefix match
        return max(base_score, 0.5 + containment_score * 0.5)

    return base_score


def generate_reference_number(session) -> str:
    """Generate the next sequential deal reference number: JOB-YYYY-NNN."""
    from dealtracker.models import Deal
    year = datetime.now().year
    prefix = f"JOB-{year}-"
    existing = (
        session.query(Deal.reference_number)
        .filter(Deal.reference_number.like(f"{prefix}%"))
        .all()
    )
    nums = []
    for (ref,) in existing:
        try:
            nums.append(int(ref.replace(prefix, "")))
        except ValueError:
            pass
    next_num = max(nums, default=0) + 1
    return f"{prefix}{next_num:03d}"
