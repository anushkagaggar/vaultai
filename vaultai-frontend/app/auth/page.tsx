"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { loginUser, registerUser } from "../../lib/backend";

export default function AuthPage() {
  const router = useRouter();
  const [isLogin, setIsLogin] = useState(true);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    setSuccess("");

    try {
      if (isLogin) {
        const data = await loginUser({ email, password });
        localStorage.setItem("token", data.access_token);
        router.push("/dashboard");
      } else {
        await registerUser({ email, password });
        setSuccess("Account created! You can now sign in.");
        setIsLogin(true);
      }
    } catch (e: any) {
      setError(e.message || "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  const inputStyle = {
    width: "100%",
    padding: "10px 14px",
    borderRadius: 8,
    border: "1px solid #2E3248",
    background: "#22263A",
    color: "#F1F5F9",
    fontSize: 14,
    outline: "none",
    boxSizing: "border-box" as const,
  };

  return (
    <div style={{ display: "flex", minHeight: "100vh", background: "#0F1117" }}>
      {/* Left panel */}
      <div
        style={{
          width: "45%",
          background: "#1A1D27",
          borderRight: "1px solid #2E3248",
          display: "flex",
          flexDirection: "column",
          padding: "32px 40px",
        }}
      >
        {/* Logo */}
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 60 }}>
          <div
            style={{
              width: 32,
              height: 32,
              background: "#6366F1",
              borderRadius: 8,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "white",
              fontWeight: 700,
              fontSize: 16,
            }}
          >
            V
          </div>
          <span style={{ fontSize: 16, fontWeight: 700, color: "#F1F5F9" }}>VaultAI</span>
        </div>

        {/* Features */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", justifyContent: "center" }}>
          <h2 style={{ fontSize: 20, fontWeight: 600, color: "#F1F5F9", marginBottom: 32 }}>
            Your financial intelligence, powered by AI
          </h2>
          {[
            { icon: "✦", label: "AI-Validated Insights" },
            { icon: "◎", label: "Confidence Scoring" },
            { icon: "◈", label: "RAG Document Grounding" },
            { icon: "◷", label: "Deterministic Analytics" },
          ].map(({ icon, label }) => (
            <div
              key={label}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 12,
                marginBottom: 18,
              }}
            >
              <span style={{ fontSize: 16, color: "#6366F1" }}>{icon}</span>
              <span style={{ fontSize: 14, color: "#94A3B8" }}>{label}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Right panel — form */}
      <div
        style={{
          flex: 1,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: "32px 40px",
        }}
      >
        <div style={{ width: "100%", maxWidth: 360 }}>
          <h2 style={{ fontSize: 22, fontWeight: 700, color: "#F1F5F9", marginBottom: 6 }}>
            {isLogin ? "Welcome back" : "Create account"}
          </h2>
          <p style={{ fontSize: 14, color: "#475569", marginBottom: 28 }}>
            {isLogin ? "Sign in to your VaultAI account" : "Start tracking your expenses with AI"}
          </p>

          <form onSubmit={handleSubmit}>
            <div style={{ marginBottom: 14 }}>
              <label style={{ display: "block", fontSize: 13, color: "#94A3B8", marginBottom: 6 }}>
                Email
              </label>
              <input
                type="email"
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                style={inputStyle}
              />
            </div>

            <div style={{ marginBottom: 20 }}>
              <label style={{ display: "block", fontSize: 13, color: "#94A3B8", marginBottom: 6 }}>
                Password
              </label>
              <input
                type="password"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                style={inputStyle}
              />
            </div>

            {error && (
              <div
                style={{
                  padding: "10px 14px",
                  background: "rgba(239,68,68,0.08)",
                  border: "1px solid rgba(239,68,68,0.2)",
                  borderRadius: 8,
                  fontSize: 13,
                  color: "#EF4444",
                  marginBottom: 16,
                }}
              >
                {error}
              </div>
            )}

            {success && (
              <div
                style={{
                  padding: "10px 14px",
                  background: "rgba(34,197,94,0.08)",
                  border: "1px solid rgba(34,197,94,0.2)",
                  borderRadius: 8,
                  fontSize: 13,
                  color: "#22C55E",
                  marginBottom: 16,
                }}
              >
                {success}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              style={{
                width: "100%",
                padding: "11px",
                borderRadius: 8,
                fontSize: 14,
                fontWeight: 500,
                color: "white",
                background: loading ? "#4B5563" : "#6366F1",
                border: "none",
                cursor: loading ? "not-allowed" : "pointer",
              }}
            >
              {loading ? "Please wait..." : isLogin ? "Sign In" : "Create Account"}
            </button>
          </form>

          <p style={{ fontSize: 13, color: "#475569", marginTop: 20, textAlign: "center" }}>
            {isLogin ? "Don't have an account? " : "Already have one? "}
            <button
              onClick={() => { setIsLogin(!isLogin); setError(""); setSuccess(""); }}
              style={{ color: "#6366F1", background: "none", border: "none", cursor: "pointer", fontSize: 13 }}
            >
              {isLogin ? "Register →" : "Sign in →"}
            </button>
          </p>
        </div>
      </div>
    </div>
  );
}