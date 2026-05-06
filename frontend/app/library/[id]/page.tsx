"use client";

import dynamic from "next/dynamic";
import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { api, fetchAuthBlobUrl } from "@/lib/api";
import type {
  ChunkRow,
  Highlight,
  Source,
  StructureNode,
} from "@/lib/types";

const PdfViewer = dynamic(() => import("@/components/PdfViewer"), { ssr: false });

export default function SourceDetailPage({ params }: { params: { id: string } }) {
  const sourceId = Number(params.id);
  const search = useSearchParams();
  const initialPage = Number(search.get("page")) || 1;
  const initialChunkId = Number(search.get("chunk")) || null;

  const [source, setSource] = useState<Source | null>(null);
  const [structure, setStructure] = useState<StructureNode[]>([]);
  const [chunks, setChunks] = useState<ChunkRow[] | null>(null);
  const [highlights, setHighlights] = useState<Highlight[]>([]);
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState(initialPage);

  const loadAll = useCallback(async () => {
    try {
      const [src, st, hl] = await Promise.all([
        api<Source>(`/api/v1/sources/${sourceId}`),
        api<StructureNode[]>(`/api/v1/sources/${sourceId}/structure`),
        api<Highlight[]>(`/api/v1/highlights?source_id=${sourceId}`),
      ]);
      setSource(src);
      setStructure(st);
      setHighlights(hl);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [sourceId]);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  useEffect(() => {
    if (!source) return;
    if (source.source_format === "pdf") {
      let revoke: string | null = null;
      fetchAuthBlobUrl(`/api/v1/sources/${sourceId}/file`)
        .then((url) => {
          revoke = url;
          setPdfUrl(url);
        })
        .catch((e) => setError(e instanceof Error ? e.message : String(e)));
      return () => {
        if (revoke) URL.revokeObjectURL(revoke);
      };
    }
    // Non-PDF: load paragraph chunks.
    api<ChunkRow[]>(`/api/v1/sources/${sourceId}/chunks?limit=1000`)
      .then(setChunks)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, [source, sourceId]);

  // Scroll to deep-linked chunk in non-PDF view.
  useEffect(() => {
    if (!chunks || !initialChunkId) return;
    const el = document.getElementById(`chunk-${initialChunkId}`);
    if (el) el.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [chunks, initialChunkId]);

  const onSaveHighlight = useCallback(
    async (text: string, chunkId: number | null, page: number | null) => {
      const note = prompt("Optional note:") ?? null;
      try {
        await api<Highlight>("/api/v1/highlights", {
          method: "POST",
          body: JSON.stringify({
            source_id: sourceId,
            chunk_id: chunkId,
            page,
            text,
            note,
          }),
        });
        const hl = await api<Highlight[]>(`/api/v1/highlights?source_id=${sourceId}`);
        setHighlights(hl);
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      }
    },
    [sourceId],
  );

  const _selectionInfo = useCallback(() => {
    const sel = window.getSelection();
    const text = sel?.toString().trim();
    if (!text) return null;
    let node: Node | null = sel?.anchorNode ?? null;
    let chunkId: number | null = null;
    while (node) {
      if (node instanceof HTMLElement && node.dataset.chunkId) {
        chunkId = Number(node.dataset.chunkId);
        break;
      }
      node = node.parentNode;
    }
    return { text, chunkId };
  }, []);

  const saveSelection = useCallback(() => {
    const info = _selectionInfo();
    if (!info) {
      alert("Select some text first.");
      return;
    }
    onSaveHighlight(info.text, info.chunkId, source?.source_format === "pdf" ? currentPage : null);
  }, [_selectionInfo, onSaveHighlight, currentPage, source]);

  const saveToShelf = useCallback(async () => {
    const info = _selectionInfo();
    if (!info || !source) {
      alert("Select some text first.");
      return;
    }
    const note = prompt("Optional note:") ?? null;
    const chunk = chunks?.find((c) => c.id === info.chunkId);
    try {
      await api("/api/v1/quotes", {
        method: "POST",
        body: JSON.stringify({
          source_id: sourceId,
          chunk_id: info.chunkId,
          text: info.text,
          note,
          citation: {
            source_title: source.title,
            authors: source.authors,
            year: source.year,
            chapter_path: chunk?.chapter_path ?? [],
            page_start: chunk?.page_start ?? (source.source_format === "pdf" ? currentPage : null),
            page_end: chunk?.page_end ?? null,
          },
        }),
      });
      alert("Saved to quote shelf.");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [_selectionInfo, source, sourceId, chunks, currentPage]);

  const onDeleteHighlight = useCallback(async (id: number) => {
    try {
      await api<void>(`/api/v1/highlights/${id}`, { method: "DELETE" });
      setHighlights((rows) => rows.filter((r) => r.id !== id));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  const tocTree = useMemo(() => buildTocTree(structure), [structure]);

  if (error) {
    return <div className="m-6 rounded border border-red-300 bg-red-50 p-3 text-sm text-red-700">{error}</div>;
  }
  if (!source) return <div className="p-6 text-sm text-neutral-500">Loading...</div>;

  return (
    <div className="flex h-[calc(100vh-49px)]">
      <aside className="w-64 shrink-0 overflow-y-auto border-r border-neutral-200 bg-neutral-50 p-3 text-sm dark:border-neutral-800 dark:bg-neutral-900">
        <div className="mb-4">
          <h2 className="mb-1 font-semibold">{source.title}</h2>
          <div className="text-xs text-neutral-500">
            {source.authors.join(", ") || "—"}
            {source.year ? ` · ${source.year}` : ""}
          </div>
          <div className="mt-1 text-xs uppercase text-neutral-500">{source.source_format}</div>
          <div className="mt-1 text-xs">
            <span className="rounded bg-neutral-200 px-1.5 py-0.5 dark:bg-neutral-800">
              {source.status}
            </span>
          </div>
        </div>

        <div className="mb-4">
          <div className="mb-1 text-xs uppercase tracking-wide text-neutral-500">Contents</div>
          {tocTree.length === 0 ? (
            <div className="text-xs text-neutral-500">No structure detected.</div>
          ) : (
            <ul className="space-y-0.5">
              {tocTree.map((n) => (
                <TocItem
                  key={n.id}
                  node={n}
                  onClick={(node) => {
                    if (source.source_format === "pdf" && node.page_start) {
                      setCurrentPage(node.page_start);
                    } else {
                      const el = document.querySelector(
                        `[data-chapter="${node.chapter_path.join(" > ")}"]`,
                      );
                      if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
                    }
                  }}
                />
              ))}
            </ul>
          )}
        </div>

        <div>
          <div className="mb-1 flex items-center justify-between text-xs uppercase tracking-wide text-neutral-500">
            <span>Highlights ({highlights.length})</span>
            <div className="flex gap-2">
              <button onClick={saveSelection} className="text-blue-600 hover:underline">
                + Highlight
              </button>
              <button onClick={saveToShelf} className="text-blue-600 hover:underline">
                + Shelf
              </button>
            </div>
          </div>
          <ul className="space-y-2">
            {highlights.map((h) => (
              <li
                key={h.id}
                className="rounded border border-neutral-200 bg-white p-2 text-xs dark:border-neutral-800 dark:bg-neutral-950"
              >
                <div className="line-clamp-3">{h.text}</div>
                {h.note && <div className="mt-1 italic text-neutral-500">{h.note}</div>}
                <div className="mt-1 flex items-center justify-between text-[10px] text-neutral-500">
                  <span>{h.page ? `p. ${h.page}` : ""}</span>
                  <button
                    onClick={() => onDeleteHighlight(h.id)}
                    className="text-red-600 hover:underline"
                  >
                    delete
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </div>
      </aside>

      <div className="flex-1 overflow-hidden">
        {source.source_format === "pdf" ? (
          pdfUrl ? (
            <PdfViewer
              fileUrl={pdfUrl}
              initialPage={currentPage}
              onPageChange={setCurrentPage}
            />
          ) : (
            <div className="p-6 text-sm text-neutral-500">Loading document...</div>
          )
        ) : chunks ? (
          <ChunkView chunks={chunks} highlightedId={initialChunkId} />
        ) : (
          <div className="p-6 text-sm text-neutral-500">Loading content...</div>
        )}
      </div>
    </div>
  );
}

interface TocNode extends StructureNode {
  children: TocNode[];
}

function buildTocTree(rows: StructureNode[]): TocNode[] {
  const byId = new Map<number, TocNode>();
  rows.forEach((r) => byId.set(r.id, { ...r, children: [] }));
  const roots: TocNode[] = [];
  byId.forEach((node) => {
    if (node.parent_id && byId.has(node.parent_id)) {
      byId.get(node.parent_id)!.children.push(node);
    } else {
      roots.push(node);
    }
  });
  return roots;
}

function TocItem({
  node,
  onClick,
  depth = 0,
}: {
  node: TocNode;
  onClick: (n: TocNode) => void;
  depth?: number;
}) {
  return (
    <li>
      <button
        onClick={() => onClick(node)}
        className="block w-full truncate rounded px-1 py-0.5 text-left hover:bg-neutral-200 dark:hover:bg-neutral-800"
        style={{ paddingLeft: `${4 + depth * 10}px` }}
        title={node.title}
      >
        {node.title}
      </button>
      {node.children.length > 0 && (
        <ul>
          {node.children.map((c) => (
            <TocItem key={c.id} node={c} onClick={onClick} depth={depth + 1} />
          ))}
        </ul>
      )}
    </li>
  );
}

function ChunkView({
  chunks,
  highlightedId,
}: {
  chunks: ChunkRow[];
  highlightedId: number | null;
}) {
  let lastChapter = "";
  return (
    <div className="mx-auto h-full max-w-3xl overflow-y-auto p-8">
      {chunks.map((c) => {
        const chapter = c.chapter_path.join(" > ");
        const showHeader = chapter && chapter !== lastChapter;
        if (showHeader) lastChapter = chapter;
        return (
          <div key={c.id}>
            {showHeader && (
              <h3
                className="mt-6 border-b border-neutral-200 pb-1 text-sm font-semibold text-neutral-700 dark:border-neutral-800 dark:text-neutral-300"
                data-chapter={chapter}
              >
                {chapter}
              </h3>
            )}
            <p
              id={`chunk-${c.id}`}
              data-chunk-id={c.id}
              className={`my-3 text-base leading-relaxed ${
                highlightedId === c.id ? "rounded bg-yellow-100 p-2 dark:bg-yellow-900/30" : ""
              }`}
            >
              {c.text}
            </p>
          </div>
        );
      })}
    </div>
  );
}
