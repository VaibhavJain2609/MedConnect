"use client";

import { useState } from "react";
import { Search, Plus, Pill, ChevronDown, Filter } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export default function MedicinesPage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedFilter, setSelectedFilter] = useState("all");

  // TODO: Replace with actual API call to /api/v1/admin/medicines
  const medicines = [
    {
      id: "1",
      brand_name: "CombiFlam Tablet",
      manufacturer: "Sanofi India Ltd",
      components: "Paracetamol (325mg) + Ibuprofen (400mg)",
      therapeutic_class: "PAIN ANALGESICS",
      mrp: 46.05,
      is_discontinued: false,
    },
    {
      id: "2",
      brand_name: "Augmentin 625 Duo Tablet",
      manufacturer: "Glaxo SmithKline",
      components: "Amoxycillin (500mg) + Clavulanic Acid (125mg)",
      therapeutic_class: "ANTI INFECTIVES",
      mrp: 223.42,
      is_discontinued: false,
    },
  ];

  const stats = {
    total: "251,320",
    active: "243,599",
    discontinued: "7,721",
    components: "1,530",
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
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Total Medicines</CardDescription>
            <CardTitle className="text-3xl font-bold text-primary-600">
              {stats.total}
            </CardTitle>
          </CardHeader>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Active</CardDescription>
            <CardTitle className="text-3xl font-bold text-green-600">
              {stats.active}
            </CardTitle>
          </CardHeader>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Discontinued</CardDescription>
            <CardTitle className="text-3xl font-bold text-gray-400">
              {stats.discontinued}
            </CardTitle>
          </CardHeader>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Unique Components</CardDescription>
            <CardTitle className="text-3xl font-bold text-blue-600">
              {stats.components}
            </CardTitle>
          </CardHeader>
        </Card>
      </div>

      {/* Search and Filters */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex flex-col sm:flex-row gap-4">
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
              <button className="flex items-center gap-2 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50">
                <Filter className="h-4 w-4" />
                <span className="hidden sm:inline">Filter</span>
                <ChevronDown className="h-4 w-4" />
              </button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Medicines Table */}
      <Card>
        <CardHeader>
          <CardTitle>Medicine List</CardTitle>
          <CardDescription>
            Showing {medicines.length} medicines
          </CardDescription>
        </CardHeader>
        <CardContent>
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
                        </div>
                      </div>
                    </td>
                    <td className="py-4 text-sm text-gray-600">
                      {medicine.manufacturer}
                    </td>
                    <td className="py-4 text-sm text-gray-600 max-w-xs truncate">
                      {medicine.components}
                    </td>
                    <td className="py-4">
                      <span className="inline-flex items-center rounded-full bg-blue-50 px-2 py-1 text-xs font-medium text-blue-700">
                        {medicine.therapeutic_class}
                      </span>
                    </td>
                    <td className="py-4 text-sm font-medium text-gray-900">
                      ₹{medicine.mrp.toFixed(2)}
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
              Showing 1-{medicines.length} of {stats.total}
            </p>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" disabled>
                Previous
              </Button>
              <Button variant="outline" size="sm">
                Next
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Integration Note */}
      <Card className="bg-blue-50 border-blue-200">
        <CardContent className="pt-6">
          <div className="flex gap-3">
            <div className="flex-shrink-0">
              <svg
                className="h-5 w-5 text-blue-600"
                fill="currentColor"
                viewBox="0 0 20 20"
              >
                <path
                  fillRule="evenodd"
                  d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z"
                  clipRule="evenodd"
                />
              </svg>
            </div>
            <div>
              <h3 className="text-sm font-medium text-blue-900">
                Backend Integration Ready
              </h3>
              <p className="mt-1 text-sm text-blue-700">
                The medicine database with 251,320+ medicines is ready. Connect to API endpoints:
                <br />
                <code className="mt-1 inline-block rounded bg-blue-100 px-2 py-0.5 text-xs">
                  GET /api/v1/admin/medicines
                </code>
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
