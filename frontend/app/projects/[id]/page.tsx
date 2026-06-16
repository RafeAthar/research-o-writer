"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { api, downloadAuthFile } from "@/lib/api";
import type {
  ContradictionOut,
  EvidenceCard,
  FlagSentencesOut,
  FlaggedSentence,
  OutlineNode,
  OutlineNodeVersion,
  Project,
  SearchHit,
  SectionPassOut,
  Verdict,
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
        <div className="mb-2 flex gap-1">
          <button
            onClick={() =>
              downloadAuthFile(
                `/api/v1/projects/${projectId}/export.md`,
                `${project.title}.md`,
              ).catch((e) => setError(e instanceof Error ? e.message : String(e)))
            }
            className="flex-1 rounded border border-neutral-300 px-2 py-1 text-xs hover:bg-neutral-200 dark:border-neutral-700 dark:hover:bg-neutral-800"
          >
            .md
          </button>
          <button
            onClick={() =>
              downloadAuthFile(
                `/api/v1/projects/${projectId}/export.docx?csl=chicago`,
                `${project.title}.docx`,
              ).catch((e) => setError(e instanceof Error ? e.message : String(e)))
            }
            className="flex-1 rounded border border-neutral-300 px-2 py-1 text-xs hover:bg-neutral-200 dark:border-neutral-700 dark:hover:bg-neutral-800"
            title="Chicago author-date"
          >
            .docx Chicago
          </button>
          <button
            onClick={() =>
              downloadAuthFile(
                `/api/v1/projects/${projectId}/export.docx?csl=apa`,
                `${project.title}.docx`,
              ).catch((e) => setError(e instanceof Error ? e.message : String(e)))
            }
            className="flex-1 rounded border border-neutral-300 px-2 py-1 text-xs hover:bg-neutral-200 dark:border-neutral-700 dark:hover:bg-neutral-800"
            title="APA 7th"
          >
            .docx APA
          </button>
        </div>
        <Link
          href={`/projects/${projectId}/sources`}
          className="mb-1 block w-full rounded border border-neutral-300 px-2 py-1 text-center text-xs hover:bg-neutral-200 dark:border-neutral-700 dark:hover:bg-neutral-800"
        >
          Sources
        </Link>
        <Link
          href={`/projects/${projectId}/coverage`}
          className="mb-1 block w-full rounded border border-neutral-300 px-2 py-1 text-center text-xs hover:bg-neutral-200 dark:border-neutral-700 dark:hover:bg-neutral-800"
        >
          Coverage map
        </Link>
        <Link
          href={`/projects/${projectId}/style`}
          className="mb-3 block w-full rounded border border-neutral-300 px-2 py-1 text-center text-xs hover:bg-neutral-200 dark:border-neutral-700 dark:hover:bg-neutral-800"
        >
          Style memory
        </Link>
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
              evidence={selectedEvidence}
            />
            <DraftView
              projectId={projectId}
              nodeId={selected.id}
              html={selected.body_md ?? ""}
            />
            <SectionActions projectId={projectId} nodeId={selected.id} />
            <ContradictionsPanel
              projectId={projectId}
              nodeId={selected.id}
              evidence={selectedEvidence}
            />
            <VersionsPanel
              projectId={projectId}
              nodeId={selected.id}
              onRestored={async () => {
                await reloadAll();
              }}
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

function htmlToText(html: string): string {
  if (typeof document === "undefined") return html;
  const tmp = document.createElement("div");
  tmp.innerHTML = html;
  return tmp.innerText || tmp.textContent || "";
}

function DraftView({
  projectId,
  nodeId,
  html,
}: {
  projectId: number;
  nodeId: number;
  html: string;
}) {
  const [result, setResult] = useState<FlaggedSentence[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const text = useMemo(() => htmlToText(html), [html]);

  const check = useCallback(async () => {
    if (!text.trim() || busy) return;
    setBusy(true);
    setErr(null);
    try {
      const res = await api<FlagSentencesOut>(
        `/api/v1/projects/${projectId}/nodes/${nodeId}/flag-sentences`,
        {
          method: "POST",
          body: JSON.stringify({ text }),
        },
      );
      setResult(res.sentences);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }, [projectId, nodeId, text, busy]);

  const unsupported = result?.filter((s) => !s.supported) ?? [];

  return (
    <section className="rounded border border-neutral-200 p-3 dark:border-neutral-800">
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-neutral-500">
          Draft check
        </h3>
        <button
          onClick={check}
          disabled={busy || !text.trim()}
          className="rounded bg-neutral-800 px-3 py-1 text-xs text-white hover:bg-neutral-900 disabled:opacity-50 dark:bg-neutral-200 dark:text-neutral-900"
        >
          {busy ? "Checking..." : "Check unsupported sentences"}
        </button>
      </div>
      {err && <div className="mb-2 text-xs text-red-700">{err}</div>}
      {result && (
        <>
          <div className="mb-2 text-xs text-neutral-500">
            {unsupported.length} of {result.length} sentence(s) flagged.
            Heuristic match against pinned evidence quotes — not a model judgement.
          </div>
          <div className="space-y-1 text-sm leading-relaxed">
            {result.map((s, i) => (
              <span
                key={i}
                className={
                  s.supported
                    ? ""
                    : "rounded bg-red-100 px-0.5 text-red-900 dark:bg-red-900/30 dark:text-red-100"
                }
                title={
                  s.supported
                    ? `matched evidence: ${s.matched_evidence_ids.join(", ") || "—"}`
                    : "no overlap with pinned evidence on this section"
                }
              >
                {s.sentence}{" "}
              </span>
            ))}
          </div>
        </>
      )}
    </section>
  );
}

function VersionsPanel({
  projectId,
  nodeId,
  onRestored,
}: {
  projectId: number;
  nodeId: number;
  onRestored: () => Promise<void>;
}) {
  const [versions, setVersions] = useState<OutlineNodeVersion[]>([]);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [diffPair, setDiffPair] = useState<[number, number] | null>(null);
  const [vCache, setVCache] = useState<Record<number, OutlineNodeVersion>>({});

  const reload = useCallback(async () => {
    try {
      const rows = await api<OutlineNodeVersion[]>(
        `/api/v1/projects/${projectId}/nodes/${nodeId}/versions`,
      );
      setVersions(rows);
      setVCache(Object.fromEntries(rows.map((v) => [v.id, v])));
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }, [projectId, nodeId]);

  useEffect(() => {
    if (open) reload();
  }, [open, reload]);

  useEffect(() => {
    setOpen(false);
    setDiffPair(null);
  }, [nodeId]);

  const snapshot = useCallback(async () => {
    if (busy) return;
    setBusy(true);
    setErr(null);
    try {
      const label = prompt("Optional label for this snapshot:") || null;
      await api<OutlineNodeVersion>(
        `/api/v1/projects/${projectId}/nodes/${nodeId}/versions`,
        { method: "POST", body: JSON.stringify({ label }) },
      );
      await reload();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }, [projectId, nodeId, busy, reload]);

  const restore = useCallback(
    async (vid: number) => {
      if (!confirm("Restore this version? Current content will be snapshotted first.")) return;
      try {
        await api<unknown>(
          `/api/v1/projects/${projectId}/nodes/${nodeId}/versions/${vid}/restore`,
          { method: "POST" },
        );
        await onRestored();
        await reload();
      } catch (e) {
        setErr(e instanceof Error ? e.message : String(e));
      }
    },
    [projectId, nodeId, onRestored, reload],
  );

  return (
    <section className="rounded border border-neutral-200 p-3 dark:border-neutral-800">
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-neutral-500">
          Version history
        </h3>
        <div className="flex gap-2">
          <button
            onClick={snapshot}
            disabled={busy}
            className="rounded border border-neutral-300 px-2 py-0.5 text-xs hover:bg-neutral-100 dark:border-neutral-700 dark:hover:bg-neutral-800"
          >
            Snapshot now
          </button>
          <button
            onClick={() => setOpen((v) => !v)}
            className="rounded border border-neutral-300 px-2 py-0.5 text-xs hover:bg-neutral-100 dark:border-neutral-700 dark:hover:bg-neutral-800"
          >
            {open ? "Hide" : "Show"}
          </button>
        </div>
      </div>
      {err && <div className="mb-2 text-xs text-red-700">{err}</div>}
      {open && (
        <ul className="space-y-1 text-xs">
          {versions.length === 0 && (
            <li className="text-neutral-500">No snapshots yet.</li>
          )}
          {versions.map((v, i) => (
            <li
              key={v.id}
              className="flex items-center justify-between rounded border border-neutral-200 px-2 py-1 dark:border-neutral-800"
            >
              <div className="min-w-0 flex-1 truncate">
                <span className="font-medium">v{versions.length - i}</span>{" "}
                <span className="text-neutral-500">
                  {new Date(v.created_at).toLocaleString()}
                </span>
                {v.label && (
                  <span className="ml-1 text-neutral-700 dark:text-neutral-300">
                    — {v.label}
                  </span>
                )}
              </div>
              <div className="flex gap-2 text-xs">
                {versions[i + 1] && (
                  <button
                    onClick={() =>
                      setDiffPair([versions[i + 1].id, v.id])
                    }
                    className="text-blue-600 hover:underline"
                  >
                    diff vs prev
                  </button>
                )}
                <button
                  onClick={() => restore(v.id)}
                  className="text-blue-600 hover:underline"
                >
                  restore
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
      {diffPair && (
        <DiffModal
          a={vCache[diffPair[0]]}
          b={vCache[diffPair[1]]}
          onClose={() => setDiffPair(null)}
        />
      )}
    </section>
  );
}

function DiffModal({
  a,
  b,
  onClose,
}: {
  a: OutlineNodeVersion | undefined;
  b: OutlineNodeVersion | undefined;
  onClose: () => void;
}) {
  if (!a || !b) return null;
  const lines = simpleLineDiff(htmlToText(a.body_md ?? ""), htmlToText(b.body_md ?? ""));
  return (
    <div className="fixed inset-0 z-30 flex items-center justify-center bg-black/40">
      <div className="max-h-[80vh] w-[min(900px,90vw)] overflow-y-auto rounded bg-white p-4 dark:bg-neutral-950">
        <div className="mb-2 flex items-center justify-between">
          <div className="text-sm font-semibold">
            Diff: {new Date(a.created_at).toLocaleString()} →{" "}
            {new Date(b.created_at).toLocaleString()}
          </div>
          <button
            onClick={onClose}
            className="rounded border border-neutral-300 px-2 py-0.5 text-xs hover:bg-neutral-100 dark:border-neutral-700 dark:hover:bg-neutral-800"
          >
            Close
          </button>
        </div>
        <pre className="whitespace-pre-wrap rounded bg-neutral-50 p-3 font-mono text-xs leading-5 dark:bg-neutral-900">
          {lines.map((l, i) => {
            const cls =
              l.kind === "+"
                ? "bg-green-100 dark:bg-green-900/30"
                : l.kind === "-"
                ? "bg-red-100 dark:bg-red-900/30"
                : "";
            return (
              <div key={i} className={cls}>
                <span className="mr-2 select-none text-neutral-400">
                  {l.kind === " " ? " " : l.kind}
                </span>
                {l.text}
              </div>
            );
          })}
        </pre>
      </div>
    </div>
  );
}

function simpleLineDiff(
  a: string,
  b: string,
): { kind: "+" | "-" | " "; text: string }[] {
  const A = a.split(/\n/);
  const B = b.split(/\n/);
  // LCS-based line diff. n,m small for our case.
  const n = A.length;
  const m = B.length;
  const dp: number[][] = Array.from({ length: n + 1 }, () => new Array(m + 1).fill(0));
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      dp[i][j] = A[i] === B[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
    }
  }
  const out: { kind: "+" | "-" | " "; text: string }[] = [];
  let i = 0;
  let j = 0;
  while (i < n && j < m) {
    if (A[i] === B[j]) {
      out.push({ kind: " ", text: A[i] });
      i++;
      j++;
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      out.push({ kind: "-", text: A[i] });
      i++;
    } else {
      out.push({ kind: "+", text: B[j] });
      j++;
    }
  }
  while (i < n) out.push({ kind: "-", text: A[i++] });
  while (j < m) out.push({ kind: "+", text: B[j++] });
  return out;
}

function SectionActions({
  projectId,
  nodeId,
}: {
  projectId: number;
  nodeId: number;
}) {
  const [busy, setBusy] = useState<null | "steel" | "miss">(null);
  const [out, setOut] = useState<{ kind: string; result: SectionPassOut } | null>(null);

  const run = async (kind: "steel" | "miss") => {
    setBusy(kind);
    setOut(null);
    try {
      const path = kind === "steel" ? "steel-man" : "whats-missing";
      const res = await api<SectionPassOut>(
        `/api/v1/projects/${projectId}/nodes/${nodeId}/${path}`,
        { method: "POST" },
      );
      setOut({ kind, result: res });
    } catch (e) {
      setOut({
        kind,
        result: {
          result_md: "",
          model: null,
          error: e instanceof Error ? e.message : String(e),
        },
      });
    } finally {
      setBusy(null);
    }
  };

  return (
    <section className="rounded border border-neutral-200 p-3 dark:border-neutral-800">
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-neutral-500">
          Section passes
        </h3>
        <div className="flex gap-2">
          <button
            onClick={() => run("steel")}
            disabled={!!busy}
            className="rounded border border-neutral-300 px-2 py-0.5 text-xs hover:bg-neutral-100 disabled:opacity-50 dark:border-neutral-700 dark:hover:bg-neutral-800"
          >
            {busy === "steel" ? "Working…" : "Steel-man"}
          </button>
          <button
            onClick={() => run("miss")}
            disabled={!!busy}
            className="rounded border border-neutral-300 px-2 py-0.5 text-xs hover:bg-neutral-100 disabled:opacity-50 dark:border-neutral-700 dark:hover:bg-neutral-800"
          >
            {busy === "miss" ? "Working…" : "What's missing"}
          </button>
        </div>
      </div>
      {out && (
        <div className="rounded bg-neutral-50 p-3 text-sm dark:bg-neutral-900">
          {out.result.error ? (
            <div className="text-red-700">{out.result.error}</div>
          ) : (
            <pre className="whitespace-pre-wrap font-sans">
              {out.result.result_md}
            </pre>
          )}
        </div>
      )}
    </section>
  );
}

function ContradictionsPanel({
  projectId,
  nodeId,
  evidence,
}: {
  projectId: number;
  nodeId: number;
  evidence: EvidenceCard[];
}) {
  const [busy, setBusy] = useState(false);
  const [verdicts, setVerdicts] = useState<Verdict[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const byId = useMemo(() => {
    const m: Record<number, EvidenceCard> = {};
    evidence.forEach((e) => (m[e.id] = e));
    return m;
  }, [evidence]);

  const run = async () => {
    if (busy || evidence.length < 2) return;
    setBusy(true);
    setErr(null);
    try {
      const res = await api<ContradictionOut>(
        `/api/v1/projects/${projectId}/nodes/${nodeId}/contradictions`,
        {
          method: "POST",
          body: JSON.stringify({
            evidence_ids: evidence.map((e) => e.id),
          }),
        },
      );
      if (res.error) setErr(res.error);
      setVerdicts(res.verdicts);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const colorFor = (v: string) =>
    v === "agree"
      ? "bg-green-100 text-green-900 dark:bg-green-900/30 dark:text-green-100"
      : v === "disagree"
      ? "bg-red-100 text-red-900 dark:bg-red-900/30 dark:text-red-100"
      : v === "unclear"
      ? "bg-amber-100 text-amber-900 dark:bg-amber-900/30 dark:text-amber-100"
      : "bg-neutral-100 text-neutral-700 dark:bg-neutral-800 dark:text-neutral-300";

  return (
    <section className="rounded border border-neutral-200 p-3 dark:border-neutral-800">
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-neutral-500">
          Cross-evidence check
        </h3>
        <button
          onClick={run}
          disabled={busy || evidence.length < 2}
          className="rounded bg-neutral-800 px-3 py-1 text-xs text-white hover:bg-neutral-900 disabled:opacity-50 dark:bg-neutral-200 dark:text-neutral-900"
          title={
            evidence.length < 2
              ? "Pin at least two pieces of evidence first"
              : "Compare all pinned evidence pairwise"
          }
        >
          {busy ? "Comparing…" : "Compare evidence"}
        </button>
      </div>
      {err && <div className="mb-2 text-xs text-red-700">{err}</div>}
      {verdicts && verdicts.length === 0 && (
        <div className="text-xs text-neutral-500">No verdicts returned.</div>
      )}
      {verdicts && verdicts.length > 0 && (
        <ul className="space-y-1 text-xs">
          {verdicts.map((v, i) => {
            const a = byId[v.pair[0]];
            const b = byId[v.pair[1]];
            return (
              <li
                key={i}
                className="rounded border border-neutral-200 p-2 dark:border-neutral-800"
              >
                <div className="flex items-center gap-2">
                  <span
                    className={`rounded px-1.5 py-0.5 font-medium uppercase ${colorFor(v.verdict)}`}
                  >
                    {v.verdict}
                  </span>
                  <span className="truncate text-neutral-500">
                    {a ? (a.citation.source_title as string) : `#${v.pair[0]}`} ↔{" "}
                    {b ? (b.citation.source_title as string) : `#${v.pair[1]}`}
                  </span>
                </div>
                {v.rationale && (
                  <div className="mt-1 text-neutral-700 dark:text-neutral-300">
                    {v.rationale}
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </section>
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
