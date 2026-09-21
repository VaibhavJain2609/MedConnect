import api from "./api";

/**
 * Authenticated file download helpers.
 *
 * Plain `<a href>` links to API endpoints 401 because the Authorization
 * header is only attached by the axios interceptor. These helpers fetch
 * the file through `api` (with the Bearer token) and then hand the blob
 * to the browser.
 */

function filenameFromDisposition(header?: string): string | undefined {
  if (!header) return undefined;
  const match = /filename\*?=(?:UTF-8'')?"?([^";\n]+)/i.exec(header);
  return match ? decodeURIComponent(match[1].trim()) : undefined;
}

/** Save an already-in-memory `blob` as a file via a temporary anchor click. */
export function saveBlob(blob: Blob, filename: string): void {
  const blobUrl = window.URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = blobUrl;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  // Defer revocation so the browser has time to start the download
  setTimeout(() => window.URL.revokeObjectURL(blobUrl), 10_000);
}

/** Fetch `url` with auth and save it as a file. */
export async function downloadFile(url: string, filename?: string): Promise<void> {
  const response = await api.get(url, { responseType: "blob" });
  const resolvedName =
    filename ??
    filenameFromDisposition(response.headers?.["content-disposition"]) ??
    "download";

  saveBlob(response.data, resolvedName);
}

/** Fetch `url` with auth and open the resulting blob in a new tab (e.g. PDF preview). */
export async function openFileInNewTab(url: string): Promise<void> {
  const response = await api.get(url, { responseType: "blob" });
  const rawContentType = response.headers?.["content-type"];
  const contentType =
    typeof rawContentType === "string" ? rawContentType : "application/octet-stream";
  const blob =
    response.data instanceof Blob && response.data.type === contentType
      ? response.data
      : new Blob([response.data], { type: contentType });

  const blobUrl = window.URL.createObjectURL(blob);
  window.open(blobUrl, "_blank", "noopener,noreferrer");
  setTimeout(() => window.URL.revokeObjectURL(blobUrl), 60_000);
}
