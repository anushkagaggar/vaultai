"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "../lib/backend";

export default function Home() {
  const [status, setStatus] = useState<string>("Loading...");

  useEffect(() => {
    async function load() {
      try {
        const data = await apiFetch("/health");
        setStatus(data.status);
      } catch (err: any) {
        setStatus("ERROR: " + err.message);
      }
    }

    load();
  }, []);

  return (
    <div style={{ padding: 40 }}>
      <h1>VaultAI Frontend</h1>
      <p>Backend Status: {status}</p>
    </div>
  );
}

