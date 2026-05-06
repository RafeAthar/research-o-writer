"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { api } from "@/lib/api";
import type { Quote } from "@/lib/types";

export default function QuoteShelfPage() {
  const [quotes, setQuotes] = useState<Quote[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState("");

  const load = useCallback(async () => {
    try {
      const rows = await api<Quote[]>("/api/v1/quotes");
      setQuotes(rows);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const onDelete = useCallback(
    async (id: number) => {
      if (!confirm("Delete this quote?")) return;
      try {
        await api<void>(`/api/v1/quotes/${id}`, { method: "DELETE" });
        setQuotes((rows) => (rows ?? []).filter((r) => r.id !== id));
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      }
    },
    [],
  );

  const filtered = (quotes ?? []).filter((q) => {
    if (!filter) return true;
    const f = filter.toLowerCase();
    return (
      q.text.toLowerCase().includes(f) ||
      ((q.citation.source_title as string) ?? "").toLowerCase().includes(f) ||
      (q.note ?? "").toLowerCase().includes(f)
    );
  });

  return (
    <div className="mx-auto max-w-4xl p-6">
      <header className="mb-4 flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Quote shelf</h1>
        <input
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Filter..."
          className="rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-900"
        />
      </header>

      {error && (
        <div className="mb-3 rounded border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </div>
      )}

      {!quotes && <div className="text-sm text-neutral-500">Loading...</div>}
      {quotes && filtered.length === 0 && (
        <div className="rounded border border-dashed border-neutral-300 p-8 text-center text-sm text-neutral-500 dark:border-neutral-700">
          No saved quotes yet. Open a source and use "+ Shelf" to save selections.
        </div>
      )}

      <ul className="space-y-3">
        {filtered.map((q) => {
          const c = q.citation || {};
          const chap = Array.isArray(c.chapter_path)
            ? (c.chapter_path as string[]).join(" > ")
            : "";
          const page =
            c.page_start && c.page_end && c.page_end !== c.page_start
              ? `pp. ${c.page_start}-${c.page_end}`
              : c.page_start
                ? `p. ${c.page_start}`
                : "";
          return (
            <li
              key={q.id}
              className="rounded border border-neutral-200 bg-white p-4 dark:border-neutral-800 dark:bg-neutral-950"
            >
              <blockquote className="border-l-2 border-neutral-300 pl-3 text-sm italic text-neutral-700 dark:text-neutral-300">
                {q.text}
              </blockquote>
              {q.note && (
                <div className="mt-2 text-xs text-neutral-500">Note: {q.note}</div>
              )}
              <div className="mt-2 flex items-center justify-between text-xs">
                <Link
                  href={`/library/${q.source_id}${q.chunk_id ? `?chunk=${q.chunk_id}` : ""}${
                    c.page_start ? `&page=${c.page_start}` : ""
                  }`}
                  className="text-blue-600 hover:underline"
                >
                  {(c.source_title as string) || `Source #${q.source_id}`}
                  {chap ? ` · ${chap}` : ""}
                  {page ? ` · ${page}` : ""}
                </Link>
                <button
                  onClick={() => onDelete(q.id)}
                  className="text-red-600 hover:underline"
                >
                  delete
                </button>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
