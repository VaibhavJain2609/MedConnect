"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import {
  ArrowLeft,
  Upload,
  FileText,
  CheckCircle,
  XCircle,
  AlertCircle,
  Download,
  Loader2,
  RefreshCw,
} from "lucide-react";
import {
  importCatalogCsv,
  getApiErrorMessage,
  type CatalogImportResponse,
  type CatalogImportRowStatus,
} from "@/lib/api/medicines-emr";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/hooks/use-toast";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

function StatusBadge({ status, label }: { status: CatalogImportRowStatus; label: string }) {
  switch (status) {
    case "created":
      return (
        <Badge variant="default" className="gap-1">
          <CheckCircle className="h-3 w-3" />
          {label}
        </Badge>
      );
    case "updated":
      return (
        <Badge variant="secondary" className="gap-1">
          <RefreshCw className="h-3 w-3" />
          {label}
        </Badge>
      );
    case "skipped":
      return (
        <Badge variant="outline" className="gap-1">
          <AlertCircle className="h-3 w-3" />
          {label}
        </Badge>
      );
    case "error":
      return (
        <Badge variant="destructive" className="gap-1">
          <XCircle className="h-3 w-3" />
          {label}
        </Badge>
      );
  }
}

export default function CatalogImportPage() {
  const router = useRouter();
  const { toast } = useToast();
  const t = useTranslations("catalogImport");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const statusLabels: Record<CatalogImportRowStatus, string> = {
    created: t("status.created"),
    updated: t("status.updated"),
    skipped: t("status.skipped"),
    error: t("status.error"),
  };

  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<CatalogImportResponse | null>(null);
  const [result, setResult] = useState<CatalogImportResponse | null>(null);

  const summaryText = (r: CatalogImportResponse) =>
    t("summary", {
      total: r.total,
      created: r.created,
      updated: r.updated,
      skipped: r.skipped,
      errors: r.errors.length,
    });

  // Dry-run: validate + preview per-row outcomes without writing.
  const dryRunMutation = useMutation({
    mutationFn: (f: File) => importCatalogCsv(f, true),
    onSuccess: (data) => setPreview(data),
    onError: (error: unknown) => {
      setFile(null);
      toast({
        title: t("previewFailed"),
        description: getApiErrorMessage(error),
        variant: "destructive",
      });
    },
  });

  // Real import, only reachable after a successful dry-run preview.
  const importMutation = useMutation({
    mutationFn: (f: File) => importCatalogCsv(f, false),
    onSuccess: (data) => {
      setResult(data);
      setPreview(null);
      toast({ title: t("importComplete"), description: summaryText(data) });
    },
    onError: (error: unknown) => {
      toast({
        title: t("importFailed"),
        description: getApiErrorMessage(error),
        variant: "destructive",
      });
    },
  });

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0];
    // Reset the input so re-selecting the same file retriggers onChange.
    e.target.value = "";
    if (!selected) return;

    if (!selected.name.toLowerCase().endsWith(".csv")) {
      toast({ title: t("invalidFile"), variant: "destructive" });
      return;
    }

    setFile(selected);
    setPreview(null);
    setResult(null);
    dryRunMutation.mutate(selected);
  };

  const handleConfirm = () => {
    if (file) importMutation.mutate(file);
  };

  const downloadTemplate = () => {
    const a = document.createElement("a");
    a.href = "/catalog_import_template.csv";
    a.download = "catalog_import_template.csv";
    a.click();
  };

  const busy = dryRunMutation.isPending || importMutation.isPending;
  const report = result ?? preview;

  return (
    <div className="container mx-auto py-6 max-w-6xl">
      <div className="mb-6">
        <Button
          variant="ghost"
          onClick={() => router.push("/admin/medicines")}
          className="mb-4"
        >
          <ArrowLeft className="h-4 w-4 mr-2" />
          {t("backToMedicines")}
        </Button>
        <div className="flex justify-between items-start">
          <div>
            <h1 className="text-3xl font-bold">{t("title")}</h1>
            <p className="text-muted-foreground mt-2">{t("subtitle")}</p>
          </div>
          <Button variant="outline" onClick={downloadTemplate}>
            <Download className="h-4 w-4 mr-2" />
            {t("downloadTemplate")}
          </Button>
        </div>
      </div>

      {/* Upload */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle>{t("uploadTitle")}</CardTitle>
          <CardDescription>{t("uploadDescription")}</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-4">
            <label htmlFor="csv-upload" className="cursor-pointer">
              <div className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90">
                <Upload className="h-4 w-4" />
                <span>{t("chooseFile")}</span>
              </div>
              <input
                id="csv-upload"
                ref={fileInputRef}
                type="file"
                accept=".csv"
                onChange={handleFileChange}
                className="hidden"
              />
            </label>
            {file && (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <FileText className="h-4 w-4" />
                <span>{file.name}</span>
              </div>
            )}
            {dryRunMutation.isPending && (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
                <span>{t("validating")}</span>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Dry-run preview / import results */}
      {report && (
        <Card>
          <CardHeader>
            <div className="flex justify-between items-center">
              <div>
                <CardTitle>{result ? t("resultsTitle") : t("previewTitle")}</CardTitle>
                <CardDescription>{summaryText(report)}</CardDescription>
              </div>
              {!result && (
                <Button onClick={handleConfirm} disabled={busy}>
                  {importMutation.isPending ? (
                    <>
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      {t("importing")}
                    </>
                  ) : (
                    t("confirmImport")
                  )}
                </Button>
              )}
            </div>
          </CardHeader>
          <CardContent>
            <div className="max-h-96 overflow-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-16">{t("colRow")}</TableHead>
                    <TableHead>{t("colBrand")}</TableHead>
                    <TableHead className="w-28">{t("colStatus")}</TableHead>
                    <TableHead>{t("colMessage")}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {report.rows.map((row) => (
                    <TableRow
                      key={row.row}
                      className={row.status === "error" ? "bg-destructive/10" : ""}
                    >
                      <TableCell>{row.row}</TableCell>
                      <TableCell className="font-medium">{row.brand_name ?? "—"}</TableCell>
                      <TableCell>
                        <StatusBadge status={row.status} label={statusLabels[row.status]} />
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {row.message}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>

            {result && (
              <div className="mt-4 flex justify-end">
                <Button onClick={() => router.push("/admin/medicines")}>
                  {t("goToMedicines")}
                </Button>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
