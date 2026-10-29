import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = { title: { default: "Lozhka", template: "%s · Lozhka" }, description: "Eastern European food, delivered in Amsterdam and Utrecht." };

export default function Root({ children }: { children: React.ReactNode }) {
  return (
    <html lang="nl">
      <body>{children}</body>
    </html>
  );
}
