"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  createExpense,
  getMe,
  getExpenses,
  getExpenseStats,
  updateExpense,
  deleteExpense,
} from "../../lib/backend";
import AuthenticatedLayout from "../components/Authenticatedlayout";

const CATEGORIES = ["Food", "Transport", "Shopping", "Utilities", "Health", "Entertainment", "Other"];

const CAT_COLORS: Record<string, string> = {
  food: "#F97316", transport: "#3B82F6", shopping: "#EC4899",
  utilities: "#8B5CF6", health: "#10B981", entertainment: "#F59E0B", other: "#6B7280",
};

function getCatColor(cat: string) {
  return CAT_COLORS[cat.toLowerCase()] ?? "#6B7280";
}

function fmt(n: number) {
  return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(n);
}

export default function Dashboard() {
  const router = useRouter();

  // ── state (ALL original logic kept) ──────────────────────────────
  const [amount, setAmount]           = useState("");
  const [category, setCategory]       = useState("Food");
  const [date, setDate]               = useState(new Date().toISOString().split("T")[0]);
  const [description, setDescription] = useState("");
  const [extras, setExtras]           = useState<{ key: string; value: string }[]>([]);
  const [user, setUser]               = useState<any>(null);
  const [expenses, setExpenses]       = useState<any[]>([]);
  const [categories, setCategories]   = useState<string[]>([]);
  const [filterCategory, setFilterCategory] = useState("");
  const [editingId, setEditingId]     = useState<number | null>(null);
  const [sortBy, setSortBy]           = useState("");
  const [order, setOrder]             = useState("desc");
  const [fromDate, setFromDate]       = useState("");
  const [toDate, setToDate]           = useState("");
  const [sortCategory, setSortCategory] = useState("");
  const [stats, setStats]             = useState<any>(null);
  const [showStats, setShowStats]     = useState(false);
  const [statsFrom, setStatsFrom]     = useState("");
  const [statsTo, setStatsTo]         = useState("");
  const [formError, setFormError]     = useState("");

  // ── helpers (ALL original logic kept) ────────────────────────────
  function addExtra() { setExtras([...extras, { key: "", value: "" }]); }
  function updateExtra(i: number, f: "key"|"value", v: string) {
    const copy = [...extras]; copy[i][f] = v; setExtras(copy);
  }
  function removeExtra(i: number) { const c = [...extras]; c.splice(i, 1); setExtras(c); }

  async function loadCategories() {
    const data: any[] = await getExpenses();
    setCategories(Array.from(new Set(data.map((e) => String(e.category)))));
  }

  async function loadExpenses(params: any = {}) {
    const data = await getExpenses(params);
    setExpenses(data);
  }

  async function add() {
    if (!amount || !category || !date) { setFormError("Amount, category and date are required"); return; }
    setFormError("");
    const extraObj: Record<string, string> = {};
    extras.forEach((e) => { if (e.key && e.value) extraObj[e.key] = e.value; });
    if (editingId) {
      await updateExpense(editingId, { amount: Number(amount), category, description, expense_date: date, extra_data: extraObj });
      setEditingId(null);
    } else {
      await createExpense({ amount: Number(amount), category, description, expense_date: date, extra_data: extraObj });
    }
    if (filterCategory === "all") await loadExpenses();
    else if (filterCategory) await loadExpenses({ category: filterCategory });
    setAmount(""); setCategory("Food"); setDate(new Date().toISOString().split("T")[0]);
    setDescription(""); setExtras([]);
    await loadCategories();
  }

  async function applySort() {
    const params: any = { order };
    if (sortBy === "date") { params.sort = "expense_date"; if (fromDate) params.from_date = fromDate; if (toDate) params.to_date = toDate; }
    if (sortBy === "amount") params.sort = "amount";
    if (sortBy === "category") { if (!sortCategory) { alert("Select category"); return; } params.sort = "category"; params.category = sortCategory; }
    await loadExpenses(params);
  }

  function resetSort() { setSortBy(""); setOrder("desc"); setFromDate(""); setToDate(""); setSortCategory(""); setExpenses([]); }

  async function loadStats() {
    try { const data = await getExpenseStats(statsFrom || undefined, statsTo || undefined); setStats(data); }
    catch { alert("Failed to load stats"); }
  }

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) { router.push("/auth"); return; }
    getMe().then(setUser).catch(() => { localStorage.removeItem("token"); router.push("/auth"); });
    loadCategories();
  }, []);

  useEffect(() => {
    if (!filterCategory) { setExpenses([]); return; }
    if (filterCategory === "all") loadExpenses();
    else loadExpenses({ category: filterCategory });
  }, [filterCategory]);

  // ── stats ─────────────────────────────────────────────────────────
  const totalThisMonth = expenses.reduce((s, e) => s + (e.amount ?? 0), 0);
  const topCat = categories[0] ?? "—";

  const inp = {
    padding: "9px 12px", borderRadius: 8, border: "1px solid #2E3248",
    background: "#22263A", color: "#F1F5F9", fontSize: 14,
    outline: "none", boxSizing: "border-box" as const,
  };

  const sel = { ...inp };

  return (
    <AuthenticatedLayout
      title="Dashboard"
      action={
        user && (
          <span style={{ fontSize: 13, color: "#475569" }}>{user.email}</span>
        )
      }
    >
      {/* Stats bar */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 16, marginBottom: 28 }}>
        {[
          { label: "TOTAL (FILTERED)", value: fmt(totalThisMonth) },
          { label: "TRANSACTIONS",     value: String(expenses.length) },
          { label: "TOP CATEGORY",     value: topCat },
          { label: "CATEGORIES",       value: String(categories.length) },
        ].map(({ label, value }) => (
          <div key={label} style={{ background: "#1A1D27", border: "1px solid #2E3248", borderRadius: 12, padding: "16px 20px" }}>
            <p style={{ fontSize: 11, color: "#475569", margin: "0 0 8px", textTransform: "uppercase", letterSpacing: "0.06em" }}>{label}</p>
            <p style={{ fontSize: 22, fontWeight: 700, color: "#F1F5F9", margin: 0, fontFamily: "monospace" }}>{value}</p>
          </div>
        ))}
      </div>

      {/* Add / Edit form */}
      <div style={{ background: "#1A1D27", border: "1px solid #2E3248", borderRadius: 12, padding: "20px 24px", marginBottom: 24 }}>
        <p style={{ fontSize: 13, fontWeight: 600, color: "#94A3B8", margin: "0 0 14px", textTransform: "uppercase", letterSpacing: "0.06em" }}>
          {editingId ? "Edit Expense" : "Add Expense"}
        </p>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "flex-end" }}>
          <input style={{ ...inp, width: 120 }} placeholder="Amount" type="number" value={amount} onChange={(e) => setAmount(e.target.value)} />
          <select style={{ ...sel, width: 160 }} value={category} onChange={(e) => setCategory(e.target.value)}>
            {CATEGORIES.map((c) => <option key={c}>{c}</option>)}
          </select>
          <input style={{ ...inp, flex: 1, minWidth: 160 }} placeholder="Description" value={description} onChange={(e) => setDescription(e.target.value)} />
          <input style={{ ...inp, width: 150 }} type="date" value={date} onChange={(e) => setDate(e.target.value)} />
          <button
            onClick={add}
            style={{ padding: "9px 20px", borderRadius: 8, background: "#6366F1", color: "white", border: "none", cursor: "pointer", fontSize: 14, fontWeight: 500 }}
          >
            {editingId ? "Update" : "+ Add"}
          </button>
          {editingId && (
            <button onClick={() => { setEditingId(null); setAmount(""); setCategory("Food"); setDescription(""); setDate(new Date().toISOString().split("T")[0]); setExtras([]); }}
              style={{ padding: "9px 14px", borderRadius: 8, background: "transparent", color: "#94A3B8", border: "1px solid #2E3248", cursor: "pointer", fontSize: 14 }}>
              Cancel
            </button>
          )}
        </div>
        {formError && <p style={{ fontSize: 12, color: "#EF4444", margin: "8px 0 0" }}>{formError}</p>}
      </div>

      {/* Filters + Sort */}
      <div style={{ background: "#1A1D27", border: "1px solid #2E3248", borderRadius: 12, padding: "16px 20px", marginBottom: 20 }}>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
          <select style={{ ...sel, width: 160 }} value={filterCategory} onChange={(e) => setFilterCategory(e.target.value)}>
            <option value="">Filter by category</option>
            <option value="all">All</option>
            {categories.map((c) => <option key={c}>{c}</option>)}
          </select>

          <select style={{ ...sel, width: 140 }} value={sortBy} onChange={(e) => setSortBy(e.target.value)}>
            <option value="">Sort by</option>
            <option value="date">Date</option>
            <option value="amount">Amount</option>
            <option value="category">Category</option>
          </select>

          {sortBy === "date" && (
            <>
              <input type="date" style={{ ...inp, width: 140 }} value={fromDate} onChange={(e) => setFromDate(e.target.value)} />
              <input type="date" style={{ ...inp, width: 140 }} value={toDate} onChange={(e) => setToDate(e.target.value)} />
            </>
          )}
          {sortBy === "category" && (
            <select style={{ ...sel, width: 150 }} value={sortCategory} onChange={(e) => setSortCategory(e.target.value)}>
              <option value="">Select category</option>
              {categories.map((c) => <option key={c}>{c}</option>)}
            </select>
          )}

          <select style={{ ...sel, width: 110 }} value={order} onChange={(e) => setOrder(e.target.value)}>
            <option value="desc">Descending</option>
            <option value="asc">Ascending</option>
          </select>

          <button onClick={applySort} style={{ padding: "9px 16px", borderRadius: 8, background: "#22263A", color: "#F1F5F9", border: "1px solid #2E3248", cursor: "pointer", fontSize: 13 }}>Apply</button>
          <button onClick={resetSort} style={{ padding: "9px 16px", borderRadius: 8, background: "transparent", color: "#475569", border: "1px solid #2E3248", cursor: "pointer", fontSize: 13 }}>Reset</button>
        </div>
      </div>

      {/* Expense table */}
      {expenses.length > 0 ? (
        <div style={{ background: "#1A1D27", border: "1px solid #2E3248", borderRadius: 12, overflow: "hidden" }}>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ borderBottom: "1px solid #2E3248" }}>
                {["Date", "Description", "Category", "Amount", "Actions"].map((h) => (
                  <th key={h} style={{ padding: "12px 16px", textAlign: "left", fontSize: 11, fontWeight: 600, color: "#475569", textTransform: "uppercase", letterSpacing: "0.06em" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {expenses.map((e) => (
                <tr key={e.id} style={{ borderBottom: "1px solid #2E3248" }}
                  onMouseEnter={(el) => (el.currentTarget as HTMLTableRowElement).style.background = "#22263A"}
                  onMouseLeave={(el) => (el.currentTarget as HTMLTableRowElement).style.background = "transparent"}
                >
                  <td style={{ padding: "13px 16px", fontSize: 13, color: "#94A3B8" }}>{e.expense_date}</td>
                  <td style={{ padding: "13px 16px", fontSize: 14, color: "#F1F5F9" }}>{e.description || "—"}</td>
                  <td style={{ padding: "13px 16px" }}>
                    <span style={{ display: "inline-flex", alignItems: "center", gap: 6, padding: "3px 10px", borderRadius: 99, fontSize: 11, fontWeight: 600, background: `${getCatColor(e.category)}20`, color: getCatColor(e.category) }}>
                      {e.category}
                    </span>
                  </td>
                  <td style={{ padding: "13px 16px", fontSize: 14, fontFamily: "monospace", color: "#F1F5F9", textAlign: "right" }}>{fmt(e.amount)}</td>
                  <td style={{ padding: "13px 16px" }}>
                    <button onClick={() => { setEditingId(e.id); setAmount(String(e.amount)); setCategory(e.category); setDate(e.expense_date); setDescription(e.description || ""); setExtras(e.extra_data ? Object.entries(e.extra_data).map(([k, v]) => ({ key: k, value: String(v) })) : []); }}
                      style={{ padding: "4px 10px", borderRadius: 6, background: "transparent", color: "#94A3B8", border: "1px solid #2E3248", cursor: "pointer", fontSize: 12, marginRight: 6 }}>Edit</button>
                    <button onClick={async () => { if (!confirm("Delete?")) return; await deleteExpense(e.id); setExpenses((p) => p.filter((x) => x.id !== e.id)); }}
                      style={{ padding: "4px 10px", borderRadius: 6, background: "transparent", color: "#EF4444", border: "1px solid rgba(239,68,68,0.3)", cursor: "pointer", fontSize: 12 }}>Delete</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div style={{ background: "#1A1D27", border: "1px solid #2E3248", borderRadius: 12, padding: 40, textAlign: "center" }}>
          <p style={{ fontSize: 24, marginBottom: 12 }}>📊</p>
          <p style={{ fontSize: 15, fontWeight: 600, color: "#F1F5F9", margin: "0 0 6px" }}>No expenses yet</p>
          <p style={{ fontSize: 13, color: "#475569", margin: 0 }}>
            {filterCategory ? "No expenses match the selected filter." : "Select a category filter or add your first expense above."}
          </p>
        </div>
      )}

      {/* Stats section */}
      <div style={{ marginTop: 28, borderTop: "1px solid #2E3248", paddingTop: 24 }}>
        <button onClick={() => setShowStats(!showStats)}
          style={{ padding: "9px 18px", borderRadius: 8, background: "transparent", color: "#94A3B8", border: "1px solid #2E3248", cursor: "pointer", fontSize: 13 }}>
          {showStats ? "▲ Hide Stats" : "▼ Show Stats"}
        </button>

        {showStats && (
          <div style={{ marginTop: 16, background: "#1A1D27", border: "1px solid #2E3248", borderRadius: 12, padding: 20 }}>
            <p style={{ fontSize: 13, fontWeight: 600, color: "#94A3B8", margin: "0 0 14px", textTransform: "uppercase", letterSpacing: "0.06em" }}>Expense Stats</p>
            <div style={{ display: "flex", gap: 10, marginBottom: 14 }}>
              <input type="date" value={statsFrom} onChange={(e) => setStatsFrom(e.target.value)} style={{ ...inp, width: 150 }} />
              <input type="date" value={statsTo} onChange={(e) => setStatsTo(e.target.value)} style={{ ...inp, width: 150 }} />
              <button onClick={loadStats} style={{ padding: "9px 16px", borderRadius: 8, background: "#6366F1", color: "white", border: "none", cursor: "pointer", fontSize: 13 }}>Get Stats</button>
            </div>
            {stats && (
              <div>
                <p style={{ fontSize: 18, fontWeight: 700, color: "#F1F5F9", fontFamily: "monospace", margin: "0 0 12px" }}>Total: {fmt(stats.total)}</p>
                <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                  {Object.entries(stats.by_category).map(([k, v]: any) => (
                    <div key={k} style={{ display: "flex", justifyContent: "space-between", padding: "8px 12px", background: "#22263A", borderRadius: 8 }}>
                      <span style={{ fontSize: 13, color: "#94A3B8", textTransform: "capitalize" }}>{k}</span>
                      <span style={{ fontSize: 13, color: "#F1F5F9", fontFamily: "monospace" }}>{fmt(v)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </AuthenticatedLayout>
  );
}