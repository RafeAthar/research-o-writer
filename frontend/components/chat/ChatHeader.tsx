"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import type { Chat, Source } from "@/lib/types";

interface Props {
  chat: Chat;
  k: number;
  onChange: (patch: Partial<Pick<Chat, "scope" | "source_ids">>) => void;
  onChangeK: (k: number) => void;
  onExport: () => void;
}

/** Header strip with title, live scope/sources/k controls, and export. */
export function ChatHeader({ chat, k, onChange, onChangeK, onExport }: Props) {
  const [sources, setSources] = useState<Source[]>([]);
  const [picking, setPicking] = useState(false);
  const [projectSourceCount, setProjectSourceCount] = useState<number | null>(null);

  useEffect(() => {
    api<Source[]>("/api/v1/sources")
      .then(setSources)
      .catch(() => setSources([]));
  }, []);

  // The project shelf is managed on the project page; here we only reflect how
  // many sources are attached so the user knows what project-scoped chat sees.
  useEffect(() => {
    if (chat.scope !== "project" || chat.project_id == null) {
      setProjectSourceCount(null);
      return;
    }
    api<Source[]>(`/api/v1/projects/${chat.project_id}/sources`)
      .then((rows) => setProjectSourceCount(rows.length))
      .catch(() => setProjectSourceCount(null));
  }, [chat.scope, chat.project_id]);

  const scopeLabel =
    chat.scope === "library"
      ? "Whole library"
      : chat.scope === "project"
        ? "Project sources"
        : `${chat.source_ids.length} source(s)`;

  return (
    <div className="mb-2 flex flex-wrap items-center gap-2 border-b border-neutral-200 pb-2 dark:border-neutral-800">
      <Link
        href="/chat"
        className="text-xs text-neutral-500 hover:underline"
      >
        ← All chats
      </Link>
      <h1 className="mr-auto truncate text-sm font-semibold" title={chat.title}>
        {chat.title}
      </h1>
      <div className="flex items-center gap-1 text-xs">
        <select
          value={chat.scope}
          onChange={(e) =>
            onChange({
              scope: e.target.value as Chat["scope"],
              source_ids:
                e.target.value === "library" ? [] : chat.source_ids,
            })
          }
          className="rounded border border-neutral-300 bg-white px-1.5 py-1 dark:border-neutral-700 dark:bg-neutral-900"
          title="Retrieval scope"
        >
          <option value="library">Whole library</option>
          <option value="sources">Specific sources</option>
          <option value="project">Project</option>
        </select>
        {chat.scope === "sources" && (
          <button
            onClick={() => setPicking((v) => !v)}
            className="rounded border border-neutral-300 bg-white px-2 py-1 dark:border-neutral-700 dark:bg-neutral-900"
            title="Pick sources"
          >
            {scopeLabel}
          </button>
        )}
        {chat.scope === "project" &&
          (chat.project_id != null ? (
            <Link
              href={`/projects/${chat.project_id}/sources`}
              className="rounded border border-neutral-300 bg-white px-2 py-1 dark:border-neutral-700 dark:bg-neutral-900"
              title="Manage this project's sources"
            >
              {projectSourceCount == null
                ? "Project sources"
                : `${projectSourceCount} project source(s)`}
            </Link>
          ) : (
            <span
              className="rounded border border-neutral-300 bg-white px-2 py-1 text-neutral-500 dark:border-neutral-700 dark:bg-neutral-900"
              title="This chat isn't linked to a project"
            >
              No project
            </span>
          ))}
        <label className="flex items-center gap-1" title="Passages retrieved per question">
          <span className="text-neutral-500">k</span>
          <input
            type="range"
            min={3}
            max={30}
            value={k}
            onChange={(e) => onChangeK(Number(e.target.value))}
            className="w-20"
          />
          <span className="w-5 text-right tabular-nums">{k}</span>
        </label>
        <button
          onClick={onExport}
          className="rounded border border-neutral-300 bg-white px-2 py-1 dark:border-neutral-700 dark:bg-neutral-900"
        >
          Export
        </button>
      </div>

      {picking && chat.scope === "sources" && (
        <div className="w-full">
          <div className="mt-1 max-h-44 overflow-y-auto rounded border border-neutral-200 p-2 text-xs dark:border-neutral-800">
            {sources.length === 0 && (
              <div className="text-neutral-500">No sources available.</div>
            )}
            {sources.map((s) => {
              const checked = chat.source_ids.includes(s.id);
              return (
                <label key={s.id} className="flex items-center gap-2 py-0.5">
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={(e) =>
                      onChange({
                        source_ids: e.target.checked
                          ? [...chat.source_ids, s.id]
                          : chat.source_ids.filter((i) => i !== s.id),
                      })
                    }
                  />
                  <span className="truncate">{s.title}</span>
                </label>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
