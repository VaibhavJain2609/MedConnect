/**
 * Uploads API — two-step file upload flow.
 *
 * 1. requestUpload(fileName, contentType) → POST /api/v1/uploads/presign
 *    returns { presigned_url, object_key, method, expires_in }
 * 2. uploadBytes(objectKey, file) → PUT /api/v1/uploads/{object_key}
 *    with the raw file body (local storage backend).
 *
 * Allowed content types (enforced server-side): image/jpeg, image/png,
 * application/pdf. Allowed extensions: .jpg .jpeg .png .pdf
 */
import api from "@/lib/api";

export const UPLOAD_ACCEPTED_TYPES = ["image/jpeg", "image/png", "application/pdf"];
export const UPLOAD_ACCEPTED_EXT = ".jpg,.jpeg,.png,.pdf";

export interface PresignResponse {
  presigned_url: string;
  object_key: string;
  method: string;
  expires_in: number;
}

/** Step 1 — ask the backend for an upload slot. */
export async function requestUpload(
  fileName: string,
  contentType: string
): Promise<PresignResponse> {
  const res = await api.post<PresignResponse>("/api/v1/uploads/presign", {
    file_name: fileName,
    content_type: contentType,
  });
  return res.data;
}

/**
 * Step 2 — PUT the raw bytes to the issued object key.
 *
 * Uses the shared axios instance so the Bearer token is attached (the local
 * PUT endpoint requires auth and verifies the key was issued to this user).
 * For an S3 storage backend the presign response returns a remote
 * presigned_url instead — pass that as `presignedUrl` and it will be used
 * via XHR without auth headers.
 */
export async function uploadBytes(
  objectKey: string,
  file: File | Blob,
  onProgress?: (percent: number) => void,
  presignedUrl?: string
): Promise<void> {
  const contentType = file.type || "application/octet-stream";

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  const isRemotePresign =
    !!presignedUrl &&
    /^https?:\/\//.test(presignedUrl) &&
    !presignedUrl.startsWith(apiUrl);

  if (isRemotePresign) {
    // S3-style presigned URL — no app auth headers.
    await new Promise<void>((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open("PUT", presignedUrl as string);
      xhr.setRequestHeader("Content-Type", contentType);
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable && onProgress) {
          onProgress(Math.round((e.loaded * 100) / e.total));
        }
      };
      xhr.onload = () =>
        xhr.status >= 200 && xhr.status < 300
          ? resolve()
          : reject(new Error(`Upload failed (${xhr.status})`));
      xhr.onerror = () => reject(new Error("Network error during upload"));
      xhr.send(file);
    });
    return;
  }

  await api.put(`/api/v1/uploads/${objectKey}`, file, {
    headers: { "Content-Type": contentType },
    onUploadProgress: (e) => {
      if (e.total && onProgress) {
        onProgress(Math.round((e.loaded * 100) / e.total));
      }
    },
  });
}

/**
 * Convenience helper: presign + PUT in one call.
 * Returns the object_key to store on the owning resource
 * (e.g. doctor.license_document_url, record.document_url).
 */
export async function uploadFile(
  file: File,
  onProgress?: (percent: number) => void
): Promise<string> {
  const { presigned_url, object_key } = await requestUpload(file.name, file.type);
  await uploadBytes(object_key, file, onProgress, presigned_url);
  return object_key;
}
