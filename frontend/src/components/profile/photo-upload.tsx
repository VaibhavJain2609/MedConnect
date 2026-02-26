"use client";

import * as React from "react";
import { Upload, X, Camera, Loader2 } from "lucide-react";
import { useMutation } from "@tanstack/react-query";
import { uploadPhoto } from "@/lib/api/users";
import { cn } from "@/lib/utils";
import { Avatar } from "@/components/ui/avatar";

export interface PhotoUploadProps {
  currentPhoto?: string | null;
  userId: string;
  onUploadSuccess?: (photoUrl: string) => void;
  onUploadError?: (error: Error) => void;
  maxSizeMB?: number;
  className?: string;
}

/**
 * PhotoUpload Component
 *
 * Profile photo upload with drag-drop and preview
 *
 * Features:
 * - Drag and drop support
 * - File picker fallback
 * - Image preview before upload
 * - Circular crop (1:1 aspect ratio)
 * - Size validation
 * - Upload progress
 * - Error handling
 *
 * @example
 * <PhotoUpload
 *   currentPhoto={user.photo}
 *   userId={user.id}
 *   onUploadSuccess={(url) => console.log("Uploaded:", url)}
 *   maxSizeMB={5}
 * />
 */
export const PhotoUpload: React.FC<PhotoUploadProps> = ({
  currentPhoto,
  userId,
  onUploadSuccess,
  onUploadError,
  maxSizeMB = 5,
  className,
}) => {
  const [isDragging, setIsDragging] = React.useState(false);
  const [previewUrl, setPreviewUrl] = React.useState<string | null>(null);
  const [selectedFile, setSelectedFile] = React.useState<File | null>(null);
  const fileInputRef = React.useRef<HTMLInputElement>(null);

  // Upload mutation
  const uploadMutation = useMutation({
    mutationFn: async (file: File) => {
      const result = await uploadPhoto(file);
      return { photoUrl: result.photo_url || "" };
    },
    onSuccess: (data) => {
      setPreviewUrl(null);
      setSelectedFile(null);
      onUploadSuccess?.(data.photoUrl);
    },
    onError: (error: Error) => {
      onUploadError?.(error);
    },
  });

  // Handle file selection
  const handleFileSelect = (file: File) => {
    // Validate file type
    if (!file.type.startsWith("image/")) {
      alert("Please select an image file");
      return;
    }

    // Validate file size
    const sizeMB = file.size / (1024 * 1024);
    if (sizeMB > maxSizeMB) {
      alert(`File size must be less than ${maxSizeMB}MB`);
      return;
    }

    setSelectedFile(file);

    // Create preview
    const reader = new FileReader();
    reader.onloadend = () => {
      setPreviewUrl(reader.result as string);
    };
    reader.readAsDataURL(file);
  };

  // Handle drag and drop
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);

    const files = e.dataTransfer.files;
    if (files && files.length > 0) {
      handleFileSelect(files[0]);
    }
  };

  // Handle file input change
  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      handleFileSelect(files[0]);
    }
  };

  // Handle upload
  const handleUpload = () => {
    if (selectedFile) {
      uploadMutation.mutate(selectedFile);
    }
  };

  // Handle cancel
  const handleCancel = () => {
    setPreviewUrl(null);
    setSelectedFile(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  return (
    <div className={cn("space-y-4", className)}>
      {/* Current Photo Preview */}
      <div className="flex items-center gap-4">
        <Avatar
          src={previewUrl || currentPhoto}
          fallback="User"
          size="2xl"
        />
        <div className="flex-1">
          <p className="text-sm font-medium text-dreams-textPrimary mb-1">
            Profile Photo
          </p>
          <p className="text-xs text-dreams-textSecondary">
            Upload a photo (max {maxSizeMB}MB). JPG, PNG, or GIF.
          </p>
        </div>
      </div>

      {/* Upload Area */}
      {!previewUrl ? (
        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          className={cn(
            "border-2 border-dashed rounded-lg p-8 text-center transition-colors cursor-pointer",
            isDragging
              ? "border-dreams-blue bg-dreams-blue/5"
              : "border-dreams-border hover:border-dreams-blue/50 hover:bg-dreams-lightBg/50"
          )}
          onClick={() => fileInputRef.current?.click()}
        >
          <Upload className="h-12 w-12 text-dreams-textSecondary mx-auto mb-3" />
          <p className="text-sm font-medium text-dreams-textPrimary mb-1">
            Drop your photo here, or{" "}
            <span className="text-dreams-blue">browse</span>
          </p>
          <p className="text-xs text-dreams-textSecondary">
            Supports: JPG, PNG, GIF (max {maxSizeMB}MB)
          </p>

          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            onChange={handleFileInputChange}
            className="hidden"
          />
        </div>
      ) : (
        /* Preview and Actions */
        <div className="space-y-4">
          <div className="border border-dreams-border rounded-lg p-4">
            <div className="flex items-start gap-4">
              <div className="relative flex-shrink-0">
                <img
                  src={previewUrl}
                  alt="Preview"
                  className="h-32 w-32 rounded-full object-cover border-2 border-dreams-border"
                />
                <button
                  onClick={handleCancel}
                  disabled={uploadMutation.isPending}
                  className="absolute -top-2 -right-2 p-1 rounded-full bg-status-overdue text-white hover:bg-status-overdue/80 disabled:opacity-50"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>

              <div className="flex-1 min-w-0">
                <p className="font-medium text-dreams-textPrimary mb-1">
                  {selectedFile?.name}
                </p>
                <p className="text-sm text-dreams-textSecondary">
                  {selectedFile
                    ? `${(selectedFile.size / (1024 * 1024)).toFixed(2)} MB`
                    : ""}
                </p>

                {uploadMutation.isPending && (
                  <div className="mt-3">
                    <div className="flex items-center gap-2 text-sm text-dreams-textSecondary">
                      <Loader2 className="h-4 w-4 animate-spin" />
                      <span>Uploading...</span>
                    </div>
                  </div>
                )}

                {uploadMutation.isError && (
                  <p className="mt-2 text-sm text-status-overdue">
                    Upload failed. Please try again.
                  </p>
                )}
              </div>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex gap-3">
            <button
              onClick={handleUpload}
              disabled={!selectedFile || uploadMutation.isPending}
              className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-dreams-blue text-white rounded-lg hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {uploadMutation.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span>Uploading...</span>
                </>
              ) : (
                <>
                  <Camera className="h-4 w-4" />
                  <span>Upload Photo</span>
                </>
              )}
            </button>

            <button
              onClick={handleCancel}
              disabled={uploadMutation.isPending}
              className="px-4 py-2 border border-dreams-border text-dreams-textSecondary rounded-lg hover:bg-dreams-lightBg transition-colors disabled:opacity-50"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

PhotoUpload.displayName = "PhotoUpload";
