"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import type { CoverageOut, Project } from "@/lib/types";

export default function CoveragePage({ params }: { params: { id: string } }) {
  const projectId = Number(params.id);
  const [project, setProject] = useState<Project | null>(null);
  const [data, setData] = useState<CoverageOut | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const [p, c] = await Promise.all([
          api<Project>(`/api/v1/projects/${projectId}`),
          api<CoverageOut>(`/api/v1/projects/${projectId}/coverage`),
        ]);
        setProject(p);
        setData(c);
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      }
    })();
  }, [projectId]);

  if (error)
    return <div className="p-6 text-sm text-red-700">{error}</div>;
  if (!project || !data)
    return <div className="p-6 text-sm text-neutral-500">Loading…</div>;

  const max = Math.max(1, ...data.matrix.flat());

  return (
    <div className="p-6">
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-xl font-semibold">{project.title} — coverage map</h1>
        <Link
          href={`/projects/${projectId}`}
          className="text-sm text-blue-600 hover:underline"
        >
          ← back to project
        </Link>
      </div>
      <p className="mb-4 text-sm text-neutral-600 dark:text-neutral-400">
        Rows = sections; columns = sources. Cells show how many evidence items
        from that source are pinned to that section. Empty rows are{" "}
        <span className="font-medium text-amber-700 dark:text-amber-400">gaps</span>.
      </p>

      {data.nodes.length === 0 ? (
        <div className="text-sm text-neutral-500">No sections in this project.</div>
      ) : data.sources.length === 0 ? (
        <div className="text-sm text-amber-700">
          No evidence pinned to any section yet.
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="text-xs">
            <thead>
              <tr>
                <th className="sticky left-0 z-10 bg-white px-2 py-1 text-left dark:bg-neutral-950">
                  Section
                </th>
                {data.sources.map((s) => (
                  <th
                    key={s.source_id}
                    className="px-1 py-1 text-left align-bottom"
                    style={{ minWidth: 40 }}
                  >
                    <div
                      className="origin-bottom-left -rotate-45 whitespace-nowrap"
                      title={s.title}
                    >
                      {s.title.length > 24 ? s.title.slice(0, 24) + "…" : s.title}
                    </div>
                  </th>
                ))}
                <th className="px-2 py-1 text-left">Total</th>
              </tr>
            </thead>
            <tbody>
              {data.nodes.map((n, ri) => {
                const total = data.matrix[ri].reduce((a, b) => a + b, 0);
                const isGap = total === 0;
                return (
                  <tr
                    key={n.node_id}
                    className={
                      isGap ? "bg-amber-50 dark:bg-amber-900/20" : ""
                    }
                  >
                    <td
                      className="sticky left-0 z-10 truncate bg-white px-2 py-1 dark:bg-neutral-950"
                      style={{
                        paddingLeft: `${8 + n.depth * 12}px`,
                        maxWidth: 280,
                      }}
                    >
                      {n.title}
                    </td>
                    {data.matrix[ri].map((v, ci) => (
                      <td
                        key={ci}
                        className="px-1 py-1"
                        style={{
                          backgroundColor: v === 0
                            ? undefined
                            : `rgba(37, 99, 235, ${0.15 + 0.6 * (v / max)})`,
                          color: v === 0
                            ? undefined
                            : v / max > 0.6 ? "white" : undefined,
                          textAlign: "center",
                        }}
                        title={
                          v > 0
                            ? `${v} evidence item(s) from "${data.sources[ci].title}"`
                            : undefined
                        }
                      >
                        {v || ""}
                      </td>
                    ))}
                    <td className="px-2 py-1 font-medium">{total}</td>
                  </tr>
                );
              })}
              <tr className="border-t border-neutral-200 dark:border-neutral-800">
                <td className="sticky left-0 z-10 bg-white px-2 py-1 font-medium dark:bg-neutral-950">
                  Total per source
                </td>
                {data.sources.map((s) => (
                  <td
                    key={s.source_id}
                    className="px-1 py-1 text-center font-medium"
                  >
                    {s.evidence_count}
                  </td>
                ))}
                <td />
              </tr>
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
