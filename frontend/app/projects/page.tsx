"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { api } from "@/lib/api";
import type { Project } from "@/lib/types";

export default function ProjectsPage() {
  const router = useRouter();
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [creating, setCreating] = useState(false);

  const load = useCallback(async () => {
    try {
      const rows = await api<Project[]>("/api/v1/projects");
      setProjects(rows);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const onCreate = useCallback(async () => {
    const t = title.trim();
    if (!t || creating) return;
    setCreating(true);
    try {
      const p = await api<Project>("/api/v1/projects", {
        method: "POST",
        body: JSON.stringify({ title: t }),
      });
      router.push(`/projects/${p.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setCreating(false);
    }
  }, [title, creating, router]);

  const onDelete = useCallback(
    async (id: number) => {
      if (!confirm("Delete project and all of its outline + evidence?")) return;
      try {
        await api<void>(`/api/v1/projects/${id}`, { method: "DELETE" });
        await load();
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      }
    },
    [load],
  );

  return (
    <div className="mx-auto max-w-4xl p-6">
      <h1 className="mb-4 text-2xl font-semibold">Projects</h1>
      {error && (
        <div className="mb-3 rounded border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="mb-6 flex items-center gap-2">
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && onCreate()}
          placeholder="New project title..."
          className="flex-1 rounded border border-neutral-300 px-3 py-1.5 text-sm dark:border-neutral-700 dark:bg-neutral-900"
        />
        <button
          onClick={onCreate}
          disabled={!title.trim() || creating}
          className="rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
        >
          Create
        </button>
      </div>

      {!projects && <div className="text-sm text-neutral-500">Loading...</div>}
      {projects && projects.length === 0 && (
        <div className="rounded border border-dashed border-neutral-300 p-8 text-center text-sm text-neutral-500 dark:border-neutral-700">
          No projects yet.
        </div>
      )}
      {projects && (
        <ul className="space-y-2">
          {projects.map((p) => (
            <li
              key={p.id}
              className="flex items-center justify-between rounded border border-neutral-200 p-3 dark:border-neutral-800"
            >
              <Link href={`/projects/${p.id}`} className="font-medium hover:underline">
                {p.title}
              </Link>
              <button
                onClick={() => onDelete(p.id)}
                className="text-xs text-red-600 hover:underline"
              >
                Delete
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
