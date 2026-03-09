"use client";
import { useState, useRef, useEffect } from "react";
import Link from "next/link";
import type { ChatMessage, Plan } from "../../lib/types/plans";

const SUGGESTED_PROMPTS = [
  "Create a budget plan for ₹80K/month income",
  "Suggest an investment plan for moderate risk",
  "Help me plan to save ₹6L in 12 months",
  "Run a simulation with ₹25K/month savings",
];

const INTENT_LABELS: Record<string, string> = {
  budget:   "Budget",
  invest:   "Investment",
  goal:     "Goal",
  simulate: "Simulation",
};

function detectIntent(text: string): string | null {
  const t = text.toLowerCase();
  if (t.includes("budget") || t.includes("income") || t.includes("expense")) return "budget";
  if (t.includes("invest") || t.includes("portfolio") || t.includes("equity")) return "invest";
  if (t.includes("goal") || t.includes("save") || t.includes("target")) return "goal";
  if (t.includes("simulat") || t.includes("what if") || t.includes("scenario")) return "simulate";
  return null;
}

const PLAN_TYPE_COLOR: Record<string, string> = {
  budget:   "#3B82F6",
  invest:   "#8B5CF6",
  goal:     "#10B981",
  simulate: "#F59E0B",
};

function InlinePlanCard({ plan }: { plan: Plan }) {
  const color = PLAN_TYPE_COLOR[plan.planType] ?? "#6366F1";
  const conf = Math.round(plan.confidence.overall * 100);
  const route = plan.planType === "simulate" ? "/simulate" : `/plans/${plan.planType}`;

  return (
    <div style={{ background: "#22263A", border: `1px solid ${color}30`, borderRadius: 10, padding: "12px 16px", marginTop: 10 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
        <span style={{ fontSize: 11, padding: "2px 8px", borderRadius: 99, background: `${color}18`, color, fontWeight: 700 }}>
          {plan.planType.toUpperCase()} PLAN
        </span>
        <span style={{ fontSize: 12, color: conf >= 70 ? "#22C55E" : "#F59E0B", fontFamily: "monospace", fontWeight: 600 }}>
          {conf}% confidence
        </span>
      </div>
      <p style={{ fontSize: 12, color: "#94A3B8", margin: "0 0 10px", lineHeight: 1.5 }}>
        {plan.explanation.slice(0, 120)}…
      </p>
      <Link href={`${route}?id=${plan.id}`} style={{ fontSize: 12, color, textDecoration: "none", fontWeight: 600 }}>
        View Full Plan →
      </Link>
    </div>
  );
}

let idCounter = 0;
const newId = () => `msg-${++idCounter}-${Date.now()}`;

export default function ChatInterface() {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: newId(),
      role: "assistant",
      content: "Hi! I'm your VaultAI Strategy Lab. I can help you create budget plans, investment strategies, goal projections, and run financial simulations. What would you like to explore?",
      timestamp: new Date().toISOString(),
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [streamingNode, setStreamingNode] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const sendMessage = async (text: string) => {
    if (!text.trim() || loading) return;
    const userMsg: ChatMessage = { id: newId(), role: "user", content: text, timestamp: new Date().toISOString() };
    setMessages((m) => [...m, userMsg]);
    setInput("");
    setLoading(true);

    // Simulate node streaming
    const nodes = ["router", "intent_classifier", "agent_run", "validate", "respond"];
    for (const node of nodes) {
      setStreamingNode(node);
      await new Promise((r) => setTimeout(r, 400));
    }
    setStreamingNode(null);

    // Mock response — in production call POST /plans/chat
    const response = `I've analyzed your request. Based on your input, I can help you with a ${detectIntent(text) ?? "financial"} plan. Use the Strategy Lab to generate a full AI-validated plan with confidence scoring and execution trace. Type a more specific request or click one of the suggested prompts below to get started.`;

    const assistantMsg: ChatMessage = {
      id: newId(),
      role: "assistant",
      content: response,
      timestamp: new Date().toISOString(),
    };
    setMessages((m) => [...m, assistantMsg]);
    setLoading(false);
  };

  const intent = input ? detectIntent(input) : null;

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", background: "#1A1D27", border: "1px solid #2E3248", borderRadius: 14, overflow: "hidden" }}>
      {/* Messages */}
      <div style={{ flex: 1, overflowY: "auto", padding: 20, display: "flex", flexDirection: "column", gap: 16 }}>
        {messages.map((msg) => (
          <div key={msg.id} style={{ display: "flex", justifyContent: msg.role === "user" ? "flex-end" : "flex-start" }}>
            <div style={{
              maxWidth: "76%",
              padding: "11px 15px",
              borderRadius: msg.role === "user" ? "12px 12px 4px 12px" : "12px 12px 12px 4px",
              background: msg.role === "user" ? "#6366F1" : "#22263A",
              border: msg.role === "assistant" ? "1px solid #2E3248" : "none",
            }}>
              <p style={{ fontSize: 14, color: "#F1F5F9", margin: 0, lineHeight: 1.6 }}>{msg.content}</p>
              {msg.plan && <InlinePlanCard plan={msg.plan} />}
              <p style={{ fontSize: 10, color: "rgba(255,255,255,0.35)", margin: "6px 0 0", textAlign: "right", fontFamily: "monospace" }}>
                {new Date(msg.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
              </p>
            </div>
          </div>
        ))}

        {/* Streaming indicator */}
        {loading && (
          <div style={{ display: "flex", justifyContent: "flex-start" }}>
            <div style={{ padding: "11px 15px", borderRadius: "12px 12px 12px 4px", background: "#22263A", border: "1px solid #2E3248" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ width: 14, height: 14, border: "2px solid rgba(99,102,241,0.3)", borderTop: "2px solid #6366F1", borderRadius: "50%", display: "inline-block", animation: "spin 0.8s linear infinite" }} />
                <span style={{ fontSize: 12, color: "#475569" }}>
                  {streamingNode ? `Running: ${streamingNode}` : "Thinking..."}
                </span>
              </div>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Suggested prompts */}
      {messages.length <= 1 && (
        <div style={{ padding: "0 20px 16px", display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
          {SUGGESTED_PROMPTS.map((p) => (
            <button
              key={p}
              onClick={() => sendMessage(p)}
              style={{ padding: "8px 12px", background: "#22263A", border: "1px solid #2E3248", borderRadius: 8, fontSize: 12, color: "#94A3B8", cursor: "pointer", textAlign: "left", lineHeight: 1.4 }}
            >
              {p}
            </button>
          ))}
        </div>
      )}

      {/* Input */}
      <div style={{ padding: "12px 16px", borderTop: "1px solid #2E3248", display: "flex", gap: 10, alignItems: "flex-end" }}>
        {intent && (
          <span style={{ fontSize: 11, padding: "3px 8px", borderRadius: 99, background: "rgba(99,102,241,0.12)", color: "#A5B4FC", fontWeight: 600, whiteSpace: "nowrap" }}>
            {INTENT_LABELS[intent]}
          </span>
        )}
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(input); } }}
          placeholder="Ask about budgeting, investments, goals, or simulations..."
          rows={1}
          style={{
            flex: 1,
            padding: "9px 12px",
            borderRadius: 8,
            border: "1px solid #2E3248",
            background: "#22263A",
            color: "#F1F5F9",
            fontSize: 14,
            outline: "none",
            resize: "none",
            fontFamily: "inherit",
            lineHeight: 1.5,
          }}
        />
        <button
          onClick={() => sendMessage(input)}
          disabled={loading || !input.trim()}
          style={{ padding: "9px 16px", borderRadius: 8, fontSize: 14, fontWeight: 600, color: "white", background: loading || !input.trim() ? "#4B5563" : "#6366F1", border: "none", cursor: loading || !input.trim() ? "not-allowed" : "pointer" }}
        >
          →
        </button>
      </div>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}