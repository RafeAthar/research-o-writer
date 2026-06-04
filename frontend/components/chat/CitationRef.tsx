"use client";

import Link from "next/link";
import { useState } from "react";

import type { ChatCitation, ChatPassage } from "@/lib/types";

interface Props {
  n: number;
  source: ChatCitation | ChatPassage | null;
}

/** Inline `[Pn]` chip with hover popover preview and click-to-jump. */
export function CitationRef({ n, source }: Props) {
  const [hover, setHover] = useState(false);

  if (!source) {
    return (
      <span className="font-mono text-xs text-neutral-500">[P{n}]</span>
    );
  }

  const href =
    `/library/${source.source_id}?chunk=${source.chunk_id}` +
    (source.page_start ? `&page=${source.page_start}` : "");

  const pageStr =
    source.page_start && source.page_end && source.page_end !== source.page_start
      ? `pp. ${source.page_start}-${source.page_end}`
      : source.page_start
        ? `p. ${source.page_start}`
        : "";

  return (
    <span
      className="relative inline-block"
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
    >
      <Link
        href={href}
        className="rounded bg-blue-100 px-1 py-0.5 font-mono text-[10px] font-medium text-blue-800 no-underline hover:bg-blue-200 dark:bg-blue-900/40 dark:text-blue-300 dark:hover:bg-blue-900/60"
      >
        P{n}
      </Link>
      {hover && (
        <span
          className="pointer-events-none absolute bottom-full left-1/2 z-20 mb-1 w-80 -translate-x-1/2 rounded border border-neutral-200 bg-white p-2 text-xs shadow-lg dark:border-neutral-700 dark:bg-neutral-900"
          role="tooltip"
        >
          <span className="block font-medium">{source.source_title}</span>
          {source.chapter_path.length > 0 && (
            <span className="block text-neutral-500">
              {source.chapter_path.join(" > ")}
            </span>
          )}
          {pageStr && <span className="block text-neutral-500">{pageStr}</span>}
          <span className="mt-1 line-clamp-4 block text-neutral-700 dark:text-neutral-300">
            {source.preview}
          </span>
        </span>
      )}
    </span>
  );
}
