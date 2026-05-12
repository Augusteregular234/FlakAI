"use client";
import { useEffect, useState, useCallback } from "react";
import { useSearchParams } from "next/navigation";
import { toast } from "sonner";
import { api, type BillingPlans } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

const TIER_COLORS: Record<string, string> = {
  free_trial: "bg-zinc-500/10 text-zinc-400 border-zinc-700",
  pro: "bg-blue-500/10 text-blue-400 border-blue-800",
  club: "bg-purple-500/10 text-purple-400 border-purple-800",
};

export default function BillingPage() {
  const [data, setData] = useState<BillingPlans | null>(null);
  const [loading, setLoading] = useState(true);
  const [checkoutLoading, setCheckoutLoading] = useState<string | null>(null);
  const searchParams = useSearchParams();

  useEffect(() => {
    if (searchParams.get("success") === "1") toast.success("¡Suscripción activada! Bienvenido al nuevo plan.");
    if (searchParams.get("canceled") === "1") toast.info("Checkout cancelado. Tu plan no ha cambiado.");
  }, [searchParams]);

  const load = useCallback(async () => {
    try {
      const d = await api.billing.plans();
      setData(d);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Error al cargar planes");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleUpgrade = async (tier: string) => {
    if (tier === "free_trial" || tier === data?.current_tier) return;
    setCheckoutLoading(tier);
    try {
      const { url } = await api.billing.createCheckout(tier as "pro" | "club");
      window.location.href = url;
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Error al iniciar checkout");
      setCheckoutLoading(null);
    }
  };

  const handlePortal = async () => {
    setCheckoutLoading("portal");
    try {
      const { url } = await api.billing.createPortal();
      window.open(url, "_blank");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Error al abrir portal");
    } finally {
      setCheckoutLoading(null);
    }
  };

  if (loading) return <div className="p-8 text-zinc-600 text-sm">Cargando planes...</div>;

  const current = data?.current_tier ?? "free_trial";

  return (
    <div className="p-8 max-w-5xl">
      <div className="mb-8">
        <h2 className="text-2xl font-bold text-white">Planes y Facturación</h2>
        <div className="flex items-center gap-3 mt-2">
          <p className="text-zinc-500 text-sm">Plan actual:</p>
          <Badge className={`${TIER_COLORS[current]} border text-xs font-semibold`}>
            {data?.plans.find((p) => p.tier === current)?.label ?? current}
          </Badge>
          {current !== "free_trial" && (
            <button
              onClick={handlePortal}
              disabled={checkoutLoading === "portal"}
              className="text-xs text-zinc-500 hover:text-white transition-colors ml-2"
            >
              Gestionar suscripción →
            </button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {data?.plans.map((plan) => {
          const isCurrentPlan = plan.tier === current;
          const isRecommended = plan.recommended;

          return (
            <div
              key={plan.tier}
              className={`relative rounded-2xl border p-6 flex flex-col transition-all ${
                isRecommended
                  ? "border-blue-700 bg-blue-950/20"
                  : isCurrentPlan
                  ? "border-emerald-800 bg-emerald-950/10"
                  : "border-zinc-800 bg-zinc-900"
              }`}
            >
              {isRecommended && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                  <span className="bg-blue-500 text-black text-xs font-black px-3 py-1 rounded-full">
                    RECOMENDADO
                  </span>
                </div>
              )}

              <div className="mb-4">
                <h3 className="text-white font-bold text-lg">{plan.label}</h3>
                <div className="flex items-baseline gap-1 mt-1">
                  <span className="text-3xl font-black text-white">
                    {plan.price_eur === 0 ? "Gratis" : `€${plan.price_eur}`}
                  </span>
                  {plan.price_eur > 0 && <span className="text-zinc-500 text-sm">/mes</span>}
                </div>
                <p className="text-zinc-500 text-xs mt-1">
                  {plan.video_limit === null
                    ? "Vídeos ilimitados"
                    : `${plan.video_limit} vídeo${plan.video_limit !== 1 ? "s" : ""}/mes`}
                </p>
              </div>

              <ul className="space-y-2 flex-1 mb-6">
                {plan.features.map((f) => (
                  <li key={f} className="flex items-start gap-2 text-sm text-zinc-300">
                    <span className="text-emerald-400 mt-0.5 shrink-0">✓</span>
                    {f}
                  </li>
                ))}
              </ul>

              <Button
                onClick={() => handleUpgrade(plan.tier)}
                disabled={isCurrentPlan || checkoutLoading !== null}
                className={
                  isCurrentPlan
                    ? "bg-zinc-800 text-zinc-500 cursor-default"
                    : isRecommended
                    ? "bg-blue-500 hover:bg-blue-400 text-black font-bold"
                    : "bg-white hover:bg-zinc-100 text-black font-bold"
                }
              >
                {checkoutLoading === plan.tier
                  ? "Redirigiendo..."
                  : plan.cta ?? "Seleccionar"}
              </Button>
            </div>
          );
        })}
      </div>

      <div className="mt-10 p-5 bg-zinc-900 border border-zinc-800 rounded-xl text-sm text-zinc-500 space-y-1">
        <p>🔒 Pagos seguros gestionados por <strong className="text-zinc-300">Stripe</strong>. FlakAI nunca almacena datos de tarjeta.</p>
        <p>📋 Cancela en cualquier momento desde el portal de cliente. Sin permanencia.</p>
        <p>⚡ Los cambios de plan se aplican inmediatamente tras el pago.</p>
      </div>
    </div>
  );
}
