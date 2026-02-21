"use client";

import { useState } from "react";
import { loginUser, registerUser } from "../../lib/backend";

export default function AuthPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [msg, setMsg] = useState("");

  async function register() {
    try {
      await registerUser({ email, password });
      setMsg("Registered successfully ✅");
    } catch (e: any) {
      setMsg("Register error: " + e.message);
    }
  }

  async function login() {
    try {
      const data = await loginUser({ email, password });
      localStorage.setItem("token", data.access_token);
      setMsg("Logged in ✅ Token saved");
    } catch (e: any) {
      setMsg("Login error: " + e.message);
    }
  }

  return (
    <div style={{ padding: 40, maxWidth: 400 }}>
      <h2>Auth</h2>

      <input
        placeholder="Email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        style={{ width: "100%", marginBottom: 10 }}
      />

      <input
        type="password"
        placeholder="Password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        style={{ width: "100%", marginBottom: 10 }}
      />

      <div style={{ display: "flex", gap: 10 }}>
        <button onClick={register}>Register</button>
        <button onClick={login}>Login</button>
      </div>

      <p>{msg}</p>
    </div>
  );
}

