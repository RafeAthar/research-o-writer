"use client";

import { useEffect, useRef, useState } from "react";

interface Props {
  fileUrl: string;
  initialPage?: number;
  onPageChange?: (page: number) => void;
}

/**
 * Minimal PDF viewer using pdf.js. Renders one page at a time as a canvas with
 * a transparent text layer for selection. Worker is served from /public.
 */
export default function PdfViewer({ fileUrl, initialPage = 1, onPageChange }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [pageNum, setPageNum] = useState(initialPage);
  const [numPages, setNumPages] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [scale, setScale] = useState(1.25);
  const docRef = useRef<unknown>(null);

  // Load document.
  useEffect(() => {
    let cancelled = false;
    let loadingTask: { destroy: () => void } | null = null;
    (async () => {
      try {
        const pdfjs: typeof import("pdfjs-dist") = await import("pdfjs-dist");
        pdfjs.GlobalWorkerOptions.workerSrc = "/pdf.worker.min.mjs";
        loadingTask = pdfjs.getDocument(fileUrl) as unknown as { destroy: () => void };
        const doc = await (
          loadingTask as unknown as { promise: Promise<{ numPages: number }> }
        ).promise;
        if (cancelled) return;
        docRef.current = doc;
        setNumPages(doc.numPages);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => {
      cancelled = true;
      if (loadingTask) {
        try {
          loadingTask.destroy();
        } catch {
          // ignore
        }
      }
    };
  }, [fileUrl]);

  // Render current page.
  useEffect(() => {
    if (!docRef.current || !containerRef.current) return;
    let cancelled = false;
    (async () => {
      try {
        const doc = docRef.current as {
          getPage: (n: number) => Promise<{
            getViewport: (args: { scale: number }) => {
              width: number;
              height: number;
            };
            render: (args: {
              canvasContext: CanvasRenderingContext2D;
              viewport: unknown;
            }) => { promise: Promise<void> };
            getTextContent: () => Promise<{ items: Array<{ str: string }> }>;
          }>;
        };
        const page = await doc.getPage(pageNum);
        const viewport = page.getViewport({ scale });
        const container = containerRef.current!;
        container.innerHTML = "";

        const wrap = document.createElement("div");
        wrap.style.position = "relative";
        wrap.style.width = `${viewport.width}px`;
        wrap.style.height = `${viewport.height}px`;
        wrap.style.margin = "0 auto";
        wrap.style.boxShadow = "0 1px 3px rgba(0,0,0,0.2)";
        wrap.style.background = "white";

        const canvas = document.createElement("canvas");
        canvas.width = viewport.width;
        canvas.height = viewport.height;
        canvas.style.display = "block";
        wrap.appendChild(canvas);
        container.appendChild(wrap);

        const ctx = canvas.getContext("2d");
        if (!ctx) return;
        const renderTask = page.render({ canvasContext: ctx, viewport });
        await renderTask.promise;
        if (cancelled) return;

        // Lightweight text overlay so users can select text.
        const tc = await page.getTextContent();
        const overlay = document.createElement("div");
        overlay.style.position = "absolute";
        overlay.style.inset = "0";
        overlay.style.opacity = "0";
        overlay.style.userSelect = "text";
        overlay.style.color = "transparent";
        overlay.style.pointerEvents = "auto";
        overlay.style.whiteSpace = "pre-wrap";
        overlay.style.fontSize = "10px";
        overlay.textContent = tc.items.map((i) => i.str).join(" ");
        wrap.appendChild(overlay);

        if (onPageChange) onPageChange(pageNum);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [pageNum, scale, onPageChange]);

  if (error) {
    return (
      <div className="rounded border border-red-300 bg-red-50 p-3 text-sm text-red-700">
        {error}
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-neutral-200 bg-white px-3 py-1.5 text-sm dark:border-neutral-800 dark:bg-neutral-900">
        <div className="flex items-center gap-2">
          <button
            onClick={() => setPageNum((p) => Math.max(1, p - 1))}
            disabled={pageNum <= 1}
            className="rounded border border-neutral-300 px-2 py-0.5 disabled:opacity-40 dark:border-neutral-700"
          >
            Prev
          </button>
          <input
            type="number"
            value={pageNum}
            onChange={(e) => {
              const n = Number(e.target.value);
              if (!Number.isNaN(n) && n >= 1 && (!numPages || n <= numPages)) setPageNum(n);
            }}
            className="w-16 rounded border border-neutral-300 px-1 py-0.5 text-center dark:border-neutral-700 dark:bg-neutral-900"
          />
          <span className="text-neutral-500">/ {numPages ?? "?"}</span>
          <button
            onClick={() => setPageNum((p) => (numPages ? Math.min(numPages, p + 1) : p + 1))}
            disabled={!!numPages && pageNum >= numPages}
            className="rounded border border-neutral-300 px-2 py-0.5 disabled:opacity-40 dark:border-neutral-700"
          >
            Next
          </button>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setScale((s) => Math.max(0.5, +(s - 0.1).toFixed(2)))}
            className="rounded border border-neutral-300 px-2 py-0.5 dark:border-neutral-700"
          >
            −
          </button>
          <span className="w-12 text-center text-xs text-neutral-500">{Math.round(scale * 100)}%</span>
          <button
            onClick={() => setScale((s) => Math.min(3, +(s + 0.1).toFixed(2)))}
            className="rounded border border-neutral-300 px-2 py-0.5 dark:border-neutral-700"
          >
            +
          </button>
        </div>
      </div>
      <div ref={containerRef} className="flex-1 overflow-auto bg-neutral-100 p-4 dark:bg-neutral-950" />
    </div>
  );
}
