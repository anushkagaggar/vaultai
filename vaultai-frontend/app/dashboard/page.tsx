"use client";

import { useEffect, useState } from "react";
import { getExpenses, createExpense } from "@/lib/api";

export default function Dashboard() {
  const [expenses, setExpenses] = useState<any[]>([]);
  const [amount, setAmount] = useState("");
  const [category, setCategory] = useState("");

  async function load() {
    try {
      const data = await getExpenses();
      setExpenses(data);
    } catch {
      alert("Not logged in");
    }
  }

  async function add() {
    await createExpense({
      amount: Number(amount),
      category,
    });

    setAmount("");
    setCategory("");
    load();
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <div style={{ padding: 40 }}>
      <h2>Dashboard</h2>

      <div>
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

      <h3>Expenses</h3>

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
