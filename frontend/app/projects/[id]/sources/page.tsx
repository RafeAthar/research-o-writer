"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { api } from "@/lib/api";
import type { Project, Source } from "@/lib/types";

export default function ProjectSourcesPage({ params }: { params: { id: string } }) {
  const projectId = Number(params.id);
  const [project, setProject] = useState<Project | null>(null);
  const [shelf, setShelf] = useState<Source[]>([]);
  const [library, setLibrary] = useState<Source[]>([]);
  const [filter, setFilter] = useState("");
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    try {
      const [p, sh, lib] = await Promise.all([
        api<Project>(`/api/v1/projects/${projectId}`),
        api<Source[]>(`/api/v1/projects/${projectId}/sources`),
        api<Source[]>(`/api/v1/sources`),
      ]);
      setProject(p);
      setShelf(sh);
      setLibrary(lib);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [projectId]);

  useEffect(() => {
    reload();
  }, [reload]);

  const shelfIds = useMemo(() => new Set(shelf.map((s) => s.id)), [shelf]);
  const available = useMemo(() => {
    const q = filter.trim().toLowerCase();
    return library
      .filter((s) => !shelfIds.has(s.id))
      .filter((s) => !q || s.title.toLowerCase().includes(q));
  }, [library, shelfIds, filter]);

  const attach = useCallback(
    async (sourceId: number) => {
      setError(null);
      try {
        const updated = await api<Source[]>(`/api/v1/projects/${projectId}/sources`, {
          method: "POST",
          body: JSON.stringify({ source_ids: [sourceId] }),
        });
        setShelf(updated);
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      }
    },
    [projectId],
  );

  const detach = useCallback(
    async (sourceId: number) => {
      setError(null);
      try {
        await api<void>(`/api/v1/projects/${projectId}/sources/${sourceId}`, {
          method: "DELETE",
        });
        setShelf((rows) => rows.filter((s) => s.id !== sourceId));
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      }
    },
    [projectId],
  );

  if (!project) return <div className="p-6 text-sm text-neutral-500">Loading…</div>;

  return (
    <div className="mx-auto max-w-3xl p-6">
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-xl font-semibold">{project.title} — sources</h1>
        <Link
          href={`/projects/${projectId}`}
          className="text-sm text-blue-600 hover:underline"
        >
          ← back to project
        </Link>
      </div>
      <p className="mb-4 text-sm text-neutral-600 dark:text-neutral-400">
        Pick which library sources this project draws on. Project-scoped chat and
        search retrieve <strong>only</strong> from the sources on this shelf. With
        an empty shelf, a project-scoped chat finds no passages. Removing a source
        here leaves it untouched in your library.
      </p>
      {error && (
        <div className="mb-3 rounded border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </div>
      )}

      <h2 className="mb-2 mt-6 text-sm font-semibold uppercase tracking-wide text-neutral-500">
        On this project ({shelf.length})
      </h2>
      {shelf.length === 0 && (
        <div className="mb-2 text-sm text-neutral-500">No sources yet — add some below.</div>
      )}
      <ul className="space-y-1">
        {shelf.map((s) => (
          <li
            key={s.id}
            className="flex items-center justify-between rounded border border-neutral-200 px-3 py-1.5 text-sm dark:border-neutral-800"
          >
            <span className="truncate" title={s.title}>
              {s.title}
              {s.authors.length > 0 && (
                <span className="text-neutral-500"> — {s.authors.join(", ")}</span>
              )}
            </span>
            <button
              onClick={() => detach(s.id)}
              className="ml-2 shrink-0 rounded border border-neutral-300 px-2 py-0.5 text-xs hover:bg-neutral-100 dark:border-neutral-700 dark:hover:bg-neutral-800"
              title="Remove from this project"
            >
              Remove
            </button>
          </li>
        ))}
      </ul>

      <h2 className="mb-2 mt-8 text-sm font-semibold uppercase tracking-wide text-neutral-500">
        Add from library
      </h2>
      <input
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
        placeholder="Filter library…"
        className="mb-2 w-full rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-900"
      />
      {available.length === 0 && (
        <div className="text-sm text-neutral-500">
          {library.length === shelf.length
            ? "Everything in your library is already on this project."
            : "No matching sources."}
        </div>
      )}
      <ul className="space-y-1">
        {available.map((s) => (
          <li
            key={s.id}
            className="flex items-center justify-between rounded border border-neutral-200 px-3 py-1.5 text-sm dark:border-neutral-800"
          >
            <span className="truncate" title={s.title}>
              {s.title}
              {s.authors.length > 0 && (
                <span className="text-neutral-500"> — {s.authors.join(", ")}</span>
              )}
            </span>
            <button
              onClick={() => attach(s.id)}
              className="ml-2 shrink-0 rounded bg-blue-600 px-2 py-0.5 text-xs font-medium text-white hover:bg-blue-700"
              title="Add to this project"
            >
              Add
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
