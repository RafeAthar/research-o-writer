"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { api } from "@/lib/api";
import type { Chat, Source } from "@/lib/types";

export default function ChatListPage() {
  const router = useRouter();
  const [chats, setChats] = useState<Chat[] | null>(null);
  const [sources, setSources] = useState<Source[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [scope, setScope] = useState<"library" | "sources">("library");
  const [pickedSourceIds, setPickedSourceIds] = useState<number[]>([]);

  const load = useCallback(async () => {
    try {
      const [c, s] = await Promise.all([
        api<Chat[]>("/api/v1/chats"),
        api<Source[]>("/api/v1/sources"),
      ]);
      setChats(c);
      setSources(s);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const onCreate = useCallback(async () => {
    if (creating) return;
    setCreating(true);
    try {
      const body = {
        title: scope === "sources" ? "Source chat" : "Library chat",
        scope,
        source_ids: scope === "sources" ? pickedSourceIds : [],
      };
      const chat = await api<Chat>("/api/v1/chats", {
        method: "POST",
        body: JSON.stringify(body),
      });
      router.push(`/chat/${chat.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setCreating(false);
    }
  }, [scope, pickedSourceIds, creating, router]);

  return (
    <div className="mx-auto grid max-w-5xl grid-cols-1 gap-6 p-6 md:grid-cols-[1fr_320px]">
      <div>
        <h1 className="mb-4 text-2xl font-semibold">Chats</h1>
        {error && (
          <div className="mb-3 rounded border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </div>
        )}
        {!chats && <div className="text-sm text-neutral-500">Loading...</div>}
        {chats && chats.length === 0 && (
          <div className="rounded border border-dashed border-neutral-300 p-8 text-center text-sm text-neutral-500 dark:border-neutral-700">
            No chats yet. Start one on the right.
          </div>
        )}
        {chats && chats.length > 0 && (
          <ul className="space-y-2">
            {chats.map((c) => (
              <li key={c.id}>
                <Link
                  href={`/chat/${c.id}`}
                  className="block rounded border border-neutral-200 p-3 hover:border-neutral-400 dark:border-neutral-800"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-medium">{c.title}</span>
                    <span className="text-xs uppercase text-neutral-500">{c.scope}</span>
                  </div>
                  {c.source_ids.length > 0 && (
                    <div className="mt-1 text-xs text-neutral-500">
                      {c.source_ids.length} source(s)
                    </div>
                  )}
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>

      <aside className="rounded border border-neutral-200 p-4 dark:border-neutral-800">
        <h2 className="mb-3 font-semibold">New chat</h2>
        <label className="mb-2 block text-xs uppercase text-neutral-500">Scope</label>
        <select
          value={scope}
          onChange={(e) => setScope(e.target.value as "library" | "sources")}
          className="mb-3 w-full rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-900"
        >
          <option value="library">Whole library</option>
          <option value="sources">Specific sources</option>
        </select>
        {scope === "sources" && (
          <div className="mb-3 max-h-48 overflow-y-auto rounded border border-neutral-200 p-2 text-sm dark:border-neutral-800">
            {sources.length === 0 && (
              <div className="text-xs text-neutral-500">No sources available.</div>
            )}
            {sources.map((s) => {
              const checked = pickedSourceIds.includes(s.id);
              return (
                <label key={s.id} className="flex items-center gap-2 py-0.5">
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={(e) => {
                      setPickedSourceIds((ids) =>
                        e.target.checked ? [...ids, s.id] : ids.filter((i) => i !== s.id),
                      );
                    }}
                  />
                  <span className="truncate">{s.title}</span>
                </label>
              );
            })}
          </div>
        )}
        <button
          onClick={onCreate}
          disabled={creating || (scope === "sources" && pickedSourceIds.length === 0)}
          className="w-full rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {creating ? "Creating..." : "Start chat"}
        </button>
      </aside>
    </div>
  );
}
