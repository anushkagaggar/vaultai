"use client";

import { useEffect, useState } from "react";
import {
  createExpense,
  getMe,
  getExpenses,
} from "@/lib/api";

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
  const [filterCategory, setFilterCategory] = useState("all");

  // ---------------- TABLE STYLES ----------------

  const thStyle = {
    border: "1px solid #555",
    padding: "10px",
    textAlign: "left" as const,
  };

  const tdStyle = {
    border: "1px solid #555",
    padding: "10px",
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

  async function loadExpenses() {
    try {
      const data = await getExpenses({
        category:
          filterCategory === "all"
            ? undefined
            : filterCategory,
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

      loadExpenses();

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

    loadExpenses();

  }, []);

  // Reload on filter change
  useEffect(() => {
    loadExpenses();
  }, [filterCategory]);

  // ---------------- UNIQUE CATEGORIES ----------------

  const categories = Array.from(
    new Set(expenses.map((e) => e.category))
  );

  // ---------------- UI ----------------

  return (
    <div style={{ padding: 40 }}>

      {/* HEADER */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
        }}
      >
        <h2>Dashboard</h2>
        <button onClick={logout}>Logout</button>
      </div>

      {/* USER */}
      {user && (
        <p style={{ color: "gray" }}>
          {user.email}
        </p>
      )}

      {/* ADD FORM */}
      <div style={{ marginTop: 25 }}>

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

        {/* EXTRA */}
        <div style={{ marginTop: 10 }}>

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
          style={{ marginTop: 15 }}
          onClick={add}
        >
          Add Expense
        </button>

      </div>


      {/* FILTER (A1 FIXED) */}
      <div style={{ marginTop: 30 }}>

        <label>Filter by Category: </label>

              <select
                  value={filterCategory}
                  onChange={(e) => setFilterCategory(e.target.value)}
                  style={{
                      backgroundColor: "white",
                      color: "black",
                      padding: "6px",
                      borderRadius: "4px",
                      border: "1px solid #ccc",
                  }}
              >
                  <option value="all" style={{ color: "black" }}>
                      All
                  </option>

                  {categories.map((c) => (
                      <option key={c} value={c} style={{ color: "black" }}>
                          {c}
                      </option>
                  ))}
        </select>

      </div>


      {/* EXPENSE LIST */}
      <div style={{ marginTop: 30 }}>

        <h3>Expenses</h3>

        <table
          style={{
            width: "100%",
            borderCollapse: "collapse",
          }}
        >

          <thead>
            <tr style={{ background: "#222" }}>
              <th style={thStyle}>Amount</th>
              <th style={thStyle}>Date</th>
              <th style={thStyle}>Category</th>
              <th style={thStyle}>Description</th>
            </tr>
          </thead>

          <tbody>

            {expenses.map((e) => (

              <tr key={e.id} style={{ background: "#111" }}>

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


      {/* LATEST */}
      {latest && (

        <div style={{ marginTop: 40 }}>

          <h3>Latest Expense</h3>

          <pre>
            {JSON.stringify(latest, null, 2)}
          </pre>

        </div>
      )}

    </div>
  );
}
