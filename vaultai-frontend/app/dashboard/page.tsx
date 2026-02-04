"use client";

import { useEffect, useState } from "react";
import {
  createExpense,
  getMe,
  getExpenses,
  getExpenseStats,
  updateExpense,
  deleteExpense,
} from "@/lib/api";

export default function Dashboard() {

  // ---------------- STATE ----------------

  const [amount, setAmount] = useState("");
  const [category, setCategory] = useState("");
  const [date, setDate] = useState("");
  const [description, setDescription] = useState("");

  const [extras, setExtras] = useState<{ key: string; value: string }[]>([]);

  const [latest, setLatest] = useState<any | null>(null);
  const [user, setUser] = useState<any | null>(null);

  const [expenses, setExpenses] = useState<any[]>([]);
  const [categories, setCategories] = useState<string[]>([]);
  const [filterCategory, setFilterCategory] = useState("");
  const [editingId, setEditingId] = useState<number | null>(null);


  // -------- A2 --------

  const [sortBy, setSortBy] = useState("");
  const [order, setOrder] = useState("desc");

  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");

  const [sortCategory, setSortCategory] = useState("");

  // -------- A3 --------

  const [showStats, setShowStats] = useState(false);
  const [statsFrom, setStatsFrom] = useState("");
  const [statsTo, setStatsTo] = useState("");

  const [stats, setStats] = useState<any | null>(null);


  // ---------------- STYLES ----------------

  const thStyle = {
    border: "1px solid #555",
    padding: "10px",
    background: "#222",
    textAlign: "left" as const,
  };

  const tdStyle = {
    border: "1px solid #555",
    padding: "10px",
    background: "#111",
  };

  const inputStyle = {
    padding: "6px",
    borderRadius: "4px",
    border: "1px solid #ccc",
  };


  // ---------------- EXTRA ----------------

  function addExtra() {
    setExtras([...extras, { key: "", value: "" }]);
  }

  function updateExtra(i: number, f: "key" | "value", v: string) {
    const copy = [...extras];
    copy[i][f] = v;
    setExtras(copy);
  }

  function removeExtra(i: number) {
    const copy = [...extras];
    copy.splice(i, 1);
    setExtras(copy);
  }


  // ---------------- LOGOUT ----------------

  function logout() {
    localStorage.removeItem("token");
    window.location.href = "/auth";
  }


  // ---------------- LOAD CATEGORIES ----------------

  async function loadCategories() {

    const data: any[] = await getExpenses();

    const unique = Array.from(
      new Set(data.map((e) => String(e.category)))
    );

    setCategories(unique);
  }


  // ---------------- LOAD EXPENSES ----------------

  async function loadExpenses(params: any = {}) {

    const data = await getExpenses(params);

    setExpenses(data);
  }


  // ---------------- ADD ----------------

  async function add() {

    if (!amount || !category || !date) {
      alert("Fill required fields");
      return;
    }

    const extraObj: Record<string, string> = {};

    extras.forEach((e) => {
      if (e.key && e.value) {
        extraObj[e.key] = e.value;
      }
    });

    let newExpense;

    if (editingId) {
      newExpense = await updateExpense(editingId, {
        amount: Number(amount),
        category,
        description,
        expense_date: date,
        extra_data: extraObj,
      });

      setEditingId(null);

    } else {

      newExpense = await createExpense({
        amount: Number(amount),
        category,
        description,
        expense_date: date,
        extra_data: extraObj,
      });

    }


    // Show immediately
    setLatest(newExpense);

    // Reload list properly from backend
    if (filterCategory === "all") {
      await loadExpenses();
    } else if (filterCategory) {
      await loadExpenses({ category: filterCategory });
    }

    setAmount("");
    setCategory("");
    setDate("");
    setDescription("");
    setExtras([]);

    await loadCategories();
  }


  // ---------------- AUTH ----------------

  useEffect(() => {

    const token = localStorage.getItem("token");

    if (!token) {
      window.location.href = "/auth";
      return;
    }

    getMe()
      .then(setUser)
      .catch(() => {
        localStorage.removeItem("token");
        window.location.href = "/auth";
      });

    loadCategories();

  }, []);


  // ---------------- A1 FILTER ----------------

  useEffect(() => {

    if (!filterCategory) {
      setExpenses([]);
      return;
    }

    if (filterCategory === "all") loadExpenses();
    else loadExpenses({ category: filterCategory });

  }, [filterCategory]);


  // ---------------- A2 APPLY ----------------

  async function applySort() {

    const params: any = {
      order,
    };

    if (sortBy === "date") {

      params.sort = "expense_date";

      if (fromDate) params.from_date = fromDate;
      if (toDate) params.to_date = toDate;
    }

    if (sortBy === "amount") {
      params.sort = "amount";
    }

    if (sortBy === "category") {

      if (!sortCategory) {
        alert("Select category");
        return;
      }

      params.sort = "category";
      params.category = sortCategory;
    }

    await loadExpenses(params);
  }


  // ---------------- A2 RESET ----------------

  function resetSort() {

    setSortBy("");
    setOrder("desc");
    setFromDate("");
    setToDate("");
    setSortCategory("");

    setExpenses([]);
  }


  // ---------------- A3 STATS ----------------

  async function loadStats() {

    try {

      const data = await getExpenseStats(
        statsFrom || undefined,
        statsTo || undefined
      );

      setStats(data);

    } catch {
      alert("Failed to load stats");
    }
  }


  // ---------------- UI ----------------

  return (
    <div style={{ padding: 40, color: "white" }}>

      {/* HEADER */}
      <div style={{ display: "flex", justifyContent: "space-between" }}>
        <h2>Dashboard</h2>

        <button
          onClick={logout}
          style={{
            background: "#2563eb",
            color: "white",
            padding: "8px 14px",
            borderRadius: "6px",
            border: "none",
          }}
        >
          Logout
        </button>
      </div>


      {/* USER */}
      {user && <p style={{ color: "#aaa" }}>{user.email}</p>}


      {/* ADD FORM */}
      <div style={{ marginTop: 25, display: "flex", gap: 10, flexWrap: "wrap" }}>

        <input style={inputStyle} placeholder="Amount"
          value={amount}
          onChange={(e) => setAmount(e.target.value)} />

        <input style={inputStyle} placeholder="Category"
          value={category}
          onChange={(e) => setCategory(e.target.value)} />

        <input style={inputStyle} type="date"
          value={date}
          onChange={(e) => setDate(e.target.value)} />

        <input style={inputStyle} placeholder="Description"
          value={description}
          onChange={(e) => setDescription(e.target.value)} />

      </div>


      {/* EXTRA */}
      <div style={{ marginTop: 15 }}>

        <h4>Extra Data</h4>

        {extras.map((ex, i) => (

          <div key={i} style={{ display: "flex", gap: 8 }}>

            <input style={inputStyle} placeholder="Key" value={ex.key}
              onChange={(e) => updateExtra(i, "key", e.target.value)} />

            <input style={inputStyle} placeholder="Value" value={ex.value}
              onChange={(e) => updateExtra(i, "value", e.target.value)} />

            <button onClick={() => removeExtra(i)}>X</button>

          </div>
        ))}

        <button onClick={addExtra}>+</button>

      </div>


      <button
        style={{
          marginTop: 15,
          background: "#2563eb",
          color: "white",
          padding: "8px 16px",
          borderRadius: "6px",
          border: "none",
        }}
        onClick={add}
      >
        Add Expense
      </button>


      {/* FILTER (A1) */}
      <div style={{ marginTop: 30 }}>

        <label>Filter: </label>

        <select
          value={filterCategory}
          onChange={(e) => setFilterCategory(e.target.value)}
          style={{ background: "white", color: "black", padding: 6 }}
        >
          <option value="">Select</option>
          <option value="all">All</option>

          {categories.map((c) => (
            <option key={c}>{c}</option>
          ))}
        </select>

      </div>


      {/* SORT (A2) */}
      <div style={{ marginTop: 30, borderTop: "1px solid #444", paddingTop: 20 }}>

        <h3>Advanced Sort</h3>

        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>

          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
            style={{ background: "white", color: "black", padding: 6 }}
          >
            <option value="">Sort By</option>
            <option value="date">Date</option>
            <option value="amount">Amount</option>
            <option value="category">Category</option>
          </select>


          {sortBy === "date" && (
            <>
              <input type="date" value={fromDate}
                onChange={(e) => setFromDate(e.target.value)} />

              <input type="date" value={toDate}
                onChange={(e) => setToDate(e.target.value)} />
            </>
          )}


          {sortBy === "category" && (

            <select
              value={sortCategory}
              onChange={(e) => setSortCategory(e.target.value)}
              style={{ background: "white", color: "black", padding: 6 }}
            >
              <option value="">Select Category</option>

              {categories.map((c) => (
                <option key={c}>{c}</option>
              ))}
            </select>
          )}


          <select
            value={order}
            onChange={(e) => setOrder(e.target.value)}
            style={{ background: "white", color: "black", padding: 6 }}
          >
            <option value="desc">Desc</option>
            <option value="asc">Asc</option>
          </select>


          <button onClick={applySort}>Apply</button>
          <button onClick={resetSort}>Reset</button>

        </div>

      </div>


      {/* A3 STATS (COLLAPSED) */}
      <div style={{ marginTop: 40, borderTop: "1px solid #444", paddingTop: 20 }}>

        <button
          onClick={() => setShowStats(!showStats)}
          style={{
            background: "#059669",
            color: "white",
            padding: "8px 16px",
            borderRadius: "6px",
            border: "none",
          }}
        >
          {showStats ? "Hide Stats" : "Show Stats"}
        </button>


        {showStats && (

          <div style={{ marginTop: 20 }}>

            <h3>Expense Insights</h3>

            <div style={{ display: "flex", gap: 10 }}>

              <input
                type="date"
                value={statsFrom}
                onChange={(e) => setStatsFrom(e.target.value)}
              />

              <input
                type="date"
                value={statsTo}
                onChange={(e) => setStatsTo(e.target.value)}
              />

              <button onClick={loadStats}>Get Stats</button>

            </div>


            {stats && (

              <div style={{ marginTop: 20 }}>

                <h4>Total: ₹ {stats.total}</h4>

                <h4>By Category:</h4>

                <ul>
                  {Object.entries(stats.by_category).map(
                    ([k, v]: any) => (
                      <li key={k}>
                        {k}: ₹ {v}
                      </li>
                    )
                  )}
                </ul>

              </div>
            )}

          </div>
        )}

      </div>


      {/* LIST */}
      {expenses.length > 0 && (

        <div style={{ marginTop: 30 }}>

          <h3>Expenses</h3>

          <table style={{ width: "100%", borderCollapse: "collapse" }}>

            <thead>
              <tr>
                <th style={thStyle}>Amount</th>
                <th style={thStyle}>Date</th>
                <th style={thStyle}>Category</th>
                <th style={thStyle}>Description</th>
                <th style={thStyle}>Actions</th>
              </tr>
            </thead>

            <tbody>

              {expenses.map((e) => (

                <tr key={e.id}>
                  <td style={tdStyle}>{e.amount}</td>
                  <td style={tdStyle}>{e.expense_date}</td>
                  <td style={tdStyle}>{e.category}</td>
                  <td style={tdStyle}>{e.description || "-"}</td>
                  <td style={tdStyle}>

                    <button
                      onClick={() => {
                        setEditingId(e.id);

                        setAmount(String(e.amount));
                        setCategory(e.category);
                        setDate(e.expense_date);
                        setDescription(e.description || "");
                        setExtras(
                          e.extra_data
                            ? Object.entries(e.extra_data).map(
                                ([k, v]) => ({ key: k, value: String(v) })
                              )
                            : []
                        );
                      }}
                    >
                      Edit
                    </button>


                    <button
                      style={{ marginLeft: 8, color: "red" }}
                      onClick={async () => {

                        if (!confirm("Delete this expense?")) return;

                        await deleteExpense(e.id);

                        setExpenses((prev) =>
                          prev.filter((x) => x.id !== e.id)
                        );
                      }}
                    >
                      Delete
                    </button>

                  </td>

                </tr>

              ))}

            </tbody>

          </table>

        </div>
      )}

    </div>
  );
}