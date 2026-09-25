import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "deskcall — Laporan Panggilan",
  description: "Hasil panggilan AI agent penagihan deskcall",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="id">
      <body>
        <header className="topbar">
          <Link href="/" className="brand">
            <span className="brand-mark" aria-hidden>●</span> deskcall
          </Link>
          <span className="topbar-note">Laporan panggilan AI agent · demo</span>
        </header>
        <main className="container">{children}</main>
      </body>
    </html>
  );
}
