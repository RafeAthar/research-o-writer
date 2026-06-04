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

  const onRename = useCallback(async (chatId: number, title: string) => {
    try {
      await api(`/api/v1/chats/${chatId}`, {
        method: "PATCH",
        body: JSON.stringify({ title }),
      });
      setChats((prev) =>
        prev?.map((c) => (c.id === chatId ? { ...c, title } : c)) ?? prev,
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  const onDelete = useCallback(async (chatId: number) => {
    if (!confirm("Delete this chat and all its messages?")) return;
    try {
      await api(`/api/v1/chats/${chatId}`, { method: "DELETE" });
      setChats((prev) => prev?.filter((c) => c.id !== chatId) ?? prev);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

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
              <ChatRow
                key={c.id}
                chat={c}
                onRename={onRename}
                onDelete={onDelete}
              />
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

function ChatRow({
  chat,
  onRename,
  onDelete,
}: {
  chat: Chat;
  onRename: (id: number, title: string) => void;
  onDelete: (id: number) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState(chat.title);

  const commit = useCallback(() => {
    const t = title.trim();
    if (t && t !== chat.title) onRename(chat.id, t);
    else setTitle(chat.title);
    setEditing(false);
  }, [title, chat.id, chat.title, onRename]);

  return (
    <li className="rounded border border-neutral-200 p-3 hover:border-neutral-400 dark:border-neutral-800">
      <div className="flex items-center justify-between gap-2">
        {editing ? (
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            onBlur={commit}
            onKeyDown={(e) => {
              if (e.key === "Enter") commit();
              if (e.key === "Escape") {
                setTitle(chat.title);
                setEditing(false);
              }
            }}
            autoFocus
            className="flex-1 rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-900"
          />
        ) : (
          <Link
            href={`/chat/${chat.id}`}
            className="flex-1 truncate font-medium"
            title={chat.title}
          >
            {chat.title}
          </Link>
        )}
        <div className="flex items-center gap-1 text-xs">
          <span className="text-neutral-500 uppercase">{chat.scope}</span>
          <button
            onClick={(e) => {
              e.preventDefault();
              setEditing(true);
            }}
            className="rounded px-1.5 py-0.5 text-neutral-500 hover:bg-neutral-100 dark:hover:bg-neutral-800"
            title="Rename"
            aria-label="Rename chat"
          >
            ✎
          </button>
          <button
            onClick={(e) => {
              e.preventDefault();
              onDelete(chat.id);
            }}
            className="rounded px-1.5 py-0.5 text-neutral-500 hover:bg-red-100 hover:text-red-700 dark:hover:bg-red-950/40"
            title="Delete"
            aria-label="Delete chat"
          >
            ✕
          </button>
        </div>
      </div>
      <div className="mt-1 flex items-center justify-between gap-2 text-xs text-neutral-500">
        <span className="truncate">
          {chat.last_message_preview || (
            <span className="italic">No messages yet</span>
          )}
        </span>
        <span className="shrink-0 tabular-nums">
          {chat.message_count} msg · {formatRelative(chat.updated_at)}
          {chat.source_ids.length > 0 && ` · ${chat.source_ids.length} src`}
        </span>
      </div>
    </li>
  );
}

function formatRelative(iso: string): string {
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return "";
  const diff = Date.now() - t;
  const s = Math.floor(diff / 1000);
  if (s < 60) return "just now";
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h`;
  const d = Math.floor(h / 24);
  if (d < 30) return `${d}d`;
  return new Date(t).toLocaleDateString();
}
