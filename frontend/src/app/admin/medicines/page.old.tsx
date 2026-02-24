"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Search, Plus, Pill, ChevronDown, Filter, Loader2, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { searchMedicines, getMedicineStats } from "@/lib/api/medicines";

export default function MedicinesPage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [currentPage, setCurrentPage] = useState(1);
  const [includeDiscontinued, setIncludeDiscontinued] = useState(true);
  const limit = 50;

  // Fetch medicines
  const {
    data: medicinesData,
    isLoading: medicinesLoading,
    error: medicinesError,
  } = useQuery({
    queryKey: ["admin-medicines", searchQuery, currentPage, includeDiscontinued],
    queryFn: () =>
      searchMedicines({
        search: searchQuery || undefined,
        page: currentPage,
        limit,
        include_discontinued: includeDiscontinued,
      }),
    staleTime: 30000, // 30 seconds
  });

  // Fetch stats
  const {
    data: stats,
    isLoading: statsLoading,
  } = useQuery({
    queryKey: ["medicine-stats"],
    queryFn: getMedicineStats,
    staleTime: 60000, // 1 minute
  });

  const medicines = medicinesData?.medicines || [];
  const total = medicinesData?.total || 0;
  const pages = medicinesData?.pages || 0;

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setCurrentPage(1); // Reset to first page on new search
  };

  const formatCurrency = (amount: number | null | string) => {
    if (amount === null || amount === undefined) return "N/A";
    const numAmount = typeof amount === 'string' ? parseFloat(amount) : amount;
    if (isNaN(numAmount)) return "N/A";
    return `₹${numAmount.toFixed(2)}`;
  };

  const getSaltComposition = (components: any[]) => {
    return components
      .map((c) => `${c.component_name} (${c.strength}${c.unit})`)
      .join(" + ");
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Medicines Database</h1>
          <p className="mt-1 text-sm text-gray-500">
            Manage your medicine inventory and components
          </p>
        </div>
        <Button className="sm:w-auto">
          <Plus className="h-4 w-4 mr-2" />
          Add Medicine
        </Button>
      </div>

      {/* Stats Cards */}
      {statsLoading ? (
        <div className="grid gap-4 md:grid-cols-4">
          {[1, 2, 3, 4].map((i) => (
            <Card key={i}>
              <CardHeader className="pb-2">
                <div className="h-4 w-24 bg-gray-200 rounded animate-pulse" />
                <div className="h-8 w-32 bg-gray-200 rounded animate-pulse mt-2" />
              </CardHeader>
            </Card>
          ))}
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-4">
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Total Medicines</CardDescription>
              <CardTitle className="text-3xl font-bold text-primary-600">
                {stats?.total.toLocaleString() || "0"}
              </CardTitle>
            </CardHeader>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Active</CardDescription>
              <CardTitle className="text-3xl font-bold text-green-600">
                {stats?.active.toLocaleString() || "0"}
              </CardTitle>
            </CardHeader>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Discontinued</CardDescription>
              <CardTitle className="text-3xl font-bold text-gray-400">
                {stats?.discontinued.toLocaleString() || "0"}
              </CardTitle>
            </CardHeader>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Unique Components</CardDescription>
              <CardTitle className="text-3xl font-bold text-blue-600">
                {stats?.components.toLocaleString() || "0"}
              </CardTitle>
            </CardHeader>
          </Card>
        </div>
      )}

      {/* Search and Filters */}
      <Card>
        <CardContent className="pt-6">
          <form onSubmit={handleSearch} className="flex flex-col sm:flex-row gap-4">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
              <input
                type="text"
                placeholder="Search by medicine name or manufacturer..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
            </div>

            <div className="flex gap-2">
              <Button type="submit" variant="outline">
                Search
              </Button>
              <label className="flex items-center gap-2 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 cursor-pointer">
                <input
                  type="checkbox"
                  checked={includeDiscontinued}
                  onChange={(e) => {
                    setIncludeDiscontinued(e.target.checked);
                    setCurrentPage(1);
                  }}
                  className="rounded"
                />
                <span className="text-sm">Show discontinued</span>
              </label>
            </div>
          </form>
        </CardContent>
      </Card>

      {/* Error State */}
      {medicinesError && (
        <Card className="border-red-200 bg-red-50">
          <CardContent className="pt-6">
            <div className="flex gap-3">
              <AlertCircle className="h-5 w-5 text-red-600 flex-shrink-0" />
              <div>
                <h3 className="text-sm font-medium text-red-900">
                  Failed to load medicines
                </h3>
                <p className="mt-1 text-sm text-red-700">
                  {medicinesError instanceof Error
                    ? medicinesError.message
                    : "An error occurred while fetching medicines"}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Medicines Table */}
      <Card>
        <CardHeader>
          <CardTitle>Medicine List</CardTitle>
          <CardDescription>
            {medicinesLoading
              ? "Loading medicines..."
              : `Showing ${medicines.length} of ${total.toLocaleString()} medicines`}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {medicinesLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-8 w-8 animate-spin text-primary-600" />
              <span className="ml-2 text-gray-600">Loading medicines...</span>
            </div>
          ) : medicines.length === 0 ? (
            <div className="text-center py-12">
              <Pill className="mx-auto h-12 w-12 text-gray-400" />
              <h3 className="mt-2 text-sm font-medium text-gray-900">No medicines found</h3>
              <p className="mt-1 text-sm text-gray-500">
                {searchQuery
                  ? "Try adjusting your search query"
                  : "Get started by adding a new medicine"}
              </p>
            </div>
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b text-left text-sm text-gray-500">
                      <th className="pb-3 font-medium">Medicine</th>
                      <th className="pb-3 font-medium">Manufacturer</th>
                      <th className="pb-3 font-medium">Components</th>
                      <th className="pb-3 font-medium">Class</th>
                      <th className="pb-3 font-medium">MRP</th>
                      <th className="pb-3 font-medium">Status</th>
                      <th className="pb-3 font-medium">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {medicines.map((medicine) => (
                      <tr key={medicine.id} className="border-b last:border-0">
                        <td className="py-4">
                          <div className="flex items-center gap-3">
                            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary-50">
                              <Pill className="h-5 w-5 text-primary-600" />
                            </div>
                            <div>
                              <p className="font-medium text-gray-900">
                                {medicine.brand_name}
                              </p>
                              {medicine.dosage_form && (
                                <p className="text-xs text-gray-500">
                                  {medicine.dosage_form}
                                </p>
                              )}
                            </div>
                          </div>
                        </td>
                        <td className="py-4 text-sm text-gray-600">
                          {medicine.manufacturer || "—"}
                        </td>
                        <td className="py-4 text-sm text-gray-600 max-w-xs">
                          <div className="truncate" title={getSaltComposition(medicine.components)}>
                            {getSaltComposition(medicine.components)}
                          </div>
                        </td>
                        <td className="py-4">
                          {medicine.therapeutic_class ? (
                            <span className="inline-flex items-center rounded-full bg-blue-50 px-2 py-1 text-xs font-medium text-blue-700">
                              {medicine.therapeutic_class}
                            </span>
                          ) : (
                            <span className="text-gray-400 text-xs">—</span>
                          )}
                        </td>
                        <td className="py-4 text-sm font-medium text-gray-900">
                          {formatCurrency(medicine.mrp)}
                        </td>
                        <td className="py-4">
                          <span
                            className={`inline-flex items-center rounded-full px-2 py-1 text-xs font-medium ${
                              medicine.is_discontinued
                                ? "bg-gray-100 text-gray-700"
                                : "bg-green-50 text-green-700"
                            }`}
                          >
                            {medicine.is_discontinued ? "Discontinued" : "Active"}
                          </span>
                        </td>
                        <td className="py-4">
                          <div className="flex gap-2">
                            <Button variant="ghost" size="sm">
                              View
                            </Button>
                            <Button variant="ghost" size="sm">
                              Edit
                            </Button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Pagination */}
              <div className="mt-4 flex items-center justify-between">
                <p className="text-sm text-gray-500">
                  Showing {(currentPage - 1) * limit + 1}-
                  {Math.min(currentPage * limit, total)} of {total.toLocaleString()}
                </p>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={currentPage === 1}
                    onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                  >
                    Previous
                  </Button>
                  <span className="flex items-center px-3 text-sm text-gray-600">
                    Page {currentPage} of {pages}
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={currentPage >= pages}
                    onClick={() => setCurrentPage((p) => Math.min(pages, p + 1))}
                  >
                    Next
                  </Button>
                </div>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      {/* Success Note */}
      {!medicinesLoading && !medicinesError && (
        <Card className="bg-green-50 border-green-200">
          <CardContent className="pt-6">
            <div className="flex gap-3">
              <div className="flex-shrink-0">
                <svg
                  className="h-5 w-5 text-green-600"
                  fill="currentColor"
                  viewBox="0 0 20 20"
                >
                  <path
                    fillRule="evenodd"
                    d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                    clipRule="evenodd"
                  />
                </svg>
              </div>
              <div>
                <h3 className="text-sm font-medium text-green-900">
                  Connected to Medicine Database
                </h3>
                <p className="mt-1 text-sm text-green-700">
                  Showing real-time data from {stats?.total.toLocaleString()} medicines with{" "}
                  {stats?.components.toLocaleString()} unique components.
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
