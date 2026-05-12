"""
Stub de suscripción / facturación.
Sustituir por integración Stripe (checkout, webhooks, customer portal).
"""

PREMIUM_TIER = "premium"
FREE_TRIAL_TIER = "free_trial"


def can_start_upload(team) -> bool:
    """Un vídeo de prueba por equipo salvo plan premium."""
    tier = getattr(team, "subscription_tier", None) or FREE_TRIAL_TIER
    if tier == PREMIUM_TIER:
        return True
    return not bool(getattr(team, "trial_video_used", False))
