export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
export const AUTH_TOKEN = process.env.NEXT_PUBLIC_AUTH_TOKEN ?? "";

export function authHeaders(extra: HeadersInit = {}): Headers {
  const headers = new Headers(extra);
  if (AUTH_TOKEN) headers.set("X-Auth-Token", AUTH_TOKEN);
  return headers;
}

export async function api<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const headers = authHeaders(init.headers);
  if (
    !headers.has("Content-Type") &&
    init.body &&
    !(init.body instanceof FormData)
  ) {
    headers.set("Content-Type", "application/json");
  }

  const res = await fetch(`${API_BASE_URL}${path}`, { ...init, headers });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${res.status} ${res.statusText}: ${text}`);
  }
  if (res.status === 204) return undefined as unknown as T;
  return (await res.json()) as T;
}

/**
 * Fetch a binary asset (PDF, etc.) with auth. Returns a blob URL the caller
 * must URL.revokeObjectURL when done.
 */
export async function fetchAuthBlobUrl(path: string): Promise<string> {
  const res = await fetch(`${API_BASE_URL}${path}`, { headers: authHeaders() });
  if (!res.ok) {
    throw new Error(`asset ${res.status}: ${await res.text().catch(() => "")}`);
  }
  const blob = await res.blob();
  return URL.createObjectURL(blob);
}

/**
 * Trigger a browser download of an authenticated GET endpoint. The browser's
 * own download UI does not let us inject headers, so fetch + blob + anchor.
 */
export async function downloadAuthFile(path: string, fallbackName: string): Promise<void> {
  const res = await fetch(`${API_BASE_URL}${path}`, { headers: authHeaders() });
  if (!res.ok) {
    throw new Error(`download ${res.status}: ${await res.text().catch(() => "")}`);
  }
  let filename = fallbackName;
  const cd = res.headers.get("Content-Disposition") ?? "";
  const m = /filename="?([^"]+)"?/i.exec(cd);
  if (m) filename = m[1];
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
