'use client';
import { useState, useRef, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Send, Loader2, CheckCircle, AlertCircle, TrendingUp, Target, BarChart2, Zap, PlusCircle } from 'lucide-react';
import {
  createExpense,
  deleteExpense,
  createBudgetPlan,
  createInvestPlan,
  createGoalPlan,
  sendChatMessage,
} from '../../lib/backend';
import { savePlanRef } from '../../app/plans/page';
import PlanCard from './PlanCard';
import type { Plan } from '../../lib/types/plans';

// ─── Types ────────────────────────────────────────────────────────────────────

type MessageRole = 'assistant' | 'user';
type MessageStatus = 'ok' | 'error' | 'loading';

interface Message {
  id: string;
  role: MessageRole;
  text: string;
  status?: MessageStatus;
  plan?: Plan;
}

// ─── Intent detection ─────────────────────────────────────────────────────────

type Intent =
  | 'add_expense'
  | 'delete_expense'
  | 'budget_plan'
  | 'invest_plan'
  | 'goal_plan'
  | 'simulate'
  | 'chat';

function detectIntent(text: string): Intent {
  const t = text.toLowerCase();

  // Expense operations — check before plan detection
  if (
    (t.includes('add') || t.includes('log') || t.includes('record') || t.includes('spent') || t.includes('bought') || t.includes('paid')) &&
    (t.includes('expense') || t.includes('₹') || t.includes('rs') || t.includes('rupee') ||
      /\d+/.test(t)) &&
    !t.includes('plan') && !t.includes('budget plan')
  ) return 'add_expense';

  if (t.includes('delete') || t.includes('remove') || t.includes('undo expense'))
    return 'delete_expense';

  // Plan intents
  if (t.includes('budget') || t.includes('income') || t.includes('salary') || t.includes('monthly expense'))
    return 'budget_plan';

  if (t.includes('invest') || t.includes('portfolio') || t.includes('stock') || t.includes('mutual fund') || t.includes('sip') || t.includes('risk'))
    return 'invest_plan';

  if (t.includes('goal') || t.includes('save') || t.includes('saving') || t.includes('target') || t.includes('debt') || t.includes('loan') || t.includes('in ') && t.includes('month'))
    return 'goal_plan';

  if (t.includes('simulat') || t.includes('what if') || t.includes('what-if') || t.includes('scenario') || t.includes('forecast'))
    return 'simulate';

  return 'chat';
}

// ─── Expense parser ───────────────────────────────────────────────────────────

interface ParsedExpense {
  amount: number;
  category: string;
  description?: string;
  expense_date?: string;
}

const CATEGORY_MAP: Record<string, string> = {
  food: 'Food', grocery: 'Food', groceries: 'Food', restaurant: 'Food', eat: 'Food',
  transport: 'Transport', travel: 'Transport', cab: 'Transport', uber: 'Transport', ola: 'Transport', auto: 'Transport', bus: 'Transport', train: 'Transport', fuel: 'Transport', petrol: 'Transport',
  shopping: 'Shopping', clothes: 'Shopping', clothing: 'Shopping', amazon: 'Shopping', flipkart: 'Shopping',
  utilities: 'Utilities', electricity: 'Utilities', water: 'Utilities', gas: 'Utilities', internet: 'Utilities', wifi: 'Utilities', mobile: 'Utilities', phone: 'Utilities', recharge: 'Utilities',
  health: 'Health', medicine: 'Health', doctor: 'Health', hospital: 'Health', pharmacy: 'Health', gym: 'Health',
  entertainment: 'Entertainment', movie: 'Entertainment', netflix: 'Entertainment', spotify: 'Entertainment', game: 'Entertainment',
};

function parseExpense(text: string): ParsedExpense | null {
  // Extract amount — handles ₹500, 500rs, rs500, 500 rupees, Rs. 500
  const amountMatch = text.match(/(?:₹|rs\.?\s*|rupees?\s*)(\d+(?:\.\d+)?)|(\d+(?:\.\d+)?)\s*(?:₹|rs\.?|rupees?)/i);
  if (!amountMatch) return null;
  const amount = parseFloat(amountMatch[1] ?? amountMatch[2]);
  if (!amount || amount <= 0) return null;

  // Extract category
  const t = text.toLowerCase();
  let category = 'Other';
  for (const [keyword, cat] of Object.entries(CATEGORY_MAP)) {
    if (t.includes(keyword)) { category = cat; break; }
  }

  // Extract date — handles 25/12/2025, 2025-12-25, Dec 25, dated X
  let expense_date: string | undefined;
  const datePatterns = [
    /(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{4})/,         // 25/12/2025
    /(\d{4})[\/\-](\d{1,2})[\/\-](\d{1,2})/,         // 2025-12-25
    /dated?\s+(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{4})/i,
  ];
  for (const pattern of datePatterns) {
    const m = text.match(pattern);
    if (m) {
      // normalise to YYYY-MM-DD
      if (m[1].length === 4) {
        expense_date = `${m[1]}-${m[2].padStart(2,'0')}-${m[3].padStart(2,'0')}`;
      } else {
        expense_date = `${m[3]}-${m[2].padStart(2,'0')}-${m[1].padStart(2,'0')}`;
      }
      break;
    }
  }

  // Description — what was bought
  const descMatch = text.match(/(?:bought|purchased|for|on)\s+(.+?)(?:\s+(?:using|via|through|with|dated?|on \d|$))/i);
  const description = descMatch?.[1]?.trim();

  return { amount, category, description, expense_date };
}

// ─── Plan payload extractors ──────────────────────────────────────────────────

function extractBudgetPayload(text: string): Record<string, unknown> {
  const incomeMatch = text.match(/(?:₹|rs\.?\s*)?(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:k|K|thousand|lakh|L)?\s*(?:\/month|per month|monthly|month|pm)?/i);
  let income = 80000;
  if (incomeMatch) {
    const raw = parseFloat(incomeMatch[1].replace(/,/g, ''));
    const lower = text.toLowerCase();
    if (lower.includes('lakh') || lower.includes(' l') || raw < 1000) income = raw * 100000;
    else if (lower.includes('k') || (raw > 0 && raw < 1000)) income = raw * 1000;
    else income = raw;
  }
  return { income_monthly: income };
}

function extractInvestPayload(text: string): Record<string, unknown> {
  const t = text.toLowerCase();
  const risk = t.includes('high') ? 'high' : t.includes('low') || t.includes('safe') || t.includes('conservative') ? 'low' : 'moderate';
  const amountMatch = text.match(/(?:₹|rs\.?\s*)?(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:k|K)?/i);
  const amount = amountMatch ? parseFloat(amountMatch[1].replace(/,/g, '')) * (text.toLowerCase().includes('k') ? 1000 : 1) : 10000;
  return { risk_profile: risk, monthly_amount: amount };
}

function extractGoalPayload(text: string): Record<string, unknown> {
  const amountMatch = text.match(/(?:₹|rs\.?\s*)?(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:k|K|lakh|L)?/i);
  const monthsMatch = text.match(/(\d+)\s*(?:months?|mo)/i);
  const t = text.toLowerCase();
  let target = 600000;
  if (amountMatch) {
    const raw = parseFloat(amountMatch[1].replace(/,/g, ''));
    target = t.includes('lakh') || t.includes(' l') ? raw * 100000 : t.includes('k') ? raw * 1000 : raw;
  }
  const horizon = monthsMatch ? parseInt(monthsMatch[1]) : 12;
  return { target_amount: target, horizon_months: horizon, goal_type: 'savings' };
}

// ─── Suggested prompts ────────────────────────────────────────────────────────

const SUGGESTIONS = [
  { icon: BarChart2,  label: 'Create a budget plan for ₹80K/month income',        intent: 'budget_plan'  as Intent },
  { icon: TrendingUp, label: 'Suggest an investment plan for moderate risk',         intent: 'invest_plan'  as Intent },
  { icon: Target,     label: 'Help me plan to save ₹6L in 12 months',               intent: 'goal_plan'    as Intent },
  { icon: Zap,        label: 'Run a simulation with ₹25K/month savings',            intent: 'simulate'     as Intent },
  { icon: PlusCircle, label: 'Add an expense of ₹500 for Groceries today',          intent: 'add_expense'  as Intent },
];

// ─── Component ────────────────────────────────────────────────────────────────

export default function ChatInterface() {
  const router = useRouter();
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 'welcome',
      role: 'assistant',
      text: "Hi! I'm your VaultAI Strategy Lab. I can help you create budget plans, investment strategies, goal projections, and run financial simulations. What would you like to explore?",
    },
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  function addMessage(msg: Omit<Message, 'id'>) {
    const id = `${Date.now()}-${Math.random()}`;
    setMessages((prev) => [...prev, { ...msg, id }]);
    return id;
  }

  function updateMessage(id: string, updates: Partial<Message>) {
    setMessages((prev) => prev.map((m) => m.id === id ? { ...m, ...updates } : m));
  }

  async function handleSend(text: string) {
    if (!text.trim() || isLoading) return;
    setInput('');
    setIsLoading(true);

    addMessage({ role: 'user', text });

    const loadingId = addMessage({ role: 'assistant', text: 'Thinking…', status: 'loading' });

    try {
      const intent = detectIntent(text);

      // ── Expense: add ──────────────────────────────────────────────────────
      if (intent === 'add_expense') {
        const parsed = parseExpense(text);
        if (!parsed) {
          updateMessage(loadingId, {
            text: "I couldn't extract the expense details. Try something like: \"Add ₹500 for Groceries on 25/12/2025\"",
            status: 'error',
          });
          return;
        }
        await createExpense({
          amount:       parsed.amount,
          category:     parsed.category,
          description:  parsed.description,
          expense_date: parsed.expense_date,
        });
        updateMessage(loadingId, {
          status: 'ok',
          text: `✅ Added **₹${parsed.amount}** in **${parsed.category}**${parsed.description ? ` for "${parsed.description}"` : ''}${parsed.expense_date ? ` on ${parsed.expense_date}` : ''}.`,
        });
        return;
      }

      // ── Expense: delete ───────────────────────────────────────────────────
      if (intent === 'delete_expense') {
        const idMatch = text.match(/\b(\d+)\b/);
        if (!idMatch) {
          updateMessage(loadingId, {
            text: "Please include the expense ID to delete. Example: \"Delete expense 42\"",
            status: 'error',
          });
          return;
        }
        await deleteExpense(parseInt(idMatch[1]));
        updateMessage(loadingId, { status: 'ok', text: `✅ Expense #${idMatch[1]} deleted.` });
        return;
      }

      // ── Simulate → redirect to simulator ─────────────────────────────────
      if (intent === 'simulate') {
        updateMessage(loadingId, {
          status: 'ok',
          text: "Opening the What-If Simulator for you — you can set custom parameters and compare scenarios there.",
        });
        setTimeout(() => router.push('/simulate'), 800);
        return;
      }

      // ── Plan creation ─────────────────────────────────────────────────────
      let plan: Plan | null = null;
      let confirmText = '';

      if (intent === 'budget_plan') {
        const result = await createBudgetPlan(extractBudgetPayload(text));
        plan = result as unknown as Plan;
        const pct = Math.round((result.confidence?.overall || 0) * 100);
        confirmText = `Budget plan created with **${pct}% confidence**.`;

      } else if (intent === 'invest_plan') {
        const result = await createInvestPlan(extractInvestPayload(text));
        plan = result as unknown as Plan;
        const rp = (result as unknown as Record<string, unknown>).riskProfile as string | undefined;
        confirmText = `Investment plan created — **${rp ?? 'moderate'} risk** profile.`;

      } else if (intent === 'goal_plan') {
        const result = await createGoalPlan(extractGoalPayload(text));
        plan = result as unknown as Plan;
        const fl = (result as unknown as Record<string, unknown>).feasibilityLabel as string | undefined;
        confirmText = `Goal plan created. Feasibility: **${fl ?? 'FEASIBLE'}**.`;

      } else {
        // Catch-all: POST /plans/chat — ChatResponse has plan?: Plan
        const response = await sendChatMessage(text);
        plan = response.plan ?? null;
        confirmText = response.message || 'Plan created via AI chat.';
      }

      if (plan) {
        const p = plan as unknown as Record<string, unknown>;
        savePlanRef({
          id: p.id as string,
          planType: (p.planType ?? p.plan_type) as import('../../lib/types/plans').PlanType,
        });
        updateMessage(loadingId, { status: 'ok', text: confirmText, plan });
      } else {
        updateMessage(loadingId, { status: 'ok', text: confirmText });
      }


    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Something went wrong';
      if (msg === 'unauthorized') { router.push('/auth'); return; }
      updateMessage(loadingId, { status: 'error', text: `❌ ${msg}` });
    } finally {
      setIsLoading(false);
    }
  }

  const showSuggestions = messages.length <= 1;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', gap: 0 }}>
      {/* Messages */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '0 0 16px', display: 'flex', flexDirection: 'column', gap: 16 }}>
        {messages.map((msg) => (
          <div
            key={msg.id}
            style={{
              display: 'flex',
              justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
              gap: 10,
              alignItems: 'flex-start',
            }}
          >
            {msg.role === 'assistant' && (
              <div style={{ width: 32, height: 32, borderRadius: 8, background: 'linear-gradient(135deg,#6366F1,#8B5CF6)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, marginTop: 2 }}>
                <span style={{ fontSize: 14, fontWeight: 800, color: 'white' }}>V</span>
              </div>
            )}

            <div style={{ maxWidth: '75%', display: 'flex', flexDirection: 'column', gap: 8, alignItems: msg.role === 'user' ? 'flex-end' : 'flex-start' }}>
              <div style={{
                padding: '10px 14px',
                borderRadius: msg.role === 'user' ? '12px 12px 2px 12px' : '12px 12px 12px 2px',
                background: msg.role === 'user' ? '#6366F1' : '#1A1D27',
                border: msg.role === 'user' ? 'none' : '1px solid #2E3248',
                fontSize: 14,
                color: '#F1F5F9',
                lineHeight: 1.6,
                display: 'flex',
                alignItems: 'center',
                gap: 8,
              }}>
                {msg.status === 'loading' && <Loader2 size={14} color="#6366F1" style={{ animation: 'spin 1s linear infinite', flexShrink: 0 }} />}
                {msg.status === 'ok' && <CheckCircle size={14} color="#10B981" style={{ flexShrink: 0 }} />}
                {msg.status === 'error' && <AlertCircle size={14} color="#EF4444" style={{ flexShrink: 0 }} />}
                <span dangerouslySetInnerHTML={{ __html: msg.text.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>') }} />
              </div>

              {/* Inline plan card */}
              {msg.plan && (
                <div style={{ width: 340 }}>
                  <PlanCard plan={msg.plan} />
                </div>
              )}
            </div>
          </div>
        ))}

        {/* Suggested prompts — only shown on welcome screen */}
        {showSuggestions && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 8, paddingLeft: 42 }}>
            {SUGGESTIONS.map(({ icon: Icon, label }) => (
              <button
                key={label}
                onClick={() => handleSend(label)}
                style={{
                  display: 'flex', alignItems: 'center', gap: 10,
                  padding: '10px 14px', borderRadius: 10, cursor: 'pointer',
                  background: '#1A1D27', border: '1px solid #2E3248',
                  color: '#CBD5E1', fontSize: 13, textAlign: 'left',
                  transition: 'border-color 0.15s',
                }}
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

      {/* Input */}
      <div style={{ borderTop: '1px solid #2E3248', paddingTop: 16 }}>
        <div style={{ display: 'flex', gap: 10, alignItems: 'flex-end' }}>
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(input); } }}
            placeholder="Ask me to create a plan, add an expense, or run a simulation…"
            rows={2}
            style={{
              flex: 1, resize: 'none', background: '#1A1D27',
              border: '1px solid #2E3248', borderRadius: 10,
              padding: '10px 14px', color: '#F1F5F9', fontSize: 14,
              outline: 'none', lineHeight: 1.5, fontFamily: 'inherit',
            }}
            onFocus={(e) => { e.currentTarget.style.borderColor = '#6366F1'; }}
            onBlur={(e) => { e.currentTarget.style.borderColor = '#2E3248'; }}
          />
          <button
            onClick={() => handleSend(input)}
            disabled={!input.trim() || isLoading}
            style={{
              width: 44, height: 44, borderRadius: 10, flexShrink: 0,
              background: input.trim() && !isLoading ? '#6366F1' : '#22263A',
              border: 'none', cursor: input.trim() && !isLoading ? 'pointer' : 'not-allowed',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              transition: 'background 0.15s',
            }}
          >
            {isLoading
              ? <Loader2 size={18} color="#6366F1" style={{ animation: 'spin 1s linear infinite' }} />
              : <Send size={18} color={input.trim() ? 'white' : '#475569'} />
            }
          </button>
        </div>
        <p style={{ fontSize: 11, color: '#475569', margin: '8px 0 0' }}>
          Enter to send · Shift+Enter for new line · Plans are saved to My Plans
        </p>
      </div>

      <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}