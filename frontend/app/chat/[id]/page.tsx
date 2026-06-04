"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { ChatHeader } from "@/components/chat/ChatHeader";
import { MessageView, type DisplayMessage } from "@/components/chat/MessageView";
import { api } from "@/lib/api";
import { chatThreadToMarkdown, downloadText } from "@/lib/chatExport";
import { streamSSE } from "@/lib/sse";
import type {
  Chat,
  ChatCitation,
  ChatMessage,
  ChatPassage,
} from "@/lib/types";

export default function ChatDetailPage({ params }: { params: { id: string } }) {
  const chatId = Number(params.id);
  const [chat, setChat] = useState<Chat | null>(null);
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<"default" | "hard">("default");
  const [k, setK] = useState(10);
  const scrollRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  const loadChat = useCallback(async () => {
    try {
      const [c, rows] = await Promise.all([
        api<Chat>(`/api/v1/chats/${chatId}`),
        api<ChatMessage[]>(`/api/v1/chats/${chatId}/messages`),
      ]);
      setChat(c);
      setMessages(
        rows.map((r) => ({
          id: `db-${r.id}`,
          role: r.role,
          content: r.content,
          citations: r.citations ?? [],
          suggestions: r.suggestions ?? undefined,
          stop_reason: r.stop_reason ?? undefined,
          error: r.error,
        })),
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [chatId]);

  useEffect(() => {
    loadChat();
  }, [loadChat]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const sendContent = useCallback(
    async (rawContent: string) => {
      const content = rawContent.trim();
      if (!content || busy) return;
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

      const ctrl = new AbortController();
      abortRef.current = ctrl;

      try {
        for await (const ev of streamSSE(
          `/api/v1/chats/${chatId}/messages`,
          { content, mode, k },
          ctrl.signal,
        )) {
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
              suggestions?: string[];
              stop_reason?: string | null;
            };
            setMessages((m) =>
              m.map((x) =>
                x.id === asstMsg.id
                  ? {
                      ...x,
                      content: data.text,
                      citations: data.citations,
                      issues: data.issues,
                      suggestions: data.suggestions,
                      stop_reason: data.stop_reason ?? null,
                      streaming: false,
                    }
                  : x,
              ),
            );
          } else if (ev.event === "error") {
            const data = JSON.parse(ev.data) as { error: string };
            setMessages((m) =>
              m.map((x) =>
                x.id === asstMsg.id
                  ? { ...x, streaming: false, error: data.error }
                  : x,
              ),
            );
          }
        }
      } catch (e) {
        if ((e as Error)?.name === "AbortError") {
          // User pressed Stop — keep whatever the model already streamed.
          setMessages((m) =>
            m.map((x) =>
              x.id === asstMsg.id ? { ...x, streaming: false } : x,
            ),
          );
        } else {
          setError(e instanceof Error ? e.message : String(e));
          setMessages((m) =>
            m.map((x) =>
              x.id === asstMsg.id ? { ...x, streaming: false } : x,
            ),
          );
        }
      } finally {
        abortRef.current = null;
        setBusy(false);
      }
    },
    [busy, chatId, mode, k],
  );

  const send = useCallback(async () => {
    const content = input;
    setInput("");
    await sendContent(content);
  }, [input, sendContent]);

  const stop = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  const regenerate = useCallback(async () => {
    // Find last assistant + the user turn before it.
    let lastAsstIdx = -1;
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === "assistant") {
        lastAsstIdx = i;
        break;
      }
    }
    if (lastAsstIdx < 1) return;
    const userTurn = messages[lastAsstIdx - 1];
    if (userTurn.role !== "user") return;
    const lastAsst = messages[lastAsstIdx];

    // If the assistant message is persisted, delete it server-side so history
    // doesn't double up.
    if (lastAsst.id.startsWith("db-")) {
      const mid = Number(lastAsst.id.slice(3));
      try {
        await api(`/api/v1/chats/${chatId}/messages/${mid}`, {
          method: "DELETE",
        });
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
        return;
      }
    }
    // Also delete the user message so its re-post doesn't duplicate.
    if (userTurn.id.startsWith("db-")) {
      const uid = Number(userTurn.id.slice(3));
      try {
        await api(`/api/v1/chats/${chatId}/messages/${uid}`, {
          method: "DELETE",
        });
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
        return;
      }
    }
    setMessages((m) => m.slice(0, lastAsstIdx - 1));
    await sendContent(userTurn.content);
  }, [messages, chatId, sendContent]);

  const continueLast = useCallback(async () => {
    // Soft-cut prompt — backend treats it as a new turn that re-sees full context.
    await sendContent("Please continue from where you stopped, without repeating.");
  }, [sendContent]);

  const onChatPatch = useCallback(
    async (patch: Partial<Pick<Chat, "scope" | "source_ids">>) => {
      if (!chat) return;
      const next = { ...chat, ...patch };
      setChat(next);
      try {
        await api(`/api/v1/chats/${chatId}`, {
          method: "PATCH",
          body: JSON.stringify(patch),
        });
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
        setChat(chat);
      }
    },
    [chat, chatId],
  );

  const onExport = useCallback(async () => {
    if (!chat) return;
    try {
      const rows = await api<ChatMessage[]>(
        `/api/v1/chats/${chatId}/messages`,
      );
      const md = chatThreadToMarkdown(chat, rows);
      const safe = chat.title.replace(/[^a-z0-9-_ ]/gi, "").slice(0, 80) || "chat";
      downloadText(`${safe}.md`, md);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [chat, chatId]);

  return (
    <div className="mx-auto flex h-[calc(100vh-49px)] max-w-4xl flex-col p-4">
      {chat && (
        <ChatHeader
          chat={chat}
          k={k}
          onChange={onChatPatch}
          onChangeK={setK}
          onExport={onExport}
        />
      )}
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
        {messages.map((m, i) => (
          <MessageView
            key={m.id}
            m={m}
            isLast={i === messages.length - 1}
            busy={busy}
            onRegenerate={regenerate}
            onContinue={continueLast}
            onSendSuggestion={sendContent}
          />
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
        {busy ? (
          <button
            onClick={stop}
            className="rounded bg-neutral-700 px-4 py-2 text-sm font-medium text-white hover:bg-neutral-800"
          >
            Stop
          </button>
        ) : (
          <button
            onClick={send}
            disabled={!input.trim()}
            className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            Send
          </button>
        )}
      </div>
    </div>
  );
}
