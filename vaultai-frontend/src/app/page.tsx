"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

export default function Home() {
  const [status, setStatus] = useState("Loading...");

  useEffect(() => {
    apiFetch("/health")
      .then((res) => setStatus(res.status))
      .catch(() => setStatus("Backend not reachable"));
  }, []);

  return (
    <main className="p-10">
      <h1 className="text-2xl font-bold">VaultAI</h1>
      <p className="mt-4">Backend status: {status}</p>
    </main>
  );
}
