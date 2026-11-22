// ============================================================
// Hachi Web App — file attachment domain (Phase 4, Initiative E)
// Wires: POST /files, GET /files, GET /files/{id}, GET /files/{id}/content
// ============================================================

import { API_BASE, USE_MOCKS, apiGet, authHeaders } from "../client";
import type { PendingAttachment } from "../types";

export interface GatewayFileMeta {
  file_id: string;
  name: string;
  media_type: string;
  size: number;
  status: string;
  created_at: string;
  extracted_text_ref?: string | null;
}

/**
 * Upload a single File to the gateway. Returns the server-assigned file_id.
 *
 * @param file        - The File object to upload.
 * @param knownType   - MIME type already determined client-side (e.g. from
 *                      makeOptimisticAttachment). Passed as ?media_type= so
 *                      the server does not have to rely solely on the
 *                      multipart Content-Type header, which some browsers omit
 *                      for uncommon formats (HEIC, AVIF, BMP, etc.).
 */
export async function uploadFile(file: File, knownType?: string): Promise<string> {
  if (USE_MOCKS) {
    await new Promise((r) => setTimeout(r, 400));
    return "mock-" + Math.random().toString(36).slice(2);
  }

  const form = new FormData();
  form.append("file", file);

  // Prefer the caller-supplied type, then file.type, then guess from extension.
  const mediaType = knownType || file.type || guessMediaType(file.name);
  const url = mediaType
    ? `${API_BASE}/files?media_type=${encodeURIComponent(mediaType)}`
    : `${API_BASE}/files`;

  // authHeaders() injects the bearer token in direct mode; the Vite dev proxy
  // injects it server-side so no extra header is needed in dev.
  // Do NOT set Content-Type — the browser sets multipart/form-data + boundary.
  const res = await fetch(url, {
    method: "POST",
    body: form,
    headers: authHeaders() as HeadersInit,
  });

  if (!res.ok) {
    const detail = await res.text().catch(() => res.statusText);
    throw new Error(`Upload failed (${res.status}): ${detail}`);
  }

  const data = (await res.json()) as { file_id?: string };
  const fileId = data.file_id ?? "";
  if (!fileId) throw new Error("Server returned no file_id");
  return fileId;
}

/** List all stored file metadata records. */
export async function listFiles(): Promise<GatewayFileMeta[]> {
  if (USE_MOCKS) return [];
  try {
    const raw = await apiGet<GatewayFileMeta[] | { files?: GatewayFileMeta[] }>("/files");
    if (Array.isArray(raw)) return raw;
    if (raw && Array.isArray(raw.files)) return raw.files;
    return [];
  } catch {
    return [];
  }
}

/** Fetch metadata for one file id. */
export async function getFileMeta(fileId: string): Promise<GatewayFileMeta | null> {
  if (USE_MOCKS) return null;
  try {
    return await apiGet<GatewayFileMeta>(`/files/${encodeURIComponent(fileId)}`);
  } catch {
    // Fallback: some gateways can transiently race metadata replication.
    // A list query often succeeds immediately and includes the same record.
    const all = await listFiles();
    return all.find((f) => f.file_id === fileId) ?? null;
  }
}

/** Build raw content URL for a stored file id. */
export function fileContentUrl(fileId: string): string {
  return `${API_BASE}/files/${encodeURIComponent(fileId)}/content`;
}

/**
 * Open file content in a new browser tab using authenticated fetch.
 * This works in both proxied and direct-token modes.
 */
export async function openFileContent(fileId: string): Promise<boolean> {
  if (!fileId || fileId.startsWith("local-") || fileId.startsWith("mock-")) return false;
  if (USE_MOCKS) return false;
  try {
    const res = await fetch(fileContentUrl(fileId), {
      method: "GET",
      headers: authHeaders({ Accept: "*/*" }) as HeadersInit,
    });
    if (!res.ok) return false;
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    window.open(url, "_blank", "noopener,noreferrer");
    setTimeout(() => URL.revokeObjectURL(url), 60_000);
    return true;
  } catch {
    return false;
  }
}

/** Build an optimistic (pre-upload) PendingAttachment from a File object. */
export function makeOptimisticAttachment(file: File, localId: string): PendingAttachment {
  const mediaType = file.type || guessMediaType(file.name);
  const localUrl = mediaType.startsWith("image/") ? URL.createObjectURL(file) : undefined;
  return {
    fileId: localId,
    name: file.name,
    mediaType,
    size: file.size,
    localUrl,
    uploading: true,
  };
}

function guessMediaType(name: string): string {
  const ext = name.split(".").pop()?.toLowerCase() ?? "";
  const map: Record<string, string> = {
    // Raster images
    png: "image/png", jpg: "image/jpeg", jpeg: "image/jpeg",
    gif: "image/gif", webp: "image/webp", bmp: "image/bmp",
    tiff: "image/tiff", tif: "image/tiff", ico: "image/x-icon",
    avif: "image/avif", heic: "image/heic", heif: "image/heif",
    // Vector / other
    svg: "image/svg+xml",
    // Documents
    pdf: "application/pdf",
    // Plain text / data
    txt: "text/plain", md: "text/markdown", csv: "text/csv",
    json: "application/json", yaml: "application/yaml", yml: "application/yaml",
    toml: "application/toml",
    // Code
    ts: "text/x-typescript", tsx: "text/x-typescript",
    js: "text/x-javascript", jsx: "text/x-javascript",
    py: "text/x-python", go: "text/x-go", rs: "text/x-rust",
    java: "text/x-java-source", c: "text/x-c", cpp: "text/x-c++",
    sh: "text/x-shellscript", rb: "text/x-ruby", kt: "text/x-kotlin",
  };
  return map[ext] ?? "application/octet-stream";
}
