"use client";

import { useEffect, useState } from "react";
import { getExpenses, createExpense, getMe } from "@/lib/api";

export default function Dashboard() {
    const [expenses, setExpenses] = useState<any[]>([]);
    const [amount, setAmount] = useState("");
    const [category, setCategory] = useState("");
    const [user, setUser] = useState<any>(null);
    const [filter, setFilter] = useState("");
    const [sort, setSort] = useState("expense_date");
    const [order, setOrder] = useState("desc");
    const [date, setDate] = useState("");
    const [description, setDescription] = useState("");
    const [extras, setExtras] = useState<
        { key: string; value: string }[]
    >([]);

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




    // ---------- LOGOUT ----------
    function logout() {
        localStorage.removeItem("token");
        window.location.href = "/auth";
    }

    // ---------- LOAD DATA ----------
    async function load() {
        try {
            const data = await getExpenses({
                category: filter || undefined,
                sort,
                order,
            });

            setExpenses(data);
        } catch {
            alert("Session expired. Login again.");
        }
    }


    // ---------- ADD EXPENSE ----------
    async function add() {
        if (!amount || !category || !date) {
            alert("Fill required fields");
            return;
        }

        // Convert extras → dict
        const extraObj: Record<string, string> = {};

        extras.forEach((e) => {
            if (e.key && e.value) {
                extraObj[e.key] = e.value;
            }
        });

        await createExpense({
            amount: Number(amount),
            category,
            description,
            expense_date: date,
            extra_data: extraObj,
        });

        setAmount("");
        setCategory("");
        setDate("");
        setDescription("");
        setExtras([]);

        load();
    }


    // ---------- ROUTE GUARD ----------
    useEffect(() => {
        const token = localStorage.getItem("token");

        if (!token) {
            window.location.href = "/auth";
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

                <button style={{ marginTop: 10 }} onClick={add}>
                    Add
                </button>
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
