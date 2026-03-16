"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import { ArrowLeft, Upload, FileText, CheckCircle, XCircle, AlertCircle, Download } from "lucide-react";
import { getAccessToken } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
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

interface CSVRow {
  brand_name: string;
  manufacturer_name: string;
  salt_compositions: string;
  drug_type?: string;
  is_discontinued?: boolean;
  launch_date?: string;
}

interface ValidationError {
  row: number;
  field: string;
  message: string;
}

interface ImportResult {
  row: number;
  brand_name: string;
  status: "success" | "error" | "skipped";
  message: string;
  brand_id?: string;
}

export default function BulkImportPage() {
  const router = useRouter();
  const { toast } = useToast();

  const [file, setFile] = useState<File | null>(null);
  const [parsedData, setParsedData] = useState<CSVRow[]>([]);
  const [validationErrors, setValidationErrors] = useState<ValidationError[]>([]);
  const [importResults, setImportResults] = useState<ImportResult[]>([]);
  const [importStats, setImportStats] = useState<{
    total: number;
    successful: number;
    failed: number;
    skipped: number;
  } | null>(null);

  // Parse CSV file
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (!selectedFile) return;

    if (!selectedFile.name.endsWith(".csv")) {
      toast({
        title: "Invalid File",
        description: "Please upload a CSV file",
        variant: "destructive",
      });
      return;
    }

    setFile(selectedFile);
    setImportResults([]);
    setImportStats(null);

    const reader = new FileReader();
    reader.onload = (event) => {
      try {
        const text = event.target?.result as string;
        const parsed = parseCSV(text);
        setParsedData(parsed);

        // Validate data
        const errors = validateData(parsed);
        setValidationErrors(errors);

        if (errors.length === 0) {
          toast({
            title: "File Parsed Successfully",
            description: `${parsed.length} rows ready to import`,
          });
        } else {
          toast({
            title: "Validation Errors Found",
            description: `${errors.length} errors in ${parsed.length} rows`,
            variant: "destructive",
          });
        }
      } catch (error) {
        toast({
          title: "Parse Error",
          description: error instanceof Error ? error.message : "Failed to parse CSV",
          variant: "destructive",
        });
      }
    };

    reader.readAsText(selectedFile);
  };

  // Simple CSV parser
  const parseCSV = (text: string): CSVRow[] => {
    const lines = text.trim().split("\n");
    if (lines.length < 2) throw new Error("CSV must have header and at least one data row");

    const headers = lines[0].split(",").map((h) => h.trim());
    const requiredHeaders = ["brand_name", "manufacturer_name", "salt_compositions"];

    // Validate headers
    for (const required of requiredHeaders) {
      if (!headers.includes(required)) {
        throw new Error(`Missing required column: ${required}`);
      }
    }

    const rows: CSVRow[] = [];
    for (let i = 1; i < lines.length; i++) {
      const values = lines[i].split(",").map((v) => v.trim());
      const row: any = {};

      headers.forEach((header, index) => {
        let value: any = values[index] || "";

        // Type conversion
        if (header === "is_discontinued") {
          value = value.toLowerCase() === "true";
        }

        row[header] = value;
      });

      rows.push(row as CSVRow);
    }

    return rows;
  };

  // Validate parsed data
  const validateData = (data: CSVRow[]): ValidationError[] => {
    const errors: ValidationError[] = [];

    data.forEach((row, index) => {
      const rowNum = index + 2; // +2 because: 0-indexed + header row

      if (!row.brand_name) {
        errors.push({ row: rowNum, field: "brand_name", message: "Brand name is required" });
      }

      if (!row.manufacturer_name) {
        errors.push({
          row: rowNum,
          field: "manufacturer_name",
          message: "Manufacturer name is required",
        });
      }

      if (!row.salt_compositions) {
        errors.push({
          row: rowNum,
          field: "salt_compositions",
          message: "Salt compositions are required",
        });
      } else {
        // Validate composition format
        const parts = row.salt_compositions.split("+");
        for (const part of parts) {
          if (!part.includes("(") || !part.includes(")")) {
            errors.push({
              row: rowNum,
              field: "salt_compositions",
              message: `Invalid format: "${part}". Expected: SaltName(strength)`,
            });
          }
        }
      }

      if (row.drug_type && !["allopathy", "ayurveda", "homeopathy"].includes(row.drug_type)) {
        errors.push({
          row: rowNum,
          field: "drug_type",
          message: "Drug type must be: allopathy, ayurveda, or homeopathy",
        });
      }
    });

    return errors;
  };

  // Import mutation
  const importMutation = useMutation({
    mutationFn: async (data: CSVRow[]) => {
      const token = getAccessToken() || "";
      const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

      const response = await fetch(`${API_BASE_URL}/api/v1/admin/brands/bulk-import`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(data),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || "Failed to import data");
      }

      return response.json();
    },
    onSuccess: (data) => {
      setImportStats({
        total: data.total,
        successful: data.successful,
        failed: data.failed,
        skipped: data.skipped,
      });
      setImportResults(data.results);

      toast({
        title: "Import Complete",
        description: `${data.successful} brands imported, ${data.failed} failed, ${data.skipped} skipped`,
      });
    },
    onError: (error: Error) => {
      toast({
        title: "Import Failed",
        description: error.message,
        variant: "destructive",
      });
    },
  });

  const handleImport = () => {
    if (validationErrors.length > 0) {
      toast({
        title: "Cannot Import",
        description: "Please fix validation errors first",
        variant: "destructive",
      });
      return;
    }

    importMutation.mutate(parsedData);
  };

  const downloadTemplate = () => {
    // Download the sample CSV file from public directory
    const a = document.createElement("a");
    a.href = "/medicine_import_sample.csv";
    a.download = "medicine_import_sample.csv";
    a.click();
  };

  return (
    <div className="container mx-auto py-6 max-w-6xl">
      <div className="mb-6">
        <Button
          variant="ghost"
          onClick={() => router.push("/admin/medicines")}
          className="mb-4"
        >
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back to Medicines
        </Button>
        <div className="flex justify-between items-start">
          <div>
            <h1 className="text-3xl font-bold">Bulk Import Medicines</h1>
            <p className="text-muted-foreground mt-2">
              Upload a CSV file to import multiple brands at once
            </p>
          </div>
          <Button variant="outline" onClick={downloadTemplate}>
            <Download className="h-4 w-4 mr-2" />
            Download Template
          </Button>
        </div>
      </div>

      {/* Upload Section */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle>Upload CSV File</CardTitle>
          <CardDescription>
            Required columns: brand_name, manufacturer_name, salt_compositions
            <br />
            Composition format: SaltName(strength) for single or SaltName1(strength1) +
            SaltName2(strength2) for combinations
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-4">
            <label htmlFor="csv-upload" className="cursor-pointer">
              <div className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90">
                <Upload className="h-4 w-4" />
                <span>Choose File</span>
              </div>
              <input
                id="csv-upload"
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
          </div>
        </CardContent>
      </Card>

      {/* Preview Table */}
      {parsedData.length > 0 && !importStats && (
        <Card className="mb-6">
          <CardHeader>
            <div className="flex justify-between items-center">
              <div>
                <CardTitle>Preview Data</CardTitle>
                <CardDescription>
                  {parsedData.length} rows parsed
                  {validationErrors.length > 0 &&
                    ` (${validationErrors.length} errors)`}
                </CardDescription>
              </div>
              <Button
                onClick={handleImport}
                disabled={validationErrors.length > 0 || importMutation.isPending}
              >
                {importMutation.isPending ? "Importing..." : "Import All"}
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            <div className="max-h-96 overflow-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-12">Row</TableHead>
                    <TableHead>Brand Name</TableHead>
                    <TableHead>Manufacturer</TableHead>
                    <TableHead>Composition</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead className="w-24">Status</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {parsedData.map((row, index) => {
                    const rowNum = index + 2;
                    const rowErrors = validationErrors.filter((e) => e.row === rowNum);
                    const hasError = rowErrors.length > 0;

                    return (
                      <TableRow key={index} className={hasError ? "bg-destructive/10" : ""}>
                        <TableCell>{rowNum}</TableCell>
                        <TableCell className="font-medium">{row.brand_name}</TableCell>
                        <TableCell>{row.manufacturer_name}</TableCell>
                        <TableCell className="text-sm">{row.salt_compositions}</TableCell>
                        <TableCell>{row.drug_type || "allopathy"}</TableCell>
                        <TableCell>
                          {hasError ? (
                            <Badge variant="destructive" className="gap-1">
                              <XCircle className="h-3 w-3" />
                              Error
                            </Badge>
                          ) : (
                            <Badge variant="secondary" className="gap-1">
                              <CheckCircle className="h-3 w-3" />
                              Valid
                            </Badge>
                          )}
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>

            {/* Validation Errors */}
            {validationErrors.length > 0 && (
              <div className="mt-4 p-4 bg-destructive/10 rounded-md">
                <div className="flex items-center gap-2 mb-2">
                  <AlertCircle className="h-4 w-4 text-destructive" />
                  <span className="font-semibold">Validation Errors</span>
                </div>
                <ul className="list-disc list-inside text-sm space-y-1">
                  {validationErrors.slice(0, 10).map((error, index) => (
                    <li key={index}>
                      Row {error.row}, {error.field}: {error.message}
                    </li>
                  ))}
                  {validationErrors.length > 10 && (
                    <li className="text-muted-foreground">
                      ... and {validationErrors.length - 10} more errors
                    </li>
                  )}
                </ul>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Import Progress */}
      {importMutation.isPending && (
        <Card className="mb-6">
          <CardHeader>
            <CardTitle>Importing...</CardTitle>
            <CardDescription>Processing {parsedData.length} rows</CardDescription>
          </CardHeader>
          <CardContent>
            <Progress value={50} className="w-full" />
          </CardContent>
        </Card>
      )}

      {/* Import Results */}
      {importStats && (
        <Card>
          <CardHeader>
            <CardTitle>Import Results</CardTitle>
            <CardDescription>
              Total: {importStats.total} | Success: {importStats.successful} | Failed:{" "}
              {importStats.failed} | Skipped: {importStats.skipped}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="max-h-96 overflow-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-12">Row</TableHead>
                    <TableHead>Brand Name</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Message</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {importResults.map((result) => (
                    <TableRow key={result.row}>
                      <TableCell>{result.row}</TableCell>
                      <TableCell className="font-medium">{result.brand_name}</TableCell>
                      <TableCell>
                        {result.status === "success" && (
                          <Badge variant="default" className="gap-1">
                            <CheckCircle className="h-3 w-3" />
                            Success
                          </Badge>
                        )}
                        {result.status === "error" && (
                          <Badge variant="destructive" className="gap-1">
                            <XCircle className="h-3 w-3" />
                            Error
                          </Badge>
                        )}
                        {result.status === "skipped" && (
                          <Badge variant="secondary" className="gap-1">
                            <AlertCircle className="h-3 w-3" />
                            Skipped
                          </Badge>
                        )}
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {result.message}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>

            <div className="mt-4 flex justify-end">
              <Button onClick={() => router.push("/admin/medicines")}>
                Go to Medicines List
              </Button>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
