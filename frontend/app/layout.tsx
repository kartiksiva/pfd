import "./globals.css";
import type { Metadata } from "next";
import type { ReactNode } from "react";
import Link from "next/link";
import AccessGate from "./AccessGate";

export const metadata: Metadata = {
  title: "PFCD MVP",
  description: "Process Documentation Agent MVP"
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <AccessGate>{children}</AccessGate>
        <footer className="siteFooter">
          <div className="siteFooterInner">
            <span className="muted">PFCD MVP</span>
            <Link href="/privacy">Privacy Policy</Link>
          </div>
        </footer>
      </body>
    </html>
  );
}
