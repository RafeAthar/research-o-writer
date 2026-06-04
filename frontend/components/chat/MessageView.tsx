"use client";

import { useCallback, useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";

import type { ChatCitation, ChatPassage } from "@/lib/types";

import { CitationCard } from "./CitationCard";
import { CitationRef } from "./CitationRef";

export interface DisplayMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations: ChatCitation[];
  passages?: ChatPassage[];
  issues?: string[];
  suggestions?: string[];
  stop_reason?: string | null;
  streaming?: boolean;
  error?: string | null;
}

interface Props {
  m: DisplayMessage;
  isLast: boolean;
  busy: boolean;
  onRegenerate: () => void;
  onContinue: () => void;
  onSendSuggestion: (text: string) => void;
}

export function MessageView({
  m,
  isLast,
  busy,
  onRegenerate,
  onContinue,
  onSendSuggestion,
}: Props) {
  if (m.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] whitespace-pre-wrap rounded-lg bg-blue-600 px-3 py-2 text-sm text-white">
          {m.content}
        </div>
      </div>
    );
  }

  // Index citations/passages by passage number so the inline chips can resolve
  // them without scanning per render.
  const sourceByNum = useMemo(() => {
    const map = new Map<number, ChatCitation | ChatPassage>();
    for (const c of m.citations) map.set(c.passage, c);
    for (const p of m.passages ?? []) if (!map.has(p.id)) map.set(p.id, p);
    return map;
  }, [m.citations, m.passages]);

  return (
    <div className="space-y-2">
      <div className="group relative rounded-lg bg-neutral-100 px-3 py-2 text-sm dark:bg-neutral-900">
        {m.error ? (
          <div className="text-red-700">{m.error}</div>
        ) : (
          <div className="prose prose-sm max-w-none leading-relaxed dark:prose-invert">
            <MarkdownWithCites text={m.content} sourceByNum={sourceByNum} />
            {m.streaming && <span className="ml-1 animate-pulse">▍</span>}
          </div>
        )}

        {!m.streaming && !m.error && m.content && (
          <MessageActions
            text={m.content}
            citations={m.citations}
            isLast={isLast}
            busy={busy}
            onRegenerate={onRegenerate}
          />
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

      {isLast && !m.streaming && m.stop_reason === "max_tokens" && (
        <button
          onClick={onContinue}
          disabled={busy}
          className="rounded border border-amber-300 bg-amber-50 px-3 py-1.5 text-xs font-medium text-amber-800 hover:bg-amber-100 disabled:opacity-50 dark:border-amber-700 dark:bg-amber-950/40 dark:text-amber-200"
        >
          Response was cut off · Continue →
        </button>
      )}

      {isLast && !m.streaming && !!m.suggestions && m.suggestions.length > 0 && (
        <div className="flex flex-wrap gap-2 pt-1">
          {m.suggestions.map((s, i) => (
            <button
              key={i}
              disabled={busy}
              onClick={() => onSendSuggestion(s)}
              className="rounded-full border border-neutral-300 bg-white px-3 py-1 text-xs text-neutral-700 hover:bg-neutral-100 disabled:opacity-50 dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-300 dark:hover:bg-neutral-800"
            >
              {s}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function MessageActions({
  text,
  citations,
  isLast,
  busy,
  onRegenerate,
}: {
  text: string;
  citations: ChatCitation[];
  isLast: boolean;
  busy: boolean;
  onRegenerate: () => void;
}) {
  const [copied, setCopied] = useState(false);
  const copy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(messageToMarkdown(text, citations));
      setCopied(true);
      setTimeout(() => setCopied(false), 1200);
    } catch {
      // ignore
    }
  }, [text, citations]);

  return (
    <div className="mt-1 flex gap-2 text-[11px] text-neutral-500 opacity-0 transition-opacity group-hover:opacity-100">
      <button
        onClick={copy}
        className="rounded px-1.5 py-0.5 hover:bg-neutral-200 dark:hover:bg-neutral-800"
      >
        {copied ? "Copied" : "Copy"}
      </button>
      {isLast && (
        <button
          disabled={busy}
          onClick={onRegenerate}
          className="rounded px-1.5 py-0.5 hover:bg-neutral-200 disabled:opacity-50 dark:hover:bg-neutral-800"
        >
          Regenerate
        </button>
      )}
    </div>
  );
}

/** Render markdown text where `[Pn]` tokens become CitationRef chips. */
function MarkdownWithCites({
  text,
  sourceByNum,
}: {
  text: string;
  sourceByNum: Map<number, ChatCitation | ChatPassage>;
}) {
  // Split by [Pn] so they survive react-markdown's text node walk. We render
  // a single ReactMarkdown tree, then post-process the rendered text nodes by
  // injecting chip components for each [Pn] token.
  return (
    <ReactMarkdown
      components={{
        // Custom paragraph renderer: it receives children where any
        // text-node containing [Pn] gets split into mixed react children.
        p: ({ children }) => <p>{splitChildrenForCites(children, sourceByNum)}</p>,
        li: ({ children }) => <li>{splitChildrenForCites(children, sourceByNum)}</li>,
      }}
    >
      {text}
    </ReactMarkdown>
  );
}

const CITE_RE = /\[P(\d+)\]/g;

function splitChildrenForCites(
  children: React.ReactNode,
  sourceByNum: Map<number, ChatCitation | ChatPassage>,
): React.ReactNode {
  const out: React.ReactNode[] = [];
  const walk = (node: React.ReactNode, keyPrefix: string) => {
    if (typeof node === "string") {
      let last = 0;
      let match: RegExpExecArray | null;
      const re = new RegExp(CITE_RE.source, "g");
      let idx = 0;
      while ((match = re.exec(node))) {
        if (match.index > last) out.push(node.slice(last, match.index));
        const n = Number(match[1]);
        out.push(
          <CitationRef
            key={`${keyPrefix}-${idx++}`}
            n={n}
            source={sourceByNum.get(n) ?? null}
          />,
        );
        last = match.index + match[0].length;
      }
      if (last < node.length) out.push(node.slice(last));
      return;
    }
    if (Array.isArray(node)) {
      node.forEach((c, i) => walk(c, `${keyPrefix}-${i}`));
      return;
    }
    out.push(node);
  };
  walk(children, "c");
  return out;
}

function CitationCards({
  citations,
  passages,
}: {
  citations: ChatCitation[];
  passages: ChatPassage[];
}) {
  const cards =
    citations.length > 0
      ? citations.map((c) => ({
          shape: {
            n: c.passage,
            chunk_id: c.chunk_id,
            source_id: c.source_id,
            source_title: c.source_title,
            chapter_path: c.chapter_path,
            page_start: c.page_start,
            page_end: c.page_end,
            preview: c.preview,
          },
          raw: c,
        }))
      : passages.map((p) => ({
          shape: {
            n: p.id,
            chunk_id: p.chunk_id,
            source_id: p.source_id,
            source_title: p.source_title,
            chapter_path: p.chapter_path,
            page_start: p.page_start,
            page_end: p.page_end,
            preview: p.preview,
          },
          raw: null,
        }));

  return (
    <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
      {cards.map(({ shape, raw }) => (
        <CitationCard
          key={`${shape.n}-${shape.chunk_id}`}
          c={shape}
          raw={raw}
        />
      ))}
    </div>
  );
}

function messageToMarkdown(text: string, citations: ChatCitation[]): string {
  if (citations.length === 0) return text;
  const lines: string[] = [text, "", "---", "", "**Citations**"];
  for (const c of citations) {
    const page =
      c.page_start && c.page_end && c.page_end !== c.page_start
        ? `pp. ${c.page_start}-${c.page_end}`
        : c.page_start
          ? `p. ${c.page_start}`
          : "";
    const chapter = c.chapter_path.length > 0 ? ` — ${c.chapter_path.join(" > ")}` : "";
    lines.push(
      `- [P${c.passage}] *${c.source_title}*${chapter}${page ? `, ${page}` : ""}`,
    );
  }
  return lines.join("\n");
}
