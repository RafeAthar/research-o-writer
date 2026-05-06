import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Research-o-Writer",
  description: "Source-grounded research and writing workspace",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="flex min-h-screen flex-col">
          <header className="border-b border-neutral-200 bg-white dark:border-neutral-800 dark:bg-neutral-900">
            <nav className="mx-auto flex max-w-6xl items-center gap-6 px-6 py-3 text-sm">
              <Link href="/" className="font-semibold tracking-tight">
                Research-o-Writer
              </Link>
              <Link href="/library" className="text-neutral-700 hover:underline dark:text-neutral-300">
                Library
              </Link>
              <Link href="/chat" className="text-neutral-700 hover:underline dark:text-neutral-300">
                Chat
              </Link>
              <Link href="/projects" className="text-neutral-700 hover:underline dark:text-neutral-300">
                Projects
              </Link>
            </nav>
          </header>
          <main className="flex-1">{children}</main>
        </div>
      </body>
    </html>
  );
}
