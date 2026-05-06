import { API_BASE_URL, authHeaders } from "./api";

export interface SSEEvent {
  event: string;
  data: string;
}

/**
 * POST a JSON body to a streaming endpoint and yield parsed SSE events.
 * Browser EventSource is GET-only, so we hand-roll the parser.
 */
export async function* streamSSE(
  path: string,
  body: unknown,
  signal?: AbortSignal,
): AsyncGenerator<SSEEvent> {
  const headers = authHeaders({ "Content-Type": "application/json" });
  const res = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok || !res.body) {
    const text = await res.text().catch(() => "");
    throw new Error(`stream ${res.status}: ${text}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let idx: number;
    while ((idx = buf.indexOf("\n\n")) !== -1) {
      const raw = buf.slice(0, idx);
      buf = buf.slice(idx + 2);
      const ev = parseSSE(raw);
      if (ev) yield ev;
    }
  }
  if (buf.trim()) {
    const ev = parseSSE(buf);
    if (ev) yield ev;
  }
}

function parseSSE(raw: string): SSEEvent | null {
  let event = "message";
  const dataLines: string[] = [];
  for (const line of raw.split("\n")) {
    if (!line) continue;
    if (line.startsWith(":")) continue;
    const colon = line.indexOf(":");
    const field = colon === -1 ? line : line.slice(0, colon);
    const value =
      colon === -1
        ? ""
        : line.slice(colon + 1).startsWith(" ")
          ? line.slice(colon + 2)
          : line.slice(colon + 1);
    if (field === "event") event = value;
    else if (field === "data") dataLines.push(value);
  }
  if (dataLines.length === 0) return null;
  return { event, data: dataLines.join("\n") };
}
