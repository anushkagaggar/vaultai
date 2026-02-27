import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "VaultAI — Your Personal Expense Tracker",
  description: "AI-powered expense tracking and financial insights",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}