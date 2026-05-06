"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { api } from "@/lib/api";
import { streamSSE } from "@/lib/sse";
import type {
  ChatCitation,
  ChatMessage,
  ChatPassage,
} from "@/lib/types";

interface DisplayMessage {
  id: string; // local id; persisted ones get "db-<id>"
  role: "user" | "assistant";
  content: string;
  citations: ChatCitation[];
  passages?: ChatPassage[]; // for in-flight assistant messages
  issues?: string[];
  streaming?: boolean;
  error?: string | null;
}

export default function ChatDetailPage({ params }: { params: { id: string } }) {
  const chatId = Number(params.id);
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<"default" | "hard">("default");
  const scrollRef = useRef<HTMLDivElement>(null);

  const loadHistory = useCallback(async () => {
    try {
      const rows = await api<ChatMessage[]>(`/api/v1/chats/${chatId}/messages`);
      setMessages(
        rows.map((r) => ({
          id: `db-${r.id}`,
          role: r.role,
          content: r.content,
          citations: r.citations ?? [],
          error: r.error,
        })),
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [chatId]);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const send = useCallback(async () => {
    const content = input.trim();
    if (!content || busy) return;
    setInput("");
    setBusy(true);
    setError(null);

    const userMsg: DisplayMessage = {
      id: `local-u-${Date.now()}`,
      role: "user",
      content,
      citations: [],
    };
    const asstMsg: DisplayMessage = {
      id: `local-a-${Date.now()}`,
      role: "assistant",
      content: "",
      citations: [],
      streaming: true,
    };
    setMessages((m) => [...m, userMsg, asstMsg]);

    try {
      for await (const ev of streamSSE(`/api/v1/chats/${chatId}/messages`, {
        content,
        mode,
        k: 10,
      })) {
        if (ev.event === "meta") {
          const data = JSON.parse(ev.data) as { passages: ChatPassage[] };
          setMessages((m) =>
            m.map((x) => (x.id === asstMsg.id ? { ...x, passages: data.passages } : x)),
          );
        } else if (ev.event === "token") {
          const delta = JSON.parse(ev.data) as string;
          setMessages((m) =>
            m.map((x) =>
              x.id === asstMsg.id ? { ...x, content: x.content + delta } : x,
            ),
          );
        } else if (ev.event === "done") {
          const data = JSON.parse(ev.data) as {
            text: string;
            used_passages: number[];
            issues: string[];
            citations: ChatCitation[];
          };
          setMessages((m) =>
            m.map((x) =>
              x.id === asstMsg.id
                ? {
                    ...x,
                    content: data.text,
                    citations: data.citations,
                    issues: data.issues,
                    streaming: false,
                  }
                : x,
            ),
          );
        } else if (ev.event === "error") {
          const data = JSON.parse(ev.data) as { error: string };
          setMessages((m) =>
            m.map((x) =>
              x.id === asstMsg.id ? { ...x, streaming: false, error: data.error } : x,
            ),
          );
        }
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setMessages((m) =>
        m.map((x) => (x.id === asstMsg.id ? { ...x, streaming: false } : x)),
      );
    } finally {
      setBusy(false);
    }
  }, [input, busy, chatId, mode]);

  return (
    <div className="mx-auto flex h-[calc(100vh-49px)] max-w-4xl flex-col p-4">
      {error && (
        <div className="mb-3 rounded border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </div>
      )}
      <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto pr-2">
        {messages.length === 0 && (
          <div className="mt-12 text-center text-sm text-neutral-500">
            Ask a question grounded in your library.
          </div>
        )}
        {messages.map((m) => (
          <MessageBubble key={m.id} m={m} />
        ))}
      </div>

      <div className="mt-3 flex items-end gap-2 border-t border-neutral-200 pt-3 dark:border-neutral-800">
        <select
          value={mode}
          onChange={(e) => setMode(e.target.value as "default" | "hard")}
          className="rounded border border-neutral-300 px-2 py-1.5 text-sm dark:border-neutral-700 dark:bg-neutral-900"
          title="default: Sonnet · hard: Opus"
        >
          <option value="default">Default</option>
          <option value="hard">Hard synthesis</option>
        </select>
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send();
            }
          }}
          rows={2}
          placeholder="Ask a question..."
          className="flex-1 resize-none rounded border border-neutral-300 px-3 py-2 text-sm dark:border-neutral-700 dark:bg-neutral-900"
          disabled={busy}
        />
        <button
          onClick={send}
          disabled={busy || !input.trim()}
          className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {busy ? "..." : "Send"}
        </button>
      </div>
    </div>
  );
}

function MessageBubble({ m }: { m: DisplayMessage }) {
  if (m.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] whitespace-pre-wrap rounded-lg bg-blue-600 px-3 py-2 text-sm text-white">
          {m.content}
        </div>
      </div>
    );
  }
  return (
    <div className="space-y-2">
      <div className="rounded-lg bg-neutral-100 px-3 py-2 text-sm dark:bg-neutral-900">
        {m.error ? (
          <div className="text-red-700">{m.error}</div>
        ) : (
          <div className="whitespace-pre-wrap leading-relaxed">
            {m.content}
            {m.streaming && <span className="ml-1 animate-pulse">▍</span>}
          </div>
        )}
      </div>
      {m.issues && m.issues.length > 0 && (
        <div className="rounded border border-red-300 bg-red-50 px-3 py-2 text-xs text-red-700 dark:border-red-800 dark:bg-red-950/40 dark:text-red-300">
          <div className="mb-1 font-medium">Citation issues</div>
          <ul className="list-disc pl-5">
            {m.issues.map((iss, i) => (
              <li key={i}>{iss}</li>
            ))}
          </ul>
        </div>
      )}
      {(m.citations.length > 0 || (m.passages && m.passages.length > 0)) && (
        <CitationCards citations={m.citations} passages={m.passages ?? []} />
      )}
    </div>
  );
}

function CitationCards({
  citations,
  passages,
}: {
  citations: ChatCitation[];
  passages: ChatPassage[];
}) {
  // Prefer verified citations; fall back to in-flight passages so the user can
  // see what was retrieved while the model streams.
  const cards =
    citations.length > 0
      ? citations.map((c) => ({
          n: c.passage,
          chunk_id: c.chunk_id,
          source_id: c.source_id,
          source_title: c.source_title,
          chapter_path: c.chapter_path,
          page_start: c.page_start,
          page_end: c.page_end,
          preview: c.preview,
        }))
      : passages.map((p) => ({
          n: p.id,
          chunk_id: p.chunk_id,
          source_id: p.source_id,
          source_title: p.source_title,
          chapter_path: p.chapter_path,
          page_start: p.page_start,
          page_end: p.page_end,
          preview: p.preview,
        }));

  return (
    <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
      {cards.map((c) => {
        const href =
          `/library/${c.source_id}?chunk=${c.chunk_id}` +
          (c.page_start ? `&page=${c.page_start}` : "");
        const pageStr =
          c.page_start && c.page_end && c.page_end !== c.page_start
            ? `pp. ${c.page_start}-${c.page_end}`
            : c.page_start
              ? `p. ${c.page_start}`
              : "";
        return (
          <Link
            key={`${c.n}-${c.chunk_id}`}
            href={href}
            className="block rounded border border-neutral-200 bg-white p-2 text-xs hover:border-neutral-400 dark:border-neutral-800 dark:bg-neutral-950"
          >
            <div className="mb-1 flex items-center justify-between">
              <span className="font-mono text-blue-700 dark:text-blue-300">[P{c.n}]</span>
              <span className="text-neutral-500">{pageStr}</span>
            </div>
            <div className="font-medium">{c.source_title}</div>
            {c.chapter_path.length > 0 && (
              <div className="text-neutral-500">{c.chapter_path.join(" > ")}</div>
            )}
            <div className="mt-1 line-clamp-3 text-neutral-700 dark:text-neutral-300">
              {c.preview}
            </div>
          </Link>
        );
      })}
    </div>
  );
}
