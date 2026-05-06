import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Research-o-Writer",
  description: "Source-grounded research and writing workspace",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
