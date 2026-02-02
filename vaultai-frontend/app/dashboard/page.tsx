"use client";

import { useEffect, useState } from "react";
import { createExpense, getMe, getExpenses } from "@/lib/api";

export default function Dashboard() {

  // ---------------- STATE ----------------

  const [amount, setAmount] = useState("");
  const [category, setCategory] = useState("");
  const [date, setDate] = useState("");
  const [description, setDescription] = useState("");

  const [extras, setExtras] = useState<
    { key: string; value: string }[]
  >([]);

  const [latest, setLatest] = useState<any | null>(null);
  const [user, setUser] = useState<any | null>(null);

  const [expenses, setExpenses] = useState<any[]>([]);
  const [filterCategory, setFilterCategory] = useState("");

  // ---------------- STYLES ----------------

  const inputStyle = {
    background: "#111",
    color: "white",
    border: "1px solid #444",
    padding: "8px",
    borderRadius: "4px",
  };

  const buttonStyle = {
    background: "#2563eb",
    color: "white",
    border: "none",
    padding: "8px 14px",
    borderRadius: "4px",
    cursor: "pointer",
  };

  const thStyle = {
    border: "1px solid #444",
    padding: "10px",
    textAlign: "left" as const,
    background: "#222",
    color: "white",
  };

  const tdStyle = {
    border: "1px solid #444",
    padding: "10px",
    background: "#111",
    color: "white",
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

  async function loadExpenses(selected: string) {
    try {
      const data = await getExpenses({
        category: selected || undefined,
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

      if (filterCategory) {
        loadExpenses(filterCategory);
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

  // ---------------- UNIQUE CATEGORIES ----------------

  const categories = Array.from(
    new Set(expenses.map((e) => e.category))
  );

  // ---------------- FILTER HANDLER ----------------

  function handleFilterChange(value: string) {
    setFilterCategory(value);

    if (value === "") {
      setExpenses([]);
      return;
    }

    loadExpenses(value);
  }

  // ---------------- UI ----------------

  return (
    <div
      style={{
        padding: 40,
        background: "#000",
        minHeight: "100vh",
        color: "white",
      }}
    >

      {/* HEADER */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <h2>Dashboard</h2>

        <button style={buttonStyle} onClick={logout}>
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
          style={inputStyle}
        />

        <input
          placeholder="Category"
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          style={inputStyle}
        />

        <input
          type="date"
          value={date}
          onChange={(e) => setDate(e.target.value)}
          style={inputStyle}
        />

        <input
          placeholder="Description"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          style={inputStyle}
        />

      </div>


      {/* EXTRA */}
      <div style={{ marginTop: 15 }}>

        <h4>Extra Data</h4>

        {extras.map((ex, i) => (

          <div key={i} style={{ display: "flex", gap: 8, marginBottom: 6 }}>

            <input
              placeholder="Key"
              value={ex.key}
              onChange={(e) =>
                updateExtra(i, "key", e.target.value)
              }
              style={inputStyle}
            />

            <input
              placeholder="Value"
              value={ex.value}
              onChange={(e) =>
                updateExtra(i, "value", e.target.value)
              }
              style={inputStyle}
            />

            <button
              style={{
                background: "#dc2626",
                color: "white",
                border: "none",
                padding: "4px 8px",
              }}
              onClick={() => removeExtra(i)}
            >
              X
            </button>

          </div>

        ))}

        <button style={buttonStyle} onClick={addExtra}>
          +
        </button>

      </div>


      <button
        style={{ ...buttonStyle, marginTop: 15 }}
        onClick={add}
      >
        Add Expense
      </button>


      {/* FILTER */}
      <div style={{ marginTop: 35 }}>

        <label style={{ marginRight: 10 }}>
          Filter:
        </label>

        <select
          value={filterCategory}
          onChange={(e) => handleFilterChange(e.target.value)}
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

        <div style={{ marginTop: 35 }}>

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
                  <td style={tdStyle}>
                    {e.description || "-"}
                  </td>

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

          <pre
            style={{
              background: "#111",
              padding: 15,
              border: "1px solid #444",
            }}
          >
            {JSON.stringify(latest, null, 2)}
          </pre>

        </div>

      )}

    </div>
  );
}
