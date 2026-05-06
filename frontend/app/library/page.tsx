"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { API_BASE_URL, AUTH_TOKEN, api } from "@/lib/api";
import type { Source } from "@/lib/types";


const STATUS_COLOR: Record<string, string> = {
  ready: "bg-green-100 text-green-800",
  failed: "bg-red-100 text-red-800",
  uploaded: "bg-neutral-100 text-neutral-700",
  extracting: "bg-amber-100 text-amber-800",
  chunking: "bg-amber-100 text-amber-800",
  embedding: "bg-amber-100 text-amber-800",
};

export default function LibraryPage() {
  const [sources, setSources] = useState<Source[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [filter, setFilter] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    try {
      const rows = await api<Source[]>("/api/v1/sources");
      setSources(rows);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 4000);
    return () => clearInterval(t);
  }, [load]);

  const onUpload = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (!file) return;
      setUploading(true);
      setError(null);
      try {
        const fd = new FormData();
        fd.append("file", file);
        const headers: Record<string, string> = {};
        if (AUTH_TOKEN) headers["X-Auth-Token"] = AUTH_TOKEN;
        const res = await fetch(`${API_BASE_URL}/api/v1/sources`, {
          method: "POST",
          headers,
          body: fd,
        });
        if (!res.ok) throw new Error(`upload failed: ${res.status} ${await res.text()}`);
        if (fileRef.current) fileRef.current.value = "";
        await load();
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        setUploading(false);
      }
    },
    [load],
  );

  const onDelete = useCallback(
    async (id: number) => {
      if (!confirm("Delete this source? This removes its chunks and embeddings.")) return;
      try {
        await api<void>(`/api/v1/sources/${id}`, { method: "DELETE" });
        await load();
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      }
    },
    [load],
  );

  const filtered = (sources ?? []).filter((s) => {
    const q = filter.toLowerCase();
    if (!q) return true;
    return (
      s.title.toLowerCase().includes(q) ||
      s.authors.some((a) => a.toLowerCase().includes(q)) ||
      s.source_format.toLowerCase().includes(q)
    );
  });

  return (
    <div className="mx-auto max-w-6xl p-6">
      <header className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Library</h1>
        <div className="flex items-center gap-3">
          <Link
            href="/library/quotes"
            className="rounded border border-neutral-300 px-3 py-1.5 text-sm hover:bg-neutral-100 dark:border-neutral-700 dark:hover:bg-neutral-800"
          >
            Quote shelf
          </Link>
          <input
            type="text"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Filter..."
            className="rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-900"
          />
          <label className="cursor-pointer rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700">
            {uploading ? "Uploading..." : "Upload"}
            <input
              ref={fileRef}
              type="file"
              accept=".pdf,.docx,.epub,.html,.htm,.md,.markdown,.txt"
              onChange={onUpload}
              disabled={uploading}
              className="hidden"
            />
          </label>
        </div>
      </header>

      {error && (
        <div className="mb-4 rounded border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </div>
      )}

      {!sources && <div className="text-sm text-neutral-500">Loading...</div>}

      {sources && filtered.length === 0 && (
        <div className="rounded border border-dashed border-neutral-300 p-10 text-center text-sm text-neutral-500 dark:border-neutral-700">
          No sources yet. Upload a PDF, DOCX, EPUB, HTML, or Markdown file to get started.
        </div>
      )}

      {sources && filtered.length > 0 && (
        <table className="w-full border-collapse text-sm">
          <thead className="border-b border-neutral-200 text-left text-xs uppercase text-neutral-500 dark:border-neutral-800">
            <tr>
              <th className="py-2 pr-4">Title</th>
              <th className="py-2 pr-4">Authors</th>
              <th className="py-2 pr-4">Format</th>
              <th className="py-2 pr-4">Pages</th>
              <th className="py-2 pr-4">Status</th>
              <th className="py-2"></th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((s) => (
              <tr
                key={s.id}
                className="border-b border-neutral-100 align-top dark:border-neutral-800"
              >
                <td className="py-2 pr-4">
                  <Link href={`/library/${s.id}`} className="font-medium hover:underline">
                    {s.title}
                  </Link>
                  {s.year && <span className="ml-1 text-xs text-neutral-500">({s.year})</span>}
                </td>
                <td className="py-2 pr-4 text-neutral-700 dark:text-neutral-300">
                  {s.authors.join(", ") || "—"}
                </td>
                <td className="py-2 pr-4 uppercase text-neutral-500">{s.source_format}</td>
                <td className="py-2 pr-4 text-neutral-500">{s.page_count ?? "—"}</td>
                <td className="py-2 pr-4">
                  <span
                    className={`rounded px-1.5 py-0.5 text-xs ${STATUS_COLOR[s.status] ?? "bg-neutral-100 text-neutral-700"}`}
                  >
                    {s.status}
                  </span>
                  {s.ingestion_error && (
                    <div className="mt-1 max-w-xs truncate text-xs text-red-600" title={s.ingestion_error}>
                      {s.ingestion_error}
                    </div>
                  )}
                </td>
                <td className="py-2 text-right">
                  <button
                    onClick={() => onDelete(s.id)}
                    className="text-xs text-red-600 hover:underline"
                  >
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
