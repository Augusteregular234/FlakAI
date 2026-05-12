TIERS = {
    "free_trial": {"label": "Free Trial", "video_limit": 1,    "price_eur": 0},
    "pro":        {"label": "Pro",        "video_limit": 20,   "price_eur": 29},
    "club":       {"label": "Club",       "video_limit": None, "price_eur": 99},
}

FREE_TRIAL_TIER = "free_trial"
PRO_TIER = "pro"
CLUB_TIER = "club"
PREMIUM_TIER = "pro"  # legacy alias


def can_start_upload(team) -> tuple[bool, str]:
    tier = getattr(team, "subscription_tier", None) or FREE_TRIAL_TIER
    limit = TIERS.get(tier, TIERS[FREE_TRIAL_TIER])["video_limit"]
    if limit is None:
        return True, ""
    video_count = len(team.videos) if hasattr(team, "videos") else 0
    if video_count >= limit:
        return (
            False,
            f"Plan {TIERS[tier]['label']} — límite de {limit} vídeo(s) alcanzado. Actualiza tu plan.",
        )
    return True, ""


def tier_info(tier: str) -> dict:
    return TIERS.get(tier, TIERS[FREE_TRIAL_TIER])
