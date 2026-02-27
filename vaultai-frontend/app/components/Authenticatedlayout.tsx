"use client";
import Sidebar from "./Sidebar";

export default function AuthenticatedLayout({
  children,
  title,
  action,
}: {
  children: React.ReactNode;
  title: string;
  action?: React.ReactNode;
}) {
  return (
    <div style={{ display: "flex", minHeight: "100vh", background: "#0F1117" }}>
      <Sidebar />

      {/* Main content shifted right by sidebar width */}
      <div style={{ marginLeft: 220, flex: 1, display: "flex", flexDirection: "column" }}>
        {/* Top bar */}
        <div
          style={{
            height: 56,
            background: "#1A1D27",
            borderBottom: "1px solid #2E3248",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "0 32px",
            position: "sticky",
            top: 0,
            zIndex: 40,
          }}
        >
          <h1 style={{ fontSize: 16, fontWeight: 600, color: "#F1F5F9", margin: 0 }}>
            {title}
          </h1>
          {action && <div>{action}</div>}
        </div>

        {/* Page content */}
        <main
          style={{
            flex: 1,
            padding: 32,
            overflowY: "auto",
          }}
        >
          <div style={{ maxWidth: 1100, margin: "0 auto" }}>
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}