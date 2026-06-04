import type { ChatCitation, ChatMessage } from "./types";

interface ExportableChat {
  title: string;
  scope: string;
  source_ids: number[];
  created_at?: string;
}

/** Render a chat thread as Pandoc-friendly Markdown with citation footnotes. */
export function chatThreadToMarkdown(
  chat: ExportableChat,
  messages: ChatMessage[],
): string {
  const lines: string[] = [];
  lines.push(`# ${chat.title}`, "");
  lines.push(`> Scope: ${chat.scope} · ${chat.source_ids.length} source(s)`, "");

  const allCites: ChatCitation[] = [];
  const citeIndex = new Map<string, number>(); // dedupe key -> footnote number

  for (const m of messages) {
    if (m.role === "user") {
      lines.push(`### You`, "");
      lines.push(m.content, "");
    } else {
      lines.push(`### Assistant`, "");
      // Rewrite inline [Pn] to footnote refs, building footnote pool.
      const rewritten = m.content.replace(/\[P(\d+)\]/g, (_, nStr) => {
        const n = Number(nStr);
        const c = m.citations.find((x) => x.passage === n);
        if (!c) return `[P${n}]`;
        const key = `${c.chunk_id}`;
        let foot = citeIndex.get(key);
        if (foot == null) {
          allCites.push(c);
          foot = allCites.length;
          citeIndex.set(key, foot);
        }
        return `[^${foot}]`;
      });
      lines.push(rewritten, "");
    }
  }

  if (allCites.length > 0) {
    lines.push("---", "", "## Sources", "");
    allCites.forEach((c, i) => {
      const page =
        c.page_start && c.page_end && c.page_end !== c.page_start
          ? `pp. ${c.page_start}-${c.page_end}`
          : c.page_start
            ? `p. ${c.page_start}`
            : "";
      const chapter =
        c.chapter_path.length > 0 ? ` — ${c.chapter_path.join(" > ")}` : "";
      lines.push(
        `[^${i + 1}]: *${c.source_title}*${chapter}${page ? `, ${page}` : ""}`,
      );
    });
  }

  return lines.join("\n");
}

export function downloadText(filename: string, text: string): void {
  const blob = new Blob([text], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
