"use client";

import { useEffect, useState } from "react";
import { createExpense, getMe } from "@/lib/api";

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

  // ---------------- TABLE STYLES ----------------

  const thStyle = {
    border: "1px solid #666",
    padding: "10px",
    textAlign: "left" as const,
  };

  const tdStyle = {
    border: "1px solid #666",
    padding: "10px",
    verticalAlign: "top" as const,
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

  // ---------------- ADD EXPENSE ----------------

  async function add() {
    try {
      if (!amount || !category || !date) {
        alert("Fill all required fields");
        return;
      }

      // Convert extras → object
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

      // Show latest only
      setLatest(newExpense);

      // Reset form
      setAmount("");
      setCategory("");
      setDate("");
      setDescription("");
      setExtras([]);

    } catch (err: any) {
      alert(err.message || "Failed to add expense");
    }
  }

  // ---------------- AUTH CHECK ----------------

  useEffect(() => {
    const token = localStorage.getItem("token");

    if (!token) {
      window.location.href = "/auth";
      return;
    }

    // Verify token
    getMe()
      .then(setUser)
      .catch(() => {
        localStorage.removeItem("token");
        window.location.href = "/auth";
      });

  }, []);

  // ---------------- UI ----------------

  return (
    <div style={{ padding: 40 }}>

      {/* HEADER */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <h2>Dashboard</h2>
        <button onClick={logout}>Logout</button>
      </div>

      {/* USER INFO */}
      {user && (
        <p style={{ color: "gray" }}>
          Logged in as: {user.email}
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

        {/* EXTRA DATA */}
        <div style={{ marginTop: 15 }}>

          <h4>Extra Data</h4>

          {extras.map((ex, i) => (
            <div
              key={i}
              style={{ display: "flex", gap: 8, marginBottom: 6 }}
            >
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

      {/* LATEST EXPENSE */}
      {latest && (

        <div style={{ marginTop: 40 }}>

          <h3>Latest Expense</h3>

          <table
            style={{
              width: "100%",
              marginTop: 15,
              borderCollapse: "collapse",
              border: "1px solid #666",
              color: "white",
            }}
          >
            <thead>
              <tr style={{ backgroundColor: "#222" }}>
                <th style={thStyle}>Amount</th>
                <th style={thStyle}>Date</th>
                <th style={thStyle}>Category</th>
                <th style={thStyle}>Description</th>
                <th style={thStyle}>Extra Data</th>
              </tr>
            </thead>

            <tbody>
              <tr style={{ backgroundColor: "#111" }}>
                <td style={tdStyle}>{latest.amount}</td>
                <td style={tdStyle}>{latest.expense_date}</td>
                <td style={tdStyle}>{latest.category}</td>
                <td style={tdStyle}>{latest.description || "-"}</td>

                <td style={tdStyle}>
                  <pre style={{ margin: 0, whiteSpace: "pre-wrap" }}>
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
