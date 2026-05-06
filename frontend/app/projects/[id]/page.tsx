"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { api, downloadAuthFile } from "@/lib/api";
import type {
  EvidenceCard,
  OutlineNode,
  Project,
  SearchHit,
} from "@/lib/types";

const TipTapEditor = dynamic(() => import("@/components/TipTapEditor"), { ssr: false });

interface OutlineTreeNode extends OutlineNode {
  children: OutlineTreeNode[];
}

export default function ProjectDetailPage({ params }: { params: { id: string } }) {
  const projectId = Number(params.id);
  const [project, setProject] = useState<Project | null>(null);
  const [nodes, setNodes] = useState<OutlineNode[]>([]);
  const [evidence, setEvidence] = useState<EvidenceCard[]>([]);
  const [selectedNodeId, setSelectedNodeId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const reloadAll = useCallback(async () => {
    try {
      const [p, ns, ev] = await Promise.all([
        api<Project>(`/api/v1/projects/${projectId}`),
        api<OutlineNode[]>(`/api/v1/projects/${projectId}/nodes`),
        api<EvidenceCard[]>(`/api/v1/projects/${projectId}/evidence`),
      ]);
      setProject(p);
      setNodes(ns);
      setEvidence(ev);
      if (selectedNodeId === null && ns.length > 0) setSelectedNodeId(ns[0].id);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [projectId, selectedNodeId]);

  useEffect(() => {
    reloadAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  const tree = useMemo(() => buildTree(nodes), [nodes]);
  const selected = nodes.find((n) => n.id === selectedNodeId) ?? null;
  const selectedEvidence = evidence
    .filter((e) => e.outline_node_id === selectedNodeId)
    .sort((a, b) => a.order_in_node - b.order_in_node);

  const addNode = useCallback(
    async (parentId: number | null) => {
      const title = prompt("Section title:");
      if (!title) return;
      try {
        const node = await api<OutlineNode>(`/api/v1/projects/${projectId}/nodes`, {
          method: "POST",
          body: JSON.stringify({ title, parent_id: parentId, order_in_parent: 0 }),
        });
        setNodes((rows) => [...rows, node]);
        setSelectedNodeId(node.id);
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      }
    },
    [projectId],
  );

  const updateNode = useCallback(
    async (id: number, patch: Partial<OutlineNode>) => {
      try {
        const updated = await api<OutlineNode>(
          `/api/v1/projects/${projectId}/nodes/${id}`,
          { method: "PATCH", body: JSON.stringify(patch) },
        );
        setNodes((rows) => rows.map((r) => (r.id === id ? updated : r)));
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      }
    },
    [projectId],
  );

  const deleteNode = useCallback(
    async (id: number) => {
      if (!confirm("Delete this section and its children?")) return;
      try {
        await api<void>(`/api/v1/projects/${projectId}/nodes/${id}`, {
          method: "DELETE",
        });
        await reloadAll();
        if (selectedNodeId === id) setSelectedNodeId(null);
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      }
    },
    [projectId, reloadAll, selectedNodeId],
  );

  const onSaveBody = useCallback(
    (html: string) => {
      if (selectedNodeId === null) return;
      updateNode(selectedNodeId, { body_md: html });
    },
    [selectedNodeId, updateNode],
  );

  const onAddEvidence = useCallback(
    async (hit: SearchHit) => {
      if (selectedNodeId === null) return;
      try {
        const card = await api<EvidenceCard>(
          `/api/v1/projects/${projectId}/evidence`,
          {
            method: "POST",
            body: JSON.stringify({
              outline_node_id: selectedNodeId,
              source_id: hit.source_id,
              chunk_id: hit.chunk_id,
              quote_text: hit.text,
              citation: {
                source_title: hit.source_title,
                chapter_path: hit.chapter_path,
                page_start: hit.page_start,
                page_end: hit.page_end,
                paragraph_index: hit.paragraph_index,
              },
              order_in_node: selectedEvidence.length,
            }),
          },
        );
        setEvidence((rows) => [...rows, card]);
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      }
    },
    [projectId, selectedNodeId, selectedEvidence.length],
  );

  const onDeleteEvidence = useCallback(
    async (id: number) => {
      try {
        await api<void>(`/api/v1/projects/${projectId}/evidence/${id}`, {
          method: "DELETE",
        });
        setEvidence((rows) => rows.filter((r) => r.id !== id));
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      }
    },
    [projectId],
  );

  if (!project) {
    return (
      <div className="p-6 text-sm text-neutral-500">
        {error ? <div className="text-red-700">{error}</div> : "Loading..."}
      </div>
    );
  }

  return (
    <div className="flex h-[calc(100vh-49px)]">
      {/* Outline tree */}
      <aside className="w-64 shrink-0 overflow-y-auto border-r border-neutral-200 bg-neutral-50 p-3 text-sm dark:border-neutral-800 dark:bg-neutral-900">
        <h1 className="mb-2 font-semibold">{project.title}</h1>
        <button
          onClick={() => addNode(null)}
          className="mb-2 w-full rounded bg-blue-600 px-2 py-1 text-xs font-medium text-white hover:bg-blue-700"
        >
          + New section
        </button>
        <button
          onClick={() =>
            downloadAuthFile(
              `/api/v1/projects/${projectId}/export.md`,
              `${project.title}.md`,
            ).catch((e) => setError(e instanceof Error ? e.message : String(e)))
          }
          className="mb-3 w-full rounded border border-neutral-300 px-2 py-1 text-xs hover:bg-neutral-200 dark:border-neutral-700 dark:hover:bg-neutral-800"
        >
          Export Markdown
        </button>
        {tree.length === 0 && <div className="text-xs text-neutral-500">No sections yet.</div>}
        <ul className="space-y-0.5">
          {tree.map((n) => (
            <OutlineItem
              key={n.id}
              node={n}
              selectedId={selectedNodeId}
              onSelect={setSelectedNodeId}
              onAddChild={addNode}
              onDelete={deleteNode}
            />
          ))}
        </ul>
      </aside>

      {/* Main editor */}
      <div className="flex-1 overflow-y-auto p-6">
        {error && (
          <div className="mb-3 rounded border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </div>
        )}
        {selected ? (
          <div className="mx-auto max-w-3xl space-y-6">
            <input
              value={selected.title}
              onChange={(e) =>
                setNodes((rows) =>
                  rows.map((r) => (r.id === selected.id ? { ...r, title: e.target.value } : r)),
                )
              }
              onBlur={(e) => updateNode(selected.id, { title: e.target.value })}
              className="w-full bg-transparent text-2xl font-semibold focus:outline-none"
            />
            <TipTapEditor
              value={selected.body_md ?? ""}
              onChange={onSaveBody}
              placeholder="Write this section..."
            />

            <section>
              <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-neutral-500">
                Evidence ({selectedEvidence.length})
              </h3>
              <ul className="space-y-2">
                {selectedEvidence.map((c) => (
                  <li
                    key={c.id}
                    className="rounded border border-neutral-200 bg-white p-3 text-sm dark:border-neutral-800 dark:bg-neutral-950"
                  >
                    <blockquote className="border-l-2 border-neutral-300 pl-3 italic text-neutral-700 dark:text-neutral-300">
                      {c.quote_text}
                    </blockquote>
                    <div className="mt-2 flex items-center justify-between text-xs">
                      <Link
                        href={`/library/${c.source_id}?chunk=${c.chunk_id ?? ""}${
                          (c.citation.page_start as number | null)
                            ? `&page=${c.citation.page_start}`
                            : ""
                        }`}
                        className="text-blue-600 hover:underline"
                      >
                        {(c.citation.source_title as string) || "Source"}
                        {Array.isArray(c.citation.chapter_path) &&
                        (c.citation.chapter_path as string[]).length > 0
                          ? ` · ${(c.citation.chapter_path as string[]).join(" > ")}`
                          : ""}
                        {c.citation.page_start ? ` · p. ${c.citation.page_start}` : ""}
                      </Link>
                      <button
                        onClick={() => onDeleteEvidence(c.id)}
                        className="text-red-600 hover:underline"
                      >
                        remove
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            </section>

            <EvidenceFinder onAdd={onAddEvidence} />
          </div>
        ) : (
          <div className="text-sm text-neutral-500">
            Select or create a section on the left to start writing.
          </div>
        )}
      </div>
    </div>
  );
}

function buildTree(rows: OutlineNode[]): OutlineTreeNode[] {
  const byId = new Map<number, OutlineTreeNode>();
  rows.forEach((r) => byId.set(r.id, { ...r, children: [] }));
  const roots: OutlineTreeNode[] = [];
  byId.forEach((n) => {
    if (n.parent_id && byId.has(n.parent_id)) {
      byId.get(n.parent_id)!.children.push(n);
    } else {
      roots.push(n);
    }
  });
  const sortRec = (list: OutlineTreeNode[]) => {
    list.sort((a, b) => a.order_in_parent - b.order_in_parent || a.id - b.id);
    list.forEach((n) => sortRec(n.children));
  };
  sortRec(roots);
  return roots;
}

function OutlineItem({
  node,
  selectedId,
  onSelect,
  onAddChild,
  onDelete,
  depth = 0,
}: {
  node: OutlineTreeNode;
  selectedId: number | null;
  onSelect: (id: number) => void;
  onAddChild: (parentId: number | null) => void;
  onDelete: (id: number) => void;
  depth?: number;
}) {
  const isSel = selectedId === node.id;
  return (
    <li>
      <div
        className={`group flex items-center gap-1 rounded px-1 py-0.5 ${
          isSel ? "bg-blue-100 dark:bg-blue-900/40" : "hover:bg-neutral-200 dark:hover:bg-neutral-800"
        }`}
        style={{ paddingLeft: `${4 + depth * 12}px` }}
      >
        <button
          onClick={() => onSelect(node.id)}
          className="flex-1 truncate text-left"
          title={node.title}
        >
          {node.title}
        </button>
        <button
          onClick={() => onAddChild(node.id)}
          className="hidden text-xs text-neutral-500 hover:text-blue-600 group-hover:inline"
          title="Add subsection"
        >
          +
        </button>
        <button
          onClick={() => onDelete(node.id)}
          className="hidden text-xs text-neutral-500 hover:text-red-600 group-hover:inline"
          title="Delete"
        >
          ×
        </button>
      </div>
      {node.children.length > 0 && (
        <ul>
          {node.children.map((c) => (
            <OutlineItem
              key={c.id}
              node={c}
              selectedId={selectedId}
              onSelect={onSelect}
              onAddChild={onAddChild}
              onDelete={onDelete}
              depth={depth + 1}
            />
          ))}
        </ul>
      )}
    </li>
  );
}

function EvidenceFinder({ onAdd }: { onAdd: (hit: SearchHit) => void }) {
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<SearchHit[]>([]);
  const [searching, setSearching] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const search = useCallback(async () => {
    if (!q.trim() || searching) return;
    setSearching(true);
    setErr(null);
    try {
      const res = await api<{ hits: SearchHit[] }>("/api/v1/search", {
        method: "POST",
        body: JSON.stringify({ query: q, mode: "hybrid", k: 10 }),
      });
      setHits(res.hits);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setSearching(false);
    }
  }, [q, searching]);

  return (
    <section className="border-t border-neutral-200 pt-4 dark:border-neutral-800">
      <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-neutral-500">
        Find evidence
      </h3>
      <div className="flex gap-2">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && search()}
          placeholder="Search your library..."
          className="flex-1 rounded border border-neutral-300 px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-900"
        />
        <button
          onClick={search}
          disabled={searching || !q.trim()}
          className="rounded bg-neutral-800 px-3 py-1 text-sm text-white hover:bg-neutral-900 disabled:opacity-50 dark:bg-neutral-200 dark:text-neutral-900"
        >
          {searching ? "..." : "Search"}
        </button>
      </div>
      {err && <div className="mt-2 text-xs text-red-700">{err}</div>}
      <ul className="mt-3 space-y-2">
        {hits.map((h) => (
          <li
            key={`${h.chunk_id}`}
            className="rounded border border-neutral-200 bg-white p-2 text-xs dark:border-neutral-800 dark:bg-neutral-950"
          >
            <div className="mb-1 flex items-center justify-between">
              <span className="font-medium">{h.source_title}</span>
              <span className="text-neutral-500">
                {h.page_start ? `p. ${h.page_start}` : ""}
              </span>
            </div>
            {h.chapter_path.length > 0 && (
              <div className="text-neutral-500">{h.chapter_path.join(" > ")}</div>
            )}
            <div className="mt-1 line-clamp-3 text-neutral-700 dark:text-neutral-300">
              {h.text}
            </div>
            <button
              onClick={() => onAdd(h)}
              className="mt-2 rounded bg-blue-600 px-2 py-0.5 text-xs font-medium text-white hover:bg-blue-700"
            >
              + Pin to section
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
