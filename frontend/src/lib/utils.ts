import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

export function recordTypeLabel(type: string): string {
  const labels: Record<string, string> = {
    prescription: "Prescription",
    diagnostic_report: "Diagnostic Report",
    discharge_summary: "Discharge Summary",
    opd_note: "OPD Note",
    immunization: "Immunization",
    lab_report: "Lab Report",
    imaging: "Imaging",
    other: "Other",
  };
  return labels[type] || type;
}

export function recordTypeColor(type: string): string {
  const colors: Record<string, string> = {
    prescription: "bg-blue-100 text-blue-800",
    diagnostic_report: "bg-purple-100 text-purple-800",
    discharge_summary: "bg-red-100 text-red-800",
    opd_note: "bg-green-100 text-green-800",
    immunization: "bg-yellow-100 text-yellow-800",
    lab_report: "bg-indigo-100 text-indigo-800",
    imaging: "bg-pink-100 text-pink-800",
    other: "bg-gray-100 text-gray-800",
  };
  return colors[type] || "bg-gray-100 text-gray-800";
}
