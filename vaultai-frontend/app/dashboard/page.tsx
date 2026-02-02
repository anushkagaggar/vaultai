"use client";

import { useEffect, useState } from "react";
import { createExpense, getMe, getExpenses } from "@/lib/api";

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

  // Filters (A1 + A2)

  const [filterCategory, setFilterCategory] = useState("");
  const [sortBy, setSortBy] = useState("expense_date");
  const [order, setOrder] = useState("desc");

  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");

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
    padding: "8px",
    background: "#111",
    color: "white",
    border: "1px solid #444",
    borderRadius: "4px",
  };

  // ---------------- EXTRA DATA ----------------

  function addExtra() {
    setExtras([...extras, { key: "", value: "" }]);
  }

  function updateExtra(i: number, field: "key" | "value", val: string) {
    const copy = [...extras];
    copy[i][field] = val;
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

  // ---------------- LOAD EXPENSES ----------------

  async function loadExpenses() {
    try {

      // A1: Do nothing unless user explicitly filters
      if (!filterCategory) {
        setExpenses([]);
        return;
      }

      const data = await getExpenses({
        category:
          filterCategory === "all"
            ? undefined
            : filterCategory,

        sort: sortBy,
        order,

        from_date: fromDate || undefined,
        to_date: toDate || undefined,
      });

      setExpenses(data);

    } catch {
      alert("Failed to load expenses");
    }
  }

  // ---------------- ADD EXPENSE ----------------

  async function add() {
    try {

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

      const newExpense = await createExpense({
        amount: Number(amount),
        category,
        description,
        expense_date: date,
        extra_data: extraObj,
      });

      setLatest(newExpense);

      setAmount("");
      setCategory("");
      setDate("");
      setDescription("");
      setExtras([]);

      // Reload only if filter active
      if (filterCategory) {
        loadExpenses();
      }

    } catch (err: any) {
      alert(err.message || "Failed");
    }
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

  }, []);

  // ---------------- APPLY FILTER ----------------

  function applyFilters() {
    loadExpenses();
  }

  function resetFilters() {

    setFilterCategory("");
    setSortBy("expense_date");
    setOrder("desc");
    setFromDate("");
    setToDate("");
    setExpenses([]);
  }

  // ---------------- UNIQUE CATEGORIES ----------------

  const categories = Array.from(
    new Set(expenses.map((e) => e.category))
  );

  // ---------------- UI ----------------

  return (
    <div style={{ padding: 40, color: "white" }}>

      {/* HEADER */}

      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
        }}
      >
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

      {user && (
        <p style={{ color: "#aaa" }}>
          Logged in as: {user.email}
        </p>
      )}


      {/* ADD FORM */}

      <div
        style={{
          marginTop: 25,
          display: "flex",
          gap: 10,
          flexWrap: "wrap",
        }}
      >

        <input
          style={inputStyle}
          placeholder="Amount"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
        />

        <input
          style={inputStyle}
          placeholder="Category"
          value={category}
          onChange={(e) => setCategory(e.target.value)}
        />

        <input
          style={inputStyle}
          type="date"
          value={date}
          onChange={(e) => setDate(e.target.value)}
        />

        <input
          style={inputStyle}
          placeholder="Description"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />

      </div>


      {/* EXTRA DATA */}

      <div style={{ marginTop: 15 }}>

        <h4>Extra Data</h4>

        {extras.map((ex, i) => (

          <div key={i} style={{ display: "flex", gap: 8 }}>

            <input
              style={inputStyle}
              placeholder="Key"
              value={ex.key}
              onChange={(e) =>
                updateExtra(i, "key", e.target.value)
              }
            />

            <input
              style={inputStyle}
              placeholder="Value"
              value={ex.value}
              onChange={(e) =>
                updateExtra(i, "value", e.target.value)
              }
            />

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


      {/* FILTER BAR (A1 + A2) */}

      <div
        style={{
          marginTop: 40,
          padding: 15,
          border: "1px solid #333",
          background: "#0f0f0f",
          display: "flex",
          gap: 15,
          flexWrap: "wrap",
          alignItems: "center",
        }}
      >

        {/* Category */}

        <select
          value={filterCategory}
          onChange={(e) => setFilterCategory(e.target.value)}
          style={{
            background: "white",
            color: "black",
            padding: "6px",
          }}
        >
          <option value="">Select</option>
          <option value="all">All</option>

          {categories.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}

        </select>


        {/* Sort */}

        <select
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value)}
          style={{
            background: "white",
            color: "black",
            padding: "6px",
          }}
        >
          <option value="expense_date">Date</option>
          <option value="amount">Amount</option>
          <option value="category">Category</option>
        </select>


        {/* Order */}

        <select
          value={order}
          onChange={(e) => setOrder(e.target.value)}
          style={{
            background: "white",
            color: "black",
            padding: "6px",
          }}
        >
          <option value="desc">Desc</option>
          <option value="asc">Asc</option>
        </select>


        {/* Dates */}

        <input
          type="date"
          value={fromDate}
          onChange={(e) => setFromDate(e.target.value)}
          style={inputStyle}
        />

        <input
          type="date"
          value={toDate}
          onChange={(e) => setToDate(e.target.value)}
          style={inputStyle}
        />


        {/* Buttons */}

        <button onClick={applyFilters}>
          Apply
        </button>

        <button onClick={resetFilters}>
          Reset
        </button>

      </div>


      {/* EXPENSE LIST */}

      {expenses.length > 0 && (

        <div style={{ marginTop: 30 }}>

          <h3>Expenses</h3>

          <table
            style={{
              width: "100%",
              borderCollapse: "collapse",
            }}
          >

            <thead>
              <tr>
                <th style={thStyle}>Amount</th>
                <th style={thStyle}>Date</th>
                <th style={thStyle}>Category</th>
                <th style={thStyle}>Description</th>
              </tr>
            </thead>

            <tbody>

              {expenses.map((e) => (

                <tr key={e.id}>

                  <td style={tdStyle}>{e.amount}</td>
                  <td style={tdStyle}>{e.expense_date}</td>
                  <td style={tdStyle}>{e.category}</td>
                  <td style={tdStyle}>{e.description || "-"}</td>

                </tr>

              ))}

            </tbody>

          </table>

        </div>

      )}


      {/* LATEST */}

      {latest && (

        <div style={{ marginTop: 40 }}>

          <h3>Latest Expense</h3>

          <table
            style={{
              width: "100%",
              borderCollapse: "collapse",
            }}
          >

            <thead>
              <tr>
                <th style={thStyle}>Amount</th>
                <th style={thStyle}>Date</th>
                <th style={thStyle}>Category</th>
                <th style={thStyle}>Description</th>
                <th style={thStyle}>Extra</th>
              </tr>
            </thead>

            <tbody>
              <tr>

                <td style={tdStyle}>{latest.amount}</td>
                <td style={tdStyle}>{latest.expense_date}</td>
                <td style={tdStyle}>{latest.category}</td>
                <td style={tdStyle}>{latest.description || "-"}</td>

                <td style={tdStyle}>
                  <pre style={{ margin: 0 }}>
                    {JSON.stringify(latest.extra_data, null, 2)}
                  </pre>
                </td>

              </tr>
            </tbody>

          </table>

        </div>

      )}

    </div>
  );
}
