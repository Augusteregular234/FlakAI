"""
Stripe billing: checkout sessions, customer portal, webhooks.
Configura STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, STRIPE_PRICE_ID_PRO,
STRIPE_PRICE_ID_CLUB en backend/.env antes de usar.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from auth import get_current_user, require_active_team
from billing.subscription import TIERS, tier_info
from config import get_settings
from database import get_db
import models

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/billing", tags=["billing"])

PRICE_MAP = {
    "pro": "stripe_price_id_pro",
    "club": "stripe_price_id_club",
}


def _stripe():
    import stripe as _s
    s = get_settings()
    if not s.stripe_secret_key:
        raise HTTPException(503, detail="Stripe no configurado. Añade STRIPE_SECRET_KEY en backend/.env")
    _s.api_key = s.stripe_secret_key
    return _s


@router.get("/plans")
def get_plans(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    team = db.query(models.Team).filter(models.Team.id == current_user.team_id).first()
    current_tier = team.subscription_tier if team else "free_trial"
    return {
        "current_tier": current_tier,
        "plans": [
            {
                "tier": "free_trial",
                "label": "Free Trial",
                "price_eur": 0,
                "video_limit": 1,
                "features": ["1 vídeo de prueba", "Detección IA mock", "Export JSONL"],
                "cta": "Tu plan actual" if current_tier == "free_trial" else None,
            },
            {
                "tier": "pro",
                "label": "Pro",
                "price_eur": 29,
                "video_limit": 20,
                "features": ["20 vídeos/mes", "Prioridad de procesamiento", "Export CSV + JSONL", "Soporte email"],
                "cta": "Actualizar a Pro" if current_tier != "pro" else "Tu plan actual",
                "recommended": True,
            },
            {
                "tier": "club",
                "label": "Club",
                "price_eur": 99,
                "video_limit": None,
                "features": ["Vídeos ilimitados", "API acceso directo", "Admin ML export", "Soporte prioritario", "Dataset privado"],
                "cta": "Actualizar a Club" if current_tier != "club" else "Tu plan actual",
            },
        ],
    }


@router.post("/create-checkout-session")
def create_checkout_session(
    body: dict,
    current_user: models.User = Depends(require_active_team),
    db: Session = Depends(get_db),
):
    tier = body.get("tier")
    if tier not in PRICE_MAP:
        raise HTTPException(400, detail="Plan inválido. Usa 'pro' o 'club'.")

    stripe = _stripe()
    s = get_settings()
    price_id_attr = PRICE_MAP[tier]
    price_id = getattr(s, price_id_attr, "")
    if not price_id:
        raise HTTPException(503, detail=f"Precio Stripe '{price_id_attr}' no configurado en .env")

    team = db.query(models.Team).filter(models.Team.id == current_user.team_id).first()

    customer_id = team.stripe_customer_id if team else None
    if not customer_id:
        customer = stripe.Customer.create(
            email=current_user.email,
            name=team.name if team else current_user.username,
            metadata={"team_id": str(current_user.team_id)},
        )
        customer_id = customer.id
        if team:
            team.stripe_customer_id = customer_id
            db.commit()

    session = stripe.checkout.Session.create(
        customer=customer_id,
        payment_method_types=["card"],
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=f"{s.app_url}/dashboard/billing?success=1",
        cancel_url=f"{s.app_url}/dashboard/billing?canceled=1",
        metadata={"team_id": str(current_user.team_id), "tier": tier},
    )
    return {"url": session.url}


@router.post("/create-portal-session")
def create_portal_session(
    current_user: models.User = Depends(require_active_team),
    db: Session = Depends(get_db),
):
    stripe = _stripe()
    s = get_settings()
    team = db.query(models.Team).filter(models.Team.id == current_user.team_id).first()
    if not team or not team.stripe_customer_id:
        raise HTTPException(400, detail="Sin suscripción activa para gestionar.")

    session = stripe.billing_portal.Session.create(
        customer=team.stripe_customer_id,
        return_url=f"{s.app_url}/dashboard/billing",
    )
    return {"url": session.url}


@router.post("/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    stripe = _stripe()
    s = get_settings()
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(payload, sig, s.stripe_webhook_secret)
    except Exception as e:
        logger.warning("Stripe webhook invalid: %s", e)
        raise HTTPException(400, detail="Invalid webhook signature")

    etype = event["type"]
    data = event["data"]["object"]

    if etype in ("customer.subscription.created", "customer.subscription.updated"):
        tier = data.get("metadata", {}).get("tier") or _price_to_tier(data, s)
        customer_id = data.get("customer")
        status = data.get("status")
        if customer_id and tier and status in ("active", "trialing"):
            team = db.query(models.Team).filter(models.Team.stripe_customer_id == customer_id).first()
            if team:
                team.subscription_tier = tier
                db.commit()

    elif etype == "customer.subscription.deleted":
        customer_id = data.get("customer")
        if customer_id:
            team = db.query(models.Team).filter(models.Team.stripe_customer_id == customer_id).first()
            if team:
                team.subscription_tier = "free_trial"
                db.commit()

    return JSONResponse({"received": True})


def _price_to_tier(sub_data: dict, s) -> str | None:
    items = sub_data.get("items", {}).get("data", [])
    for item in items:
        price_id = item.get("price", {}).get("id", "")
        if price_id == s.stripe_price_id_pro:
            return "pro"
        if price_id == s.stripe_price_id_club:
            return "club"
    return None
