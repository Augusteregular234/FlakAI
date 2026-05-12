"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuthStore } from "@/lib/store";
import { cn } from "@/lib/utils";

const navItems = [
  { href: "/dashboard", label: "Mis Vídeos", icon: "▶" },
  { href: "/dashboard/upload", label: "Subir Vídeo", icon: "↑" },
  { href: "/dashboard/review", label: "Revisión", icon: "◉" },
];

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, team, logout } = useAuthStore();

  const handleLogout = () => {
    logout();
    router.push("/login");
  };

  return (
    <aside className="w-56 min-h-screen bg-zinc-900 border-r border-zinc-800 flex flex-col">
      <div className="px-5 py-6 border-b border-zinc-800">
        <h1 className="text-xl font-black text-white tracking-tight">
          Flak<span className="text-emerald-400">AI</span>
          <span className="text-zinc-600 text-sm font-light ml-1">v2</span>
        </h1>
        {team && <p className="text-zinc-500 text-xs mt-1 truncate">{team.name}</p>}
      </div>

      <nav className="flex-1 px-3 py-4 space-y-1">
        {navItems.map((item) => {
          const active = pathname === item.href || (item.href !== "/dashboard" && pathname.startsWith(item.href));
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors",
                active
                  ? "bg-emerald-500/10 text-emerald-400"
                  : "text-zinc-400 hover:text-white hover:bg-zinc-800"
              )}
            >
              <span className="text-base">{item.icon}</span>
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="px-5 py-4 border-t border-zinc-800">
        <p className="text-zinc-500 text-xs truncate mb-2">{user?.username}</p>
        <button
          onClick={handleLogout}
          className="text-zinc-600 hover:text-red-400 text-xs transition-colors"
        >
          Cerrar sesión
        </button>
      </div>
    </aside>
  );
}
