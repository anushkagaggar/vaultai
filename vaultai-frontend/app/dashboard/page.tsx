"use client";

import { useEffect, useState } from "react";
import { getExpenses, createExpense, getMe } from "@/lib/api";

export default function Dashboard() {
  const [expenses, setExpenses] = useState<any[]>([]);
  const [amount, setAmount] = useState("");
  const [category, setCategory] = useState("");
  const [user, setUser] = useState<any>(null);

  // ---------- LOGOUT ----------
  function logout() {
    localStorage.removeItem("token");
    window.location.href = "/login";
  }

  // ---------- LOAD DATA ----------
  async function load() {
    try {
      // Who am I
      const me = await getMe();
      setUser(me);

      // Expenses
      const data = await getExpenses();
      setExpenses(data);

    } catch (err) {
      console.error(err);
      logout(); // fallback safety
    }
  }

  // ---------- ADD EXPENSE ----------
  async function add() {
    if (!amount || !category) {
      alert("Fill all fields");
      return;
    }

    await createExpense({
      amount: Number(amount),
      category,
    });

    setAmount("");
    setCategory("");

    load();
  }

  // ---------- ROUTE GUARD ----------
  useEffect(() => {
    const token = localStorage.getItem("token");

    if (!token) {
      window.location.href = "/login";
      return;
    }

    load();
  }, []);

  return (
    <div style={{ padding: 40 }}>

      {/* HEADER */}
      <div style={{ display: "flex", justifyContent: "space-between" }}>
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
      <div style={{ marginTop: 20 }}>
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

        <button onClick={add}>Add</button>
      </div>

      {/* LIST */}
      <h3 style={{ marginTop: 30 }}>Expenses</h3>

      <ul>
        {expenses.map((e) => (
          <li key={e.id}>
            {e.amount} — {e.category}
          </li>
        ))}
      </ul>

    </div>
  );
}
