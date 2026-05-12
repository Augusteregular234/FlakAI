"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuthStore } from "@/lib/store";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";

const TIER_LABELS: Record<string, { label: string; color: string }> = {
  free_trial: { label: "Free",  color: "bg-zinc-700 text-zinc-400" },
  pro:        { label: "Pro",   color: "bg-blue-900 text-blue-300" },
  club:       { label: "Club",  color: "bg-purple-900 text-purple-300" },
};

const baseNav = [
  { href: "/dashboard",         label: "Mis Vídeos",   icon: "▶" },
  { href: "/dashboard/upload",  label: "Subir Vídeo",  icon: "↑" },
  { href: "/dashboard/review",  label: "Revisión",     icon: "◉" },
  { href: "/dashboard/billing", label: "Facturación",  icon: "💳" },
];

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, team, logout } = useAuthStore();

  const handleLogout = () => {
    logout();
    router.push("/login");
  };

  const tier = team?.subscription_tier ?? "free_trial";
  const tierMeta = TIER_LABELS[tier] ?? TIER_LABELS.free_trial;

  return (
    <aside className="w-60 min-h-screen bg-zinc-900 border-r border-zinc-800 flex flex-col">
      {/* Logo */}
      <div className="px-5 pt-6 pb-5 border-b border-zinc-800">
        <h1 className="text-xl font-black text-white tracking-tight">
          Flak<span className="text-emerald-400">AI</span>
          <span className="text-zinc-600 text-sm font-light ml-1">v2</span>
        </h1>
        {team && (
          <div className="flex items-center gap-2 mt-2">
            <p className="text-zinc-400 text-xs truncate flex-1">{team.name}</p>
            <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${tierMeta.color}`}>
              {tierMeta.label}
            </span>
          </div>
        )}
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-0.5">
        {user?.is_admin && (
          <Link
            href="/dashboard/admin"
            className={cn(
              "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors mb-3",
              pathname === "/dashboard/admin"
                ? "bg-amber-500/15 text-amber-400"
                : "text-amber-600 hover:text-amber-400 hover:bg-zinc-800"
            )}
          >
            <span>⚙</span>
            Admin · Equipos
          </Link>
        )}

        {baseNav.map((item) => {
          const active =
            pathname === item.href ||
            (item.href !== "/dashboard" && pathname.startsWith(item.href));
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors",
                active
                  ? "bg-emerald-500/10 text-emerald-400"
                  : "text-zinc-400 hover:text-white hover:bg-zinc-800"
              )}
            >
              <span className="w-4 text-center text-sm">{item.icon}</span>
              {item.label}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="px-4 py-4 border-t border-zinc-800">
        {tier === "free_trial" && (
          <Link
            href="/dashboard/billing"
            className="block mb-3 p-3 bg-gradient-to-r from-blue-950 to-purple-950 border border-blue-900/50 rounded-xl text-xs"
          >
            <p className="text-white font-semibold mb-0.5">Actualizar plan</p>
            <p className="text-zinc-400">Pro desde €29/mes →</p>
          </Link>
        )}
        <div className="flex items-center justify-between">
          <p className="text-zinc-500 text-xs truncate max-w-[120px]">{user?.username}</p>
          <button
            onClick={handleLogout}
            className="text-zinc-600 hover:text-red-400 text-xs transition-colors shrink-0"
          >
            Salir
          </button>
        </div>
      </div>
    </aside>
  );
}
