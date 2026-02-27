"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

const nav = [
  { href: "/dashboard", label: "Dashboard", icon: "⊞" },
  { href: "/insights",  label: "Insights",  icon: "✦" },
  { href: "/uploads",   label: "Uploads",   icon: "⬆" },
  { href: "/runs",      label: "Runs",      icon: "◎" },
];

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();

  function logout() {
    localStorage.removeItem("token");
    router.push("/auth");
  }

  return (
    <aside
      style={{
        width: 220,
        minHeight: "100vh",
        background: "#1A1D27",
        borderRight: "1px solid #2E3248",
        display: "flex",
        flexDirection: "column",
        position: "fixed",
        top: 0,
        left: 0,
        bottom: 0,
        zIndex: 50,
      }}
    >
      {/* Logo */}
      <div
        style={{
          padding: "20px 20px 16px",
          borderBottom: "1px solid #2E3248",
          display: "flex",
          alignItems: "center",
          gap: 10,
        }}
      >
        <div
          style={{
            width: 32,
            height: 32,
            background: "#6366F1",
            borderRadius: 8,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: 16,
            color: "white",
            fontWeight: 700,
          }}
        >
          V
        </div>
        <span
          style={{
            fontSize: 16,
            fontWeight: 700,
            color: "#F1F5F9",
            letterSpacing: "-0.02em",
          }}
        >
          VaultAI
        </span>
      </div>

      {/* Nav links */}
      <nav style={{ flex: 1, padding: "12px 10px", display: "flex", flexDirection: "column", gap: 2 }}>
        {nav.map(({ href, label, icon }) => {
          const active = pathname === href || (href !== "/" && pathname.startsWith(href));
          return (
            <Link
              key={href}
              href={href}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                padding: "9px 12px",
                borderRadius: 8,
                fontSize: 14,
                fontWeight: active ? 600 : 400,
                color: active ? "#F1F5F9" : "#94A3B8",
                background: active ? "#22263A" : "transparent",
                borderLeft: active ? "2px solid #6366F1" : "2px solid transparent",
                textDecoration: "none",
                transition: "all 0.15s ease",
              }}
            >
              <span style={{ fontSize: 14 }}>{icon}</span>
              {label}
            </Link>
          );
        })}
      </nav>

      {/* Bottom - logout */}
      <div style={{ padding: "12px 10px", borderTop: "1px solid #2E3248" }}>
        <button
          onClick={logout}
          style={{
            width: "100%",
            padding: "9px 12px",
            borderRadius: 8,
            fontSize: 14,
            fontWeight: 400,
            color: "#94A3B8",
            background: "transparent",
            border: "none",
            cursor: "pointer",
            textAlign: "left",
            display: "flex",
            alignItems: "center",
            gap: 10,
          }}
          onMouseEnter={(e) => {
            (e.currentTarget as HTMLButtonElement).style.color = "#EF4444";
            (e.currentTarget as HTMLButtonElement).style.background = "rgba(239,68,68,0.08)";
          }}
          onMouseLeave={(e) => {
            (e.currentTarget as HTMLButtonElement).style.color = "#94A3B8";
            (e.currentTarget as HTMLButtonElement).style.background = "transparent";
          }}
        >
          <span>⊗</span>
          Logout
        </button>
      </div>
    </aside>
  );
}