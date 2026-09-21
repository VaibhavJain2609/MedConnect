"use client";

import { useRef, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  FileText,
  Paperclip,
  RefreshCw,
  X,
} from "lucide-react";
import {
  uploadFile,
  UPLOAD_ACCEPTED_EXT,
  UPLOAD_ACCEPTED_TYPES,
} from "@/lib/api/uploads";

type UploadState =
  | { status: "idle" }
  | { status: "uploading"; fileName: string; progress: number }
  | { status: "done"; fileName: string; objectKey: string }
  | { status: "error"; message: string; file: File | null };

interface FileUploadProps {
  label?: string;
  hint?: string;
  /** Input accept attribute, e.g. ".pdf,.jpg,.jpeg,.png" */
  accept?: string;
  /** MIME types allowed client-side (also enforced server-side). */
  allowedTypes?: string[];
  /** Client-side size cap in MB. */
  maxSizeMb?: number;
  /** Pre-existing attachment — renders the "done" state. */
  initialFileName?: string | null;
  initialObjectKey?: string | null;
  /** Called with the object_key on success, or null when cleared/failed. */
  onUploaded?: (objectKey: string | null) => void;
  /** Called with true while an upload is in flight — lets the parent
   *  disable form submission until the upload settles. */
  onUploadingChange?: (uploading: boolean) => void;
}

function errorMessage(err: unknown): string {
  const e = err as { userMessage?: string; message?: string };
  return e?.userMessage || e?.message || "Upload failed. Please try again.";
}

export function FileUpload({
  label = "Attach Document",
  hint,
  accept = UPLOAD_ACCEPTED_EXT,
  allowedTypes = UPLOAD_ACCEPTED_TYPES,
  maxSizeMb = 10,
  initialFileName,
  initialObjectKey,
  onUploaded,
  onUploadingChange,
}: FileUploadProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [state, setState] = useState<UploadState>(
    initialObjectKey
      ? {
          status: "done",
          fileName: initialFileName || "Attached document",
          objectKey: initialObjectKey,
        }
      : { status: "idle" }
  );

  const startUpload = async (file: File) => {
    setState({ status: "uploading", fileName: file.name, progress: 0 });
    onUploadingChange?.(true);
    try {
      const objectKey = await uploadFile(file, (pct) => {
        setState((s) =>
          s.status === "uploading" ? { ...s, progress: pct } : s
        );
      });
      setState({ status: "done", fileName: file.name, objectKey });
      onUploaded?.(objectKey);
    } catch (err) {
      setState({ status: "error", message: errorMessage(err), file });
      onUploaded?.(null);
    } finally {
      onUploadingChange?.(false);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0] ?? null;
    // Reset input so picking the same file again re-triggers onChange.
    e.target.value = "";
    if (!selected) return;

    if (allowedTypes.length && !allowedTypes.includes(selected.type)) {
      setState({
        status: "error",
        message: "Only PDF, JPG, and PNG files are allowed.",
        file: null,
      });
      onUploaded?.(null);
      return;
    }
    if (selected.size > maxSizeMb * 1024 * 1024) {
      setState({
        status: "error",
        message: `File exceeds the ${maxSizeMb} MB limit.`,
        file: null,
      });
      onUploaded?.(null);
      return;
    }
    startUpload(selected);
  };

  const clear = () => {
    setState({ status: "idle" });
    onUploaded?.(null);
  };

  return (
    <div>
      {label && (
        <label className="mb-1 block text-sm font-medium text-dreams-textPrimary">
          {label}
          {hint && (
            <span className="ml-1 text-xs font-normal text-dreams-textSecondary">
              ({hint})
            </span>
          )}
        </label>
      )}

      {/* Idle — pick a file */}
      {state.status === "idle" && (
        <div
          className="flex cursor-pointer items-center gap-3 rounded-lg border border-dashed border-dreams-border bg-dreams-lightBg px-4 py-3 transition hover:border-dreams-blue"
          onClick={() => inputRef.current?.click()}
        >
          <Paperclip className="h-5 w-5 flex-shrink-0 text-dreams-textSecondary" />
          <span className="text-sm text-dreams-textSecondary">
            Click to select a file
          </span>
        </div>
      )}

      {/* Uploading — progress bar */}
      {state.status === "uploading" && (
        <div className="rounded-lg border border-dreams-border bg-dreams-lightBg px-4 py-3">
          <div className="flex items-center gap-2">
            <FileText className="h-4 w-4 flex-shrink-0 text-dreams-textSecondary" />
            <span className="flex-1 truncate text-sm font-medium text-dreams-textPrimary">
              {state.fileName}
            </span>
            <span className="text-xs text-dreams-textSecondary">
              {state.progress}%
            </span>
          </div>
          <div className="mt-2 h-1.5 w-full rounded-full bg-gray-200">
            <div
              className="h-1.5 rounded-full bg-dreams-blue transition-all duration-200"
              style={{ width: `${state.progress}%` }}
            />
          </div>
        </div>
      )}

      {/* Done — success tick */}
      {state.status === "done" && (
        <div className="flex items-center gap-2 rounded-lg border border-green-200 bg-green-50 px-4 py-3">
          <CheckCircle2 className="h-5 w-5 flex-shrink-0 text-green-600" />
          <span className="flex-1 truncate text-sm font-medium text-dreams-textPrimary">
            {state.fileName}
          </span>
          <button
            type="button"
            onClick={clear}
            className="text-dreams-textSecondary hover:text-dreams-textPrimary"
            aria-label="Remove file"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* Error — retry */}
      {state.status === "error" && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3">
          <div className="flex items-center gap-2">
            <AlertCircle className="h-5 w-5 flex-shrink-0 text-red-600" />
            <span className="flex-1 text-sm text-red-700">{state.message}</span>
            {state.file ? (
              <button
                type="button"
                onClick={() => startUpload(state.file!)}
                className="flex items-center gap-1 text-sm font-medium text-dreams-blue hover:underline"
              >
                <RefreshCw className="h-3.5 w-3.5" />
                Retry
              </button>
            ) : (
              <button
                type="button"
                onClick={() => inputRef.current?.click()}
                className="flex items-center gap-1 text-sm font-medium text-dreams-blue hover:underline"
              >
                Choose file
              </button>
            )}
          </div>
        </div>
      )}

      <input
        ref={inputRef}
        type="file"
        accept={accept}
        onChange={handleFileChange}
        className="hidden"
      />
    </div>
  );
}
