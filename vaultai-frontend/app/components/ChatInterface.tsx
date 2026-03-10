'use client';
import React, { useState, useRef, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import {
  Send, Loader2, CheckCircle, AlertCircle,
  BarChart2, TrendingUp, Target, PlusCircle, ChevronRight,
} from 'lucide-react';
import { sendChatMessage, createExpense, deleteExpense, ApiError } from '../../lib/backend';
import { savePlanRef } from '../../app/plans/page';

// ─────────────────────────────────────────────────────────────────────────────
// Types that mirror the backend PlanResponse exactly
// ─────────────────────────────────────────────────────────────────────────────

interface PlanResponse {
  plan_id:            number | null;
  plan_type:          string;           // "budget" | "invest" | "goal"
  projected_outcomes: Record<string, unknown> | null;
  explanation:        string | null;
  confidence:         Record<string, unknown> | null;
  degraded:           boolean;
  graph_trace:        string[];
  source_hash:        string | null;
}

// Full ChatPlanRequest — mirrors backend ChatPlanRequest exactly
interface ChatPayload {
  message:            string;
  // Budget
  income_monthly?:     number;
  savings_target_pct?: number;
  fixed_categories?:   string[];
  // Invest
  investment_amount?: number;
  risk_profile?:      string;
  horizon_months?:    number;
  // Goal
  goal_type?:         string;
  target_amount?:     number;
  current_savings?:   number;
  monthly_savings?:   number;
  annual_rate?:       number;
}

// ─────────────────────────────────────────────────────────────────────────────
// HITL — field definitions for every param the backend may ask for
// ─────────────────────────────────────────────────────────────────────────────

interface FieldDef {
  key:         keyof ChatPayload;
  label:       string;
  placeholder: string;
  type:        'number' | 'select';
  options?:    { value: string; label: string }[];
  // convert raw string → correct typed value for the payload
  parse:       (raw: string) => number | string | string[];
}

const FIELD_DEFS: Record<string, FieldDef> = {
  income_monthly: {
    key: 'income_monthly', label: 'Monthly Income (₹)',
    placeholder: 'e.g. 80000', type: 'number',
    parse: (v) => parseFloat(v.replace(/[^\d.]/g, '')),
  },
  savings_target_pct: {
    key: 'savings_target_pct', label: 'Savings Target %',
    placeholder: 'e.g. 20 for 20%', type: 'number',
    // backend expects 0–1 decimal
    parse: (v) => { const n = parseFloat(v.replace(/[^\d.]/g, '')); return n > 1 ? n / 100 : n; },
  },
  investment_amount: {
    key: 'investment_amount', label: 'Investment Amount (₹)',
    placeholder: 'e.g. 50000', type: 'number',
    parse: (v) => parseFloat(v.replace(/[^\d.]/g, '')),
  },
  risk_profile: {
    key: 'risk_profile', label: 'Risk Profile',
    placeholder: '', type: 'select',
    options: [
      { value: 'conservative', label: 'Conservative — stable, low risk' },
      { value: 'moderate',     label: 'Moderate — balanced growth' },
      { value: 'aggressive',   label: 'Aggressive — high growth, higher risk' },
    ],
    parse: (v) => v,
  },
  horizon_months: {
    key: 'horizon_months', label: 'Investment Horizon (months)',
    placeholder: 'e.g. 36 for 3 years', type: 'number',
    parse: (v) => parseInt(v.replace(/[^\d]/g, '')),
  },
  goal_type: {
    key: 'goal_type', label: 'Goal Type',
    placeholder: '', type: 'select',
    options: [
      { value: 'savings',        label: 'Savings — general saving target' },
      { value: 'emergency_fund', label: 'Emergency Fund' },
      { value: 'purchase',       label: 'Purchase — car, phone, gadget, etc.' },
      { value: 'education',      label: 'Education' },
      { value: 'retirement',     label: 'Retirement' },
    ],
    parse: (v) => v,
  },
  target_amount: {
    key: 'target_amount', label: 'Target Amount (₹)',
    placeholder: 'e.g. 600000', type: 'number',
    parse: (v) => parseFloat(v.replace(/[^\d.]/g, '')),
  },
  current_savings: {
    key: 'current_savings', label: 'Current Savings (₹)',
    placeholder: 'e.g. 0', type: 'number',
    parse: (v) => parseFloat(v.replace(/[^\d.]/g, '')),
  },
  monthly_savings: {
    key: 'monthly_savings', label: 'Monthly Savings Capacity (₹)',
    placeholder: 'Leave blank to let AI calculate', type: 'number',
    parse: (v) => parseFloat(v.replace(/[^\d.]/g, '')),
  },
  annual_rate: {
    key: 'annual_rate', label: 'Expected Annual Return',
    placeholder: 'e.g. 7 for 7%', type: 'number',
    // backend expects 0–1 decimal
    parse: (v) => { const n = parseFloat(v.replace(/[^\d.]/g, '')); return n > 1 ? n / 100 : n; },
  },
};

// ─────────────────────────────────────────────────────────────────────────────
// Parse the 422 detail string from the backend to find missing field names
// Backend format: "Your message was classified as a budget plan.
//                  Please also provide: income_monthly."
// ─────────────────────────────────────────────────────────────────────────────

function parseMissingFields(detail: string): FieldDef[] {
  const match = detail.match(/[Pp]lease also provide:\s*(.+?)\.?\s*$/);
  if (!match) return [];
  return match[1]
    .split(/,\s*/)
    .map((f) => f.trim())
    .filter((f) => FIELD_DEFS[f])
    .map((f) => FIELD_DEFS[f]);
}

// ─────────────────────────────────────────────────────────────────────────────
// Expense parser — for "add ₹500 groceries" type messages
// Only used when message clearly refers to an expense operation
// ─────────────────────────────────────────────────────────────────────────────

const CATEGORY_MAP: Record<string, string> = {
  food: 'Food', grocery: 'Food', groceries: 'Food', restaurant: 'Food', eat: 'Food', lunch: 'Food', dinner: 'Food', breakfast: 'Food',
  transport: 'Transport', cab: 'Transport', uber: 'Transport', ola: 'Transport', auto: 'Transport', bus: 'Transport', train: 'Transport', fuel: 'Transport', petrol: 'Transport',
  shopping: 'Shopping', clothes: 'Shopping', clothing: 'Shopping', amazon: 'Shopping', flipkart: 'Shopping',
  utilities: 'Utilities', electricity: 'Utilities', water: 'Utilities', internet: 'Utilities', wifi: 'Utilities', mobile: 'Utilities', recharge: 'Utilities',
  health: 'Health', medicine: 'Health', doctor: 'Health', hospital: 'Health', pharmacy: 'Health', gym: 'Health',
  entertainment: 'Entertainment', movie: 'Entertainment', netflix: 'Entertainment', game: 'Entertainment',
};

function isExpenseMessage(text: string): boolean {
  const t = text.toLowerCase();
  const hasAction = t.includes('add') || t.includes('log') || t.includes('record') || t.includes('spent') || t.includes('bought') || t.includes('paid');
  const hasMoney  = t.includes('₹') || /\brs\.?\b/.test(t) || t.includes('rupee');
  const noPlan    = !t.includes('budget plan') && !t.includes('invest') && !t.includes('goal plan');
  return hasAction && hasMoney && noPlan;
}

function parseExpense(text: string): { amount: number; category: string; description?: string; expense_date?: string } | null {
  const amountMatch = text.match(/(?:₹|rs\.?\s*)(\d+(?:\.\d+)?)|(\d+(?:\.\d+)?)\s*(?:₹|rs\.?|rupees?)/i);
  if (!amountMatch) return null;
  const amount = parseFloat(amountMatch[1] ?? amountMatch[2]);
  if (!amount || amount <= 0) return null;

  const t = text.toLowerCase();
  let category = 'Other';
  for (const [kw, cat] of Object.entries(CATEGORY_MAP)) {
    if (t.includes(kw)) { category = cat; break; }
  }

  let expense_date: string | undefined;
  const dm = text.match(/(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{4})/);
  if (dm) expense_date = `${dm[3]}-${dm[2].padStart(2,'0')}-${dm[1].padStart(2,'0')}`;

  // Extract description: words after the amount that aren't stop/date/amount words
  const STOP = new Set(['today','yesterday','add','expense','log','record','spent','bought','paid','for','using','via','on','the','a','an','my','i']);
  const amountIdx = text.search(/[₹]|\brs\.?\s*\d|\d+\s*(?:₹|rs\.?)/i);
  const afterFull = amountIdx >= 0 ? text.slice(amountIdx) : text;
  const numEnd    = afterFull.search(/\d/) + (afterFull.match(/\d+(?:\.\d+)?/)?.[0].length ?? 0);
  const trailing  = afterFull.slice(numEnd).trim();
  const descWords = trailing.split(/\s+/).filter((w) => w.length > 1 && !STOP.has(w.toLowerCase()) && !/^\d/.test(w) && !/[\/:₹]/.test(w));
  const description = descWords.length > 0 ? descWords.slice(0, 4).join(' ') : undefined;

  return { amount, category, description, expense_date };
}

// ─────────────────────────────────────────────────────────────────────────────
// Message types
// ─────────────────────────────────────────────────────────────────────────────

interface HitlState {
  pendingPayload: ChatPayload;
  missingFields:  FieldDef[];
}

interface Message {
  id:     string;
  role:   'user' | 'assistant';
  text:   string;
  status?: 'loading' | 'ok' | 'error' | 'hitl';
  plan?:  PlanResponse;
  hitl?:  HitlState;
}

// ─────────────────────────────────────────────────────────────────────────────
// Suggestion prompts
// ─────────────────────────────────────────────────────────────────────────────

const SUGGESTIONS: { icon: React.ElementType; label: string }[] = [
  { icon: BarChart2,  label: 'Help me create a budget plan' },
  { icon: TrendingUp, label: 'Where should I invest ₹50,000?' },
  { icon: Target,     label: 'Can I save ₹6,00,000 in 12 months?' },
  { icon: PlusCircle, label: 'Add expense ₹500 groceries today' },
];

// ─────────────────────────────────────────────────────────────────────────────
// Plan result display — renders backend PlanResponse fields directly
// No normalisation — show what the backend actually returned
// ─────────────────────────────────────────────────────────────────────────────

function PlanCard({ plan }: { plan: PlanResponse }) {
  const TYPE_COLOR: Record<string, string> = { budget: '#3B82F6', invest: '#8B5CF6', goal: '#10B981' };
  const color      = TYPE_COLOR[plan.plan_type] ?? '#6366F1';
  const outcomes   = plan.projected_outcomes ?? {};
  const conf       = plan.confidence;
  const overallPct = conf ? Math.round(Number(conf.overall ?? 0) * 100) : null;

  // Show numeric outcomes as key-value grid
  const numericOutcomes = Object.entries(outcomes).filter(([, v]) => typeof v === 'number');
  const displayKey = (k: string) => k.replace(/_/g, ' ');
  const displayVal = (k: string, v: number) => {
    if (k.includes('amount') || k.includes('savings') || k.includes('income') || k.includes('balance') || k.includes('target'))
      return `₹${v.toLocaleString('en-IN')}`;
    if (k.includes('rate') || k.includes('pct') || k.includes('ratio'))
      return `${(v <= 1 ? v * 100 : v).toFixed(1)}%`;
    if (k.includes('month'))
      return `${v} mo`;
    return String(v);
  };

  return (
    <div style={{ background: '#0F1219', border: `1px solid ${color}35`, borderRadius: 10, padding: 16, marginTop: 6 }}>
      {/* Header row */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <span style={{ background: `${color}18`, color, padding: '3px 10px', borderRadius: 99, fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.07em' }}>
            {plan.plan_type}
          </span>
          {plan.degraded && (
            <span style={{ background: 'rgba(245,158,11,0.15)', color: '#F59E0B', padding: '2px 8px', borderRadius: 99, fontSize: 10, fontWeight: 600 }}>
              degraded
            </span>
          )}
        </div>
        {overallPct !== null && (
          <span style={{ fontFamily: 'monospace', fontSize: 12, fontWeight: 700, color: overallPct >= 70 ? '#22C55E' : overallPct >= 40 ? '#F59E0B' : '#EF4444' }}>
            {overallPct}% confidence
          </span>
        )}
      </div>

      {/* Numeric outcomes grid */}
      {numericOutcomes.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(130px, 1fr))', gap: 8, marginBottom: 12 }}>
          {numericOutcomes.slice(0, 6).map(([k, v]) => (
            <div key={k} style={{ background: '#1A1D27', borderRadius: 8, padding: '8px 10px' }}>
              <p style={{ fontSize: 10, color: '#64748B', margin: '0 0 3px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                {displayKey(k)}
              </p>
              <p style={{ fontSize: 15, fontWeight: 700, color: '#F1F5F9', margin: 0, fontFamily: 'monospace' }}>
                {displayVal(k, v as number)}
              </p>
            </div>
          ))}
        </div>
      )}

      {/* Explanation */}
      {plan.explanation && (
        <p style={{ fontSize: 13, color: '#94A3B8', margin: '0 0 10px', lineHeight: 1.65 }}>
          {plan.explanation}
        </p>
      )}

      {/* Graph trace (collapsed) */}
      {plan.graph_trace?.length > 0 && (
        <details style={{ marginBottom: plan.plan_id ? 10 : 0 }}>
          <summary style={{ fontSize: 11, color: '#475569', cursor: 'pointer', userSelect: 'none' }}>
            Execution trace ({plan.graph_trace.length} nodes)
          </summary>
          <div style={{ marginTop: 6, display: 'flex', flexWrap: 'wrap', gap: 4 }}>
            {plan.graph_trace.map((node, i) => (
              <span key={i} style={{ fontSize: 10, background: '#1E2235', color: '#64748B', padding: '2px 7px', borderRadius: 4, fontFamily: 'monospace' }}>
                {node}
              </span>
            ))}
          </div>
        </details>
      )}

      {/* View full plan link */}
      {plan.plan_id && (
        <a
          href={`/plans/${plan.plan_type}?id=${plan.plan_id}`}
          style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 12, color, textDecoration: 'none', fontWeight: 600, marginTop: 6 }}
        >
          View full plan <ChevronRight size={11} />
        </a>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// HITL Form — shown inline when backend returns 422 with missing fields
// ─────────────────────────────────────────────────────────────────────────────

function HitlForm({ fields, onSubmit }: {
  fields:   FieldDef[];
  onSubmit: (values: Partial<ChatPayload>) => void;
}) {
  const [values, setValues] = useState<Record<string, string>>({});
  const allRequired = fields.filter((f) => f.key !== 'monthly_savings'); // monthly_savings is optional
  const allFilled   = allRequired.every((f) => (values[f.key] ?? '').trim() !== '');

  function handleSubmit() {
    if (!allFilled) return;
    const parsed: Partial<ChatPayload> = {};
    fields.forEach((f) => {
      const raw = (values[f.key] ?? '').trim();
      if (raw === '') return; // skip optional empty fields
      (parsed as Record<string, unknown>)[f.key] = f.parse(raw);
    });
    onSubmit(parsed);
  }

  return (
    <div style={{ background: '#0F1219', border: '1px solid #3730A3', borderRadius: 10, padding: 16, marginTop: 8 }}>
      <p style={{ fontSize: 11, color: '#A5B4FC', fontWeight: 700, margin: '0 0 14px', textTransform: 'uppercase', letterSpacing: '0.07em' }}>
        ✋ Need a few more details to proceed
      </p>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {fields.map((field) => (
          <div key={field.key}>
            <label style={{ display: 'block', fontSize: 12, color: '#94A3B8', marginBottom: 5 }}>
              {field.label}
              {field.key === 'monthly_savings' && <span style={{ color: '#475569', marginLeft: 6 }}>(optional)</span>}
            </label>
            {field.type === 'select' ? (
              <select
                value={values[field.key] ?? ''}
                onChange={(e) => setValues((v) => ({ ...v, [field.key]: e.target.value }))}
                style={{ width: '100%', background: '#1A1D27', border: '1px solid #2E3248', borderRadius: 6, padding: '9px 10px', color: values[field.key] ? '#F1F5F9' : '#475569', fontSize: 13 }}
              >
                <option value="">Select…</option>
                {field.options!.map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            ) : (
              <input
                type="text"
                inputMode="decimal"
                placeholder={field.placeholder}
                value={values[field.key] ?? ''}
                onChange={(e) => setValues((v) => ({ ...v, [field.key]: e.target.value }))}
                style={{ width: '100%', boxSizing: 'border-box', background: '#1A1D27', border: '1px solid #2E3248', borderRadius: 6, padding: '9px 10px', color: '#F1F5F9', fontSize: 13 }}
              />
            )}
          </div>
        ))}
      </div>
      <button
        onClick={handleSubmit}
        disabled={!allFilled}
        style={{ marginTop: 14, padding: '10px 22px', borderRadius: 8, border: 'none', cursor: allFilled ? 'pointer' : 'not-allowed', background: allFilled ? '#6366F1' : '#22263A', color: allFilled ? 'white' : '#475569', fontSize: 13, fontWeight: 700 }}
      >
        Generate Plan →
      </button>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main ChatInterface component
// ─────────────────────────────────────────────────────────────────────────────

export default function ChatInterface() {
  const router = useRouter();
  const [messages, setMessages] = useState<Message[]>([{
    id:     'welcome',
    role:   'assistant',
    status: 'ok',
    text:   "Hi! I'm your VaultAI Strategy Lab. Tell me what you need — budget plan, investment strategy, or a savings goal. I can also log expenses.\n\nJust describe what you want in plain English and I'll handle the rest.",
  }]);
  const [input,     setInput]     = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // ── helpers ───────────────────────────────────────────────────────────────

  function pushMsg(msg: Omit<Message, 'id'>): string {
    const id = `${Date.now()}-${Math.random()}`;
    setMessages((prev) => [...prev, { ...msg, id }]);
    return id;
  }

  function patchMsg(id: string, patch: Partial<Message>) {
    setMessages((prev) => prev.map((m) => m.id === id ? { ...m, ...patch } : m));
  }

  // ── core: call /plans/chat and handle every response case ─────────────────

  async function callChat(payload: ChatPayload, loadingId: string) {
    try {
      const plan = await sendChatMessage(payload) as unknown as PlanResponse;

      // Save to localStorage for /plans page
      if (plan.plan_id) {
        savePlanRef({ id: String(plan.plan_id), planType: plan.plan_type as 'budget' | 'invest' | 'goal' | 'simulate' });
      }

      const typeLabel = plan.plan_type.charAt(0).toUpperCase() + plan.plan_type.slice(1);
      patchMsg(loadingId, {
        status: 'ok',
        text:   `${typeLabel} plan created${plan.degraded ? ' — *(running in degraded mode)*' : ''}.`,
        plan,
      });
    } catch (err: unknown) {
      const e = err as ApiError;

      if (e.status === 401 || e.detail === 'unauthorized') {
        router.push('/auth');
        return;
      }

      // 422 — either missing params (HITL) or unrecognised intent
      if (e.status === 422) {
        const missingFields = parseMissingFields(e.detail ?? '');

        if (missingFields.length > 0) {
          // HITL: show inline form for missing fields
          patchMsg(loadingId, {
            status: 'hitl',
            text:   e.detail,
            hitl:   { pendingPayload: payload, missingFields },
          });
          return;
        }

        // 422 but no parseable field list — unrecognised intent
        patchMsg(loadingId, {
          status: 'error',
          text:   e.detail ?? 'Could not understand the request. Try being more specific.',
        });
        return;
      }

      // 501 — simulate/combined not yet implemented
      if (e.status === 501) {
        patchMsg(loadingId, {
          status: 'error',
          text:   e.detail ?? 'This plan type is not available yet.',
        });
        return;
      }

      // 503 — no expense history
      if (e.status === 503) {
        patchMsg(loadingId, {
          status: 'error',
          text:   e.detail ?? 'Could not load spending history. Please record some expenses first.',
        });
        return;
      }

      // Anything else
      patchMsg(loadingId, {
        status: 'error',
        text:   e.detail ?? e.message ?? 'Something went wrong. Please try again.',
      });
    } finally {
      setIsLoading(false);
    }
  }

  // ── handle user sending a message ────────────────────────────────────────

  async function handleSend(text: string) {
    if (!text.trim() || isLoading) return;
    setInput('');
    setIsLoading(true);

    pushMsg({ role: 'user', text });
    const loadingId = pushMsg({ role: 'assistant', text: 'Thinking…', status: 'loading' });

    // Check for expense operations first — clear intent before sending to plan endpoint
    if (isExpenseMessage(text)) {
      try {
        const parsed = parseExpense(text);
        if (!parsed) {
          patchMsg(loadingId, {
            status: 'error',
            text:   "Couldn't extract expense details. Try: \"Add ₹500 for Groceries on 25/12/2025\"",
          });
          setIsLoading(false);
          return;
        }
        await createExpense(parsed);
        patchMsg(loadingId, {
          status: 'ok',
          text:   `Added ₹${parsed.amount} under **${parsed.category}**${parsed.description ? ` — "${parsed.description}"` : ''}${parsed.expense_date ? ` on ${parsed.expense_date}` : ''}.`,
        });
      } catch (err: unknown) {
        const e = err as ApiError;
        if (e.status === 401) { router.push('/auth'); return; }
        patchMsg(loadingId, { status: 'error', text: e.detail ?? 'Failed to add expense.' });
      } finally {
        setIsLoading(false);
      }
      return;
    }

    // Delete expense
    if (/\b(delete|remove)\b.*\bexpense\b/i.test(text)) {
      const idMatch = text.match(/\b(\d+)\b/);
      if (!idMatch) {
        patchMsg(loadingId, { status: 'error', text: 'Please include the expense ID. Example: "Delete expense 42"' });
        setIsLoading(false);
        return;
      }
      try {
        await deleteExpense(parseInt(idMatch[1]));
        patchMsg(loadingId, { status: 'ok', text: `Expense #${idMatch[1]} deleted.` });
      } catch (err: unknown) {
        const e = err as ApiError;
        patchMsg(loadingId, { status: 'error', text: e.detail ?? 'Failed to delete expense.' });
      } finally {
        setIsLoading(false);
      }
      return;
    }

    // Everything else → /plans/chat
    // Backend classifies intent and returns 422 if params are missing
    await callChat({ message: text }, loadingId);
  }

  // ── HITL form submitted — merge values and retry ──────────────────────────

  async function handleHitlSubmit(msgId: string, collected: Partial<ChatPayload>) {
    const msg = messages.find((m) => m.id === msgId);
    if (!msg?.hitl) return;

    setIsLoading(true);
    const newPayload: ChatPayload = { ...msg.hitl.pendingPayload, ...collected };

    // Replace HITL message with a new loading state (same bubble)
    patchMsg(msgId, { status: 'loading', text: 'Generating your plan…', hitl: undefined });
    await callChat(newPayload, msgId);
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Render
  // ─────────────────────────────────────────────────────────────────────────

  const showSuggestions = messages.length <= 1;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>

      {/* ── Message thread ─────────────────────────────────────────────── */}
      <div style={{ flex: 1, overflowY: 'auto', paddingBottom: 16, display: 'flex', flexDirection: 'column', gap: 16 }}>
        {messages.map((msg) => (
          <div key={msg.id} style={{ display: 'flex', justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start', gap: 10, alignItems: 'flex-start' }}>

            {/* Avatar */}
            {msg.role === 'assistant' && (
              <div style={{ width: 32, height: 32, borderRadius: 8, background: 'linear-gradient(135deg,#6366F1,#8B5CF6)', flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', marginTop: 2 }}>
                <span style={{ fontSize: 13, fontWeight: 800, color: 'white' }}>V</span>
              </div>
            )}

            <div style={{ maxWidth: '78%', display: 'flex', flexDirection: 'column', alignItems: msg.role === 'user' ? 'flex-end' : 'flex-start' }}>

              {/* Bubble */}
              <div style={{
                padding: '10px 14px',
                borderRadius: msg.role === 'user' ? '12px 12px 2px 12px' : '12px 12px 12px 2px',
                background: msg.role === 'user' ? '#6366F1' : '#1A1D27',
                border: msg.role === 'user' ? 'none' : '1px solid #2E3248',
                fontSize: 14, color: '#F1F5F9', lineHeight: 1.65,
                display: 'flex', alignItems: 'flex-start', gap: 8,
              }}>
                {msg.status === 'loading' && <Loader2 size={14} color="#6366F1" style={{ animation: 'spin 1s linear infinite', flexShrink: 0, marginTop: 3 }} />}
                {msg.status === 'ok'      && <CheckCircle size={14} color="#10B981" style={{ flexShrink: 0, marginTop: 3 }} />}
                {msg.status === 'error'   && <AlertCircle size={14} color="#EF4444" style={{ flexShrink: 0, marginTop: 3 }} />}
                <span
                  style={{ whiteSpace: 'pre-wrap' }}
                  dangerouslySetInnerHTML={{ __html: msg.text.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>').replace(/\*(.*?)\*/g, '<em>$1</em>') }}
                />
              </div>

              {/* Plan card */}
              {msg.plan && <PlanCard plan={msg.plan} />}

              {/* HITL form */}
              {msg.hitl && (
                <HitlForm
                  fields={msg.hitl.missingFields}
                  onSubmit={(vals) => handleHitlSubmit(msg.id, vals)}
                />
              )}
            </div>
          </div>
        ))}

        {/* Suggestion chips — only on welcome */}
        {showSuggestions && (
          <div style={{ paddingLeft: 42, display: 'flex', flexDirection: 'column', gap: 6, marginTop: 4 }}>
            {SUGGESTIONS.map(({ icon: Icon, label }) => (
              <button
                key={label}
                onClick={() => handleSend(label)}
                style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '9px 14px', borderRadius: 10, background: '#1A1D27', border: '1px solid #2E3248', color: '#CBD5E1', fontSize: 13, cursor: 'pointer', textAlign: 'left', transition: 'border-color 0.15s, color 0.15s' }}
                onMouseEnter={(e) => { e.currentTarget.style.borderColor = '#6366F1'; e.currentTarget.style.color = '#F1F5F9'; }}
                onMouseLeave={(e) => { e.currentTarget.style.borderColor = '#2E3248'; e.currentTarget.style.color = '#CBD5E1'; }}
              >
                <Icon size={14} color="#6366F1" style={{ flexShrink: 0 }} />
                {label}
              </button>
            ))}
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* ── Input area ──────────────────────────────────────────────────── */}
      <div style={{ borderTop: '1px solid #2E3248', paddingTop: 14 }}>
        <div style={{ display: 'flex', gap: 10, alignItems: 'flex-end' }}>
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(input); } }}
            placeholder="Describe what you need — budget, invest, save for a goal, or log an expense…"
            rows={2}
            disabled={isLoading}
            style={{ flex: 1, resize: 'none', background: '#1A1D27', border: '1px solid #2E3248', borderRadius: 10, padding: '10px 14px', color: '#F1F5F9', fontSize: 14, outline: 'none', lineHeight: 1.5, fontFamily: 'inherit', opacity: isLoading ? 0.6 : 1 }}
            onFocus={(e)  => { e.currentTarget.style.borderColor = '#6366F1'; }}
            onBlur={(e)   => { e.currentTarget.style.borderColor = '#2E3248'; }}
          />
          <button
            onClick={() => handleSend(input)}
            disabled={!input.trim() || isLoading}
            style={{ width: 44, height: 44, flexShrink: 0, borderRadius: 10, border: 'none', background: input.trim() && !isLoading ? '#6366F1' : '#22263A', cursor: input.trim() && !isLoading ? 'pointer' : 'not-allowed', display: 'flex', alignItems: 'center', justifyContent: 'center', transition: 'background 0.15s' }}
          >
            {isLoading
              ? <Loader2 size={18} color="#6366F1" style={{ animation: 'spin 1s linear infinite' }} />
              : <Send    size={18} color={input.trim() ? 'white' : '#475569'} />
            }
          </button>
        </div>
        <p style={{ fontSize: 11, color: '#475569', margin: '6px 0 0' }}>
          Enter to send · Shift+Enter for new line · Plans are saved to My Plans automatically
        </p>
      </div>

      <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}