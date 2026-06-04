"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { api } from "@/lib/api";
import type { ChatCitation, OutlineNode, Project } from "@/lib/types";

interface CitationCardShape {
  n: number;
  chunk_id: number;
  source_id: number;
  source_title: string;
  chapter_path: string[];
  page_start: number | null;
  page_end: number | null;
  preview: string;
}

interface Props {
  c: CitationCardShape;
  raw: ChatCitation | null;
}

/** A citation card with a "+" menu to save/pin or copy the passage. */
export function CitationCard({ c, raw }: Props) {
  const href =
    `/library/${c.source_id}?chunk=${c.chunk_id}` +
    (c.page_start ? `&page=${c.page_start}` : "");
  const pageStr =
    c.page_start && c.page_end && c.page_end !== c.page_start
      ? `pp. ${c.page_start}-${c.page_end}`
      : c.page_start
        ? `p. ${c.page_start}`
        : "";

  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <div className="relative rounded border border-neutral-200 bg-white p-2 text-xs dark:border-neutral-800 dark:bg-neutral-950">
      <div className="mb-1 flex items-center justify-between">
        <span className="font-mono text-blue-700 dark:text-blue-300">[P{c.n}]</span>
        <div className="flex items-center gap-2">
          <span className="text-neutral-500">{pageStr}</span>
          <button
            onClick={() => setMenuOpen((v) => !v)}
            className="rounded px-1 leading-none text-neutral-500 hover:bg-neutral-100 dark:hover:bg-neutral-800"
            aria-label="Citation actions"
            title="Save / pin / copy"
          >
            +
          </button>
        </div>
      </div>
      <Link href={href} className="block hover:underline">
        <div className="font-medium">{c.source_title}</div>
        {c.chapter_path.length > 0 && (
          <div className="text-neutral-500">{c.chapter_path.join(" > ")}</div>
        )}
        <div className="mt-1 line-clamp-3 text-neutral-700 dark:text-neutral-300">
          {c.preview}
        </div>
      </Link>
      {menuOpen && (
        <CitationActions
          card={c}
          raw={raw}
          onClose={() => setMenuOpen(false)}
        />
      )}
    </div>
  );
}

function CitationActions({
  card,
  raw,
  onClose,
}: {
  card: CitationCardShape;
  raw: ChatCitation | null;
  onClose: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [pickingNode, setPickingNode] = useState(false);

  const buildCitation = useCallback(
    () => ({
      source_title: card.source_title,
      chapter_path: card.chapter_path,
      page_start: card.page_start,
      page_end: card.page_end,
      paragraph_index: raw?.paragraph_index ?? null,
      char_start: raw?.char_start ?? null,
      char_end: raw?.char_end ?? null,
    }),
    [card, raw],
  );

  const onCopyMarkdown = useCallback(async () => {
    const cite =
      `*${card.source_title}*` +
      (card.chapter_path.length > 0 ? ` — ${card.chapter_path.join(" > ")}` : "") +
      (card.page_start
        ? `, ${
            card.page_end && card.page_end !== card.page_start
              ? `pp. ${card.page_start}-${card.page_end}`
              : `p. ${card.page_start}`
          }`
        : "");
    const md = `> ${card.preview.replace(/\n+/g, " ").trim()}\n>\n> — ${cite}`;
    try {
      await navigator.clipboard.writeText(md);
      setMsg("Copied");
    } catch {
      setMsg("Copy failed");
    }
    setTimeout(onClose, 800);
  }, [card, onClose]);

  const onSaveQuote = useCallback(async () => {
    setBusy(true);
    setMsg(null);
    try {
      await api("/api/v1/quotes", {
        method: "POST",
        body: JSON.stringify({
          source_id: card.source_id,
          chunk_id: card.chunk_id,
          text: card.preview,
          citation: buildCitation(),
        }),
      });
      setMsg("Saved to shelf");
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Failed");
    } finally {
      setBusy(false);
      setTimeout(onClose, 1000);
    }
  }, [card, buildCitation, onClose]);

  return (
    <div className="absolute right-0 top-7 z-30 w-56 rounded border border-neutral-200 bg-white p-1 text-xs shadow-lg dark:border-neutral-700 dark:bg-neutral-900">
      {msg && (
        <div className="px-2 py-1 text-neutral-500">{msg}</div>
      )}
      {!msg && !pickingNode && (
        <>
          <button
            onClick={onCopyMarkdown}
            className="block w-full rounded px-2 py-1.5 text-left hover:bg-neutral-100 dark:hover:bg-neutral-800"
          >
            Copy as Markdown citation
          </button>
          <button
            disabled={busy}
            onClick={onSaveQuote}
            className="block w-full rounded px-2 py-1.5 text-left hover:bg-neutral-100 disabled:opacity-50 dark:hover:bg-neutral-800"
          >
            Save to quote shelf
          </button>
          <button
            disabled={busy}
            onClick={() => setPickingNode(true)}
            className="block w-full rounded px-2 py-1.5 text-left hover:bg-neutral-100 disabled:opacity-50 dark:hover:bg-neutral-800"
          >
            Pin to outline node…
          </button>
          <button
            onClick={onClose}
            className="block w-full rounded px-2 py-1.5 text-left text-neutral-500 hover:bg-neutral-100 dark:hover:bg-neutral-800"
          >
            Cancel
          </button>
        </>
      )}
      {pickingNode && (
        <OutlineNodePicker
          card={card}
          buildCitation={buildCitation}
          onDone={(label) => {
            setMsg(label);
            setPickingNode(false);
          }}
        />
      )}
    </div>
  );
}

function OutlineNodePicker({
  card,
  buildCitation,
  onDone,
}: {
  card: CitationCardShape;
  buildCitation: () => Record<string, unknown>;
  onDone: (msg: string) => void;
}) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState<number | null>(null);
  const [nodes, setNodes] = useState<OutlineNode[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const ps = await api<Project[]>("/api/v1/projects");
        setProjects(ps);
        if (ps.length > 0) setProjectId(ps[0].id);
      } catch (e) {
        onDone(e instanceof Error ? e.message : "Failed to load projects");
      } finally {
        setLoading(false);
      }
    })();
  }, [onDone]);

  useEffect(() => {
    if (projectId == null) return;
    (async () => {
      try {
        const ns = await api<OutlineNode[]>(
          `/api/v1/projects/${projectId}/nodes`,
        );
        setNodes(ns);
      } catch (e) {
        onDone(e instanceof Error ? e.message : "Failed to load nodes");
      }
    })();
  }, [projectId, onDone]);

  const pin = useCallback(
    async (nodeId: number) => {
      try {
        await api(`/api/v1/projects/${projectId}/evidence`, {
          method: "POST",
          body: JSON.stringify({
            outline_node_id: nodeId,
            source_id: card.source_id,
            chunk_id: card.chunk_id,
            quote_text: card.preview,
            citation: buildCitation(),
          }),
        });
        onDone("Pinned");
      } catch (e) {
        onDone(e instanceof Error ? e.message : "Failed");
      }
    },
    [projectId, card, buildCitation, onDone],
  );

  if (loading) return <div className="px-2 py-1 text-neutral-500">Loading…</div>;
  if (projects.length === 0) {
    return (
      <div className="px-2 py-1 text-neutral-500">
        No projects yet. Create one first.
      </div>
    );
  }

  return (
    <div className="max-h-64 overflow-y-auto p-1">
      <select
        value={projectId ?? ""}
        onChange={(e) => setProjectId(Number(e.target.value))}
        className="mb-1 w-full rounded border border-neutral-300 px-1 py-0.5 text-xs dark:border-neutral-700 dark:bg-neutral-900"
      >
        {projects.map((p) => (
          <option key={p.id} value={p.id}>
            {p.title}
          </option>
        ))}
      </select>
      {nodes.length === 0 && (
        <div className="px-1 py-1 text-neutral-500">No outline nodes.</div>
      )}
      {nodes.map((n) => (
        <button
          key={n.id}
          onClick={() => pin(n.id)}
          className="block w-full truncate rounded px-2 py-1 text-left hover:bg-neutral-100 dark:hover:bg-neutral-800"
          title={n.title}
        >
          {n.title}
        </button>
      ))}
    </div>
  );
}
