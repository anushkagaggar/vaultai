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
  const [filterCategory, setFilterCategory] = useState("");

  // ---------------- TABLE STYLES ----------------

  const thStyle = {
    border: "1px solid #555",
    padding: "10px",
    textAlign: "left" as const,
    background: "#222",
  };

  const tdStyle = {
    border: "1px solid #555",
    padding: "10px",
    background: "#111",
  };

  // ---------------- EXTRA DATA ----------------

  function addExtra() {
    setExtras([...extras, { key: "", value: "" }]);
  }

  function updateExtra(
    index: number,
    field: "key" | "value",
    val: string
  ) {
    const copy = [...extras];
    copy[index][field] = val;
    setExtras(copy);
  }

  function removeExtra(index: number) {
    const copy = [...extras];
    copy.splice(index, 1);
    setExtras(copy);
  }

  // ---------------- LOGOUT ----------------

  function logout() {
    localStorage.removeItem("token");
    window.location.href = "/auth";
  }

  // ---------------- LOAD EXPENSES ----------------

  async function loadExpenses(category?: string) {
    try {
      const data = await getExpenses({
        category: category || undefined,
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

      // Reload if filter active
      if (filterCategory) {
        loadExpenses(filterCategory === "all" ? undefined : filterCategory);
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

    // Load once for categories only
    loadExpenses();

  }, []);

  // ---------------- FILTER CHANGE ----------------

  useEffect(() => {

    if (!filterCategory) {
      setExpenses([]);
      return;
    }

    if (filterCategory === "all") {
      loadExpenses();
    } else {
      loadExpenses(filterCategory);
    }

  }, [filterCategory]);

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
      <div style={{ marginTop: 25, display: "flex", gap: 10, flexWrap: "wrap" }}>

        <input
          placeholder="Amount"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
        />

        <input
          placeholder="Category"
          value={category}
          onChange={(e) => setCategory(e.target.value)}
        />

        <input
          type="date"
          value={date}
          onChange={(e) => setDate(e.target.value)}
        />

        <input
          placeholder="Description"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />

      </div>

      {/* EXTRA */}
      <div style={{ marginTop: 15 }}>

        <h4>Extra Data</h4>

        {extras.map((ex, i) => (
          <div key={i} style={{ display: "flex", gap: 8 }}>

            <input
              placeholder="Key"
              value={ex.key}
              onChange={(e) =>
                updateExtra(i, "key", e.target.value)
              }
            />

            <input
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


      {/* FILTER */}
      <div style={{ marginTop: 30 }}>

        <label style={{ marginRight: 10 }}>
          Filter:
        </label>

        <select
          value={filterCategory}
          onChange={(e) => setFilterCategory(e.target.value)}
          style={{
            background: "white",
            color: "black",
            padding: "6px",
            borderRadius: "4px",
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
                <th style={thStyle}>Extra Data</th>
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
