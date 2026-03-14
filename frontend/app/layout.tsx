import "./globals.css";
import type { Metadata } from "next";
import type { ReactNode } from "react";
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
      </body>
    </html>
  );
}
