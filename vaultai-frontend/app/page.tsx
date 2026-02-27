import Link from "next/link";

export default function LandingPage() {
  return (
    <div
      style={{
        minHeight: "100vh",
        background: "#0F1117",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <div style={{ maxWidth: 480, width: "100%", padding: "0 24px", textAlign: "center" }}>
        {/* Logo */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 12, marginBottom: 32 }}>
          <div
            style={{
              width: 44,
              height: 44,
              background: "#6366F1",
              borderRadius: 12,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 22,
              color: "white",
              fontWeight: 700,
            }}
          >
            V
          </div>
          <span style={{ fontSize: 28, fontWeight: 700, color: "#F1F5F9", letterSpacing: "-0.02em" }}>
            VaultAI
          </span>
        </div>

        {/* Tagline */}
        <h1
          style={{
            fontSize: 22,
            fontWeight: 600,
            color: "#F1F5F9",
            margin: "0 0 14px",
            lineHeight: 1.4,
          }}
        >
          Your personal AI-powered expense intelligence
        </h1>

        {/* Description */}
        <p
          style={{
            fontSize: 14,
            color: "#94A3B8",
            margin: "0 0 36px",
            lineHeight: 1.7,
            maxWidth: 360,
            marginLeft: "auto",
            marginRight: "auto",
          }}
        >
          Track spending, understand patterns, and get AI-validated financial
          insights — grounded in your own documents.
        </p>

        {/* CTAs */}
        <div style={{ display: "flex", gap: 12, justifyContent: "center", marginBottom: 28 }}>
          <Link
            href="/auth"
            style={{
              padding: "10px 24px",
              borderRadius: 8,
              fontSize: 14,
              fontWeight: 500,
              color: "white",
              background: "#6366F1",
              textDecoration: "none",
              border: "none",
            }}
          >
            Get Started
          </Link>
          <Link
            href="/auth"
            style={{
              padding: "10px 24px",
              borderRadius: 8,
              fontSize: 14,
              fontWeight: 500,
              color: "#94A3B8",
              background: "transparent",
              textDecoration: "none",
              border: "1px solid #2E3248",
            }}
          >
            Sign In
          </Link>
        </div>

        {/* Tech note */}
        <p style={{ fontSize: 11, color: "#475569", margin: 0, letterSpacing: "0.02em" }}>
          Powered by LLaMA 3.1 · Validated insights · RAG-grounded reasoning
        </p>
      </div>
    </div>
  );
}