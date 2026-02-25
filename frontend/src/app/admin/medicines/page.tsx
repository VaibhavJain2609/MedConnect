"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Search, Plus, Pill, Loader2, AlertCircle, Beaker, Package, Info, List, Upload, Building2, Edit, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  listSalts,
  listBrands,
  getMedicineStats,
  getSalt,
  getBrandsForSalt,
  getBrand,
  getBrandAlternatives,
  type Salt,
  type Brand,
  type BrandForSalt,
} from "@/lib/api/medicines-emr";

// API functions for Manufacturers
async function listManufacturers(params: { search?: string }) {
  const queryParams = new URLSearchParams();
  if (params.search) queryParams.append("search", params.search);
  queryParams.append("limit", "50");

  const res = await fetch(`/api/v1/manufacturers?${queryParams}`);
  if (!res.ok) throw new Error("Failed to fetch manufacturers");
  return res.json();
}

async function createManufacturer(data: any) {
  const res = await fetch("/api/v1/admin/manufacturers", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.detail || "Failed to create manufacturer");
  }
  return res.json();
}

async function updateManufacturer(id: string, data: any) {
  const res = await fetch(`/api/v1/admin/manufacturers/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.detail || "Failed to update manufacturer");
  }
  return res.json();
}

async function deleteManufacturer(id: string) {
  const res = await fetch(`/api/v1/admin/manufacturers/${id}`, {
    method: "DELETE",
  });
  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.detail || "Failed to delete manufacturer");
  }
}

// API functions for Salts CRUD
async function createSalt(data: any) {
  const res = await fetch("/api/v1/admin/salts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.detail || "Failed to create salt");
  }
  return res.json();
}

async function updateSalt(id: string, data: any) {
  const res = await fetch(`/api/v1/admin/salts/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.detail || "Failed to update salt");
  }
  return res.json();
}

async function deleteSalt(id: string) {
  const res = await fetch(`/api/v1/admin/salts/${id}`, {
    method: "DELETE",
  });
  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.detail || "Failed to delete salt");
  }
}

export default function MedicinesPageEMR() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [searchQuery, setSearchQuery] = useState("");
  const [currentPage, setCurrentPage] = useState(1);
  const [includeDiscontinued, setIncludeDiscontinued] = useState(false);
  const [activeTab, setActiveTab] = useState<"manufacturers" | "salts" | "brands">("manufacturers");

  // Dialog states - View dialogs
  const [selectedSaltId, setSelectedSaltId] = useState<string | null>(null);
  const [selectedBrandId, setSelectedBrandId] = useState<string | null>(null);
  const [showSaltDetails, setShowSaltDetails] = useState(false);
  const [showSaltBrands, setShowSaltBrands] = useState(false);
  const [showBrandDetails, setShowBrandDetails] = useState(false);
  const [showBrandAlternatives, setShowBrandAlternatives] = useState(false);

  // Dialog states - Manufacturer CRUD
  const [showCreateManufacturer, setShowCreateManufacturer] = useState(false);
  const [showEditManufacturer, setShowEditManufacturer] = useState(false);
  const [editingManufacturer, setEditingManufacturer] = useState<any>(null);
  const [manufacturerFormData, setManufacturerFormData] = useState({
    manufacturer_name: "",
    country: "",
    license_number: "",
    is_active: true,
  });

  // Dialog states - Salt CRUD
  const [showCreateSalt, setShowCreateSalt] = useState(false);
  const [showEditSalt, setShowEditSalt] = useState(false);
  const [editingSalt, setEditingSalt] = useState<any>(null);
  const [saltFormData, setSaltFormData] = useState({
    salt_name: "",
    description: "",
    chemical_formula: "",
    habit_forming: false,
    prescription_required: true,
    pregnancy_category: "",
  });

  const limit = 50;

  // Fetch manufacturers
  const {
    data: manufacturersData,
    isLoading: manufacturersLoading,
    error: manufacturersError,
  } = useQuery({
    queryKey: ["admin-manufacturers-list", searchQuery],
    queryFn: () => listManufacturers({ search: searchQuery || undefined }),
    staleTime: 30000,
    enabled: activeTab === "manufacturers",
  });

  // Fetch salts
  const {
    data: saltsData,
    isLoading: saltsLoading,
    error: saltsError,
  } = useQuery({
    queryKey: ["admin-salts", searchQuery, currentPage],
    queryFn: () =>
      listSalts({
        search: searchQuery || undefined,
        page: currentPage,
        limit,
      }),
    staleTime: 30000,
    enabled: activeTab === "salts",
  });

  // Fetch brands
  const {
    data: brandsData,
    isLoading: brandsLoading,
    error: brandsError,
  } = useQuery({
    queryKey: ["admin-brands", searchQuery, currentPage, includeDiscontinued],
    queryFn: () =>
      listBrands({
        search: searchQuery || undefined,
        page: currentPage,
        limit,
        include_discontinued: includeDiscontinued,
      }),
    staleTime: 30000,
    enabled: activeTab === "brands",
  });

  // Fetch stats
  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ["medicine-stats-emr"],
    queryFn: getMedicineStats,
    staleTime: 60000,
  });

  // Manufacturer mutations
  const createManufacturerMutation = useMutation({
    mutationFn: createManufacturer,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-manufacturers-list"] });
      queryClient.invalidateQueries({ queryKey: ["medicine-stats-emr"] });
      setShowCreateManufacturer(false);
      resetManufacturerForm();
    },
  });

  const updateManufacturerMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) => updateManufacturer(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-manufacturers-list"] });
      setShowEditManufacturer(false);
      setEditingManufacturer(null);
      resetManufacturerForm();
    },
  });

  const deleteManufacturerMutation = useMutation({
    mutationFn: deleteManufacturer,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-manufacturers-list"] });
      queryClient.invalidateQueries({ queryKey: ["medicine-stats-emr"] });
    },
  });

  // Salt mutations
  const createSaltMutation = useMutation({
    mutationFn: createSalt,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-salts"] });
      queryClient.invalidateQueries({ queryKey: ["medicine-stats-emr"] });
      setShowCreateSalt(false);
      resetSaltForm();
    },
  });

  const updateSaltMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) => updateSalt(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-salts"] });
      setShowEditSalt(false);
      setEditingSalt(null);
      resetSaltForm();
    },
  });

  const deleteSaltMutation = useMutation({
    mutationFn: deleteSalt,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-salts"] });
      queryClient.invalidateQueries({ queryKey: ["medicine-stats-emr"] });
    },
  });

  // Fetch selected salt details
  const { data: selectedSalt } = useQuery({
    queryKey: ["salt-details", selectedSaltId],
    queryFn: () => getSalt(selectedSaltId!),
    enabled: !!selectedSaltId && showSaltDetails,
  });

  // Fetch brands for selected salt
  const { data: saltBrands } = useQuery({
    queryKey: ["salt-brands", selectedSaltId],
    queryFn: () => getBrandsForSalt(selectedSaltId!),
    enabled: !!selectedSaltId && showSaltBrands,
  });

  // Fetch selected brand details
  const { data: selectedBrand } = useQuery({
    queryKey: ["brand-details", selectedBrandId],
    queryFn: () => getBrand(selectedBrandId!),
    enabled: !!selectedBrandId && showBrandDetails,
  });

  // Fetch brand alternatives
  const { data: brandAlternatives } = useQuery({
    queryKey: ["brand-alternatives", selectedBrandId],
    queryFn: () => getBrandAlternatives(selectedBrandId!),
    enabled: !!selectedBrandId && showBrandAlternatives,
  });

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setCurrentPage(1);
  };

  const handleTabChange = (value: string) => {
    setActiveTab(value as "manufacturers" | "salts" | "brands");
    setCurrentPage(1);
    setSearchQuery("");
  };

  // Manufacturer handlers
  const resetManufacturerForm = () => {
    setManufacturerFormData({
      manufacturer_name: "",
      country: "",
      license_number: "",
      is_active: true,
    });
  };

  const handleCreateManufacturer = () => {
    createManufacturerMutation.mutate(manufacturerFormData);
  };

  const handleEditManufacturer = (manufacturer: any) => {
    setEditingManufacturer(manufacturer);
    setManufacturerFormData({
      manufacturer_name: manufacturer.manufacturer_name,
      country: manufacturer.country || "",
      license_number: manufacturer.license_number || "",
      is_active: manufacturer.is_active,
    });
    setShowEditManufacturer(true);
  };

  const handleUpdateManufacturer = () => {
    if (!editingManufacturer) return;
    updateManufacturerMutation.mutate({ id: editingManufacturer.manufacturer_id, data: manufacturerFormData });
  };

  const handleDeleteManufacturer = (id: string, name: string) => {
    if (confirm(`Delete manufacturer "${name}"? This will fail if the manufacturer has any brands.`)) {
      deleteManufacturerMutation.mutate(id);
    }
  };

  // Salt handlers
  const resetSaltForm = () => {
    setSaltFormData({
      salt_name: "",
      description: "",
      chemical_formula: "",
      habit_forming: false,
      prescription_required: true,
      pregnancy_category: "",
    });
  };

  const handleCreateSalt = () => {
    createSaltMutation.mutate(saltFormData);
  };

  const handleEditSalt = (salt: any) => {
    setEditingSalt(salt);
    setSaltFormData({
      salt_name: salt.salt_name,
      description: salt.description || "",
      chemical_formula: salt.chemical_formula || "",
      habit_forming: salt.habit_forming,
      prescription_required: salt.prescription_required,
      pregnancy_category: salt.pregnancy_category || "",
    });
    setShowEditSalt(true);
  };

  const handleUpdateSalt = () => {
    if (!editingSalt) return;
    updateSaltMutation.mutate({ id: editingSalt.salt_id, data: saltFormData });
  };

  const handleDeleteSalt = (id: string, name: string) => {
    if (confirm(`Delete salt "${name}"? This will fail if the salt has any strengths.`)) {
      deleteSaltMutation.mutate(id);
    }
  };

  const handleViewSalt = (saltId: string) => {
    setSelectedSaltId(saltId);
    setShowSaltDetails(true);
  };

  const handleViewSaltBrands = (saltId: string) => {
    setSelectedSaltId(saltId);
    setShowSaltBrands(true);
  };

  const handleViewBrand = (brandId: string) => {
    setSelectedBrandId(brandId);
    setShowBrandDetails(true);
  };

  const handleViewBrandAlternatives = (brandId: string) => {
    setSelectedBrandId(brandId);
    setShowBrandAlternatives(true);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Medicine Database (EMR)</h1>
          <p className="mt-1 text-sm text-gray-500">
            Normalized pharmaceutical database with salts, strengths, and brands
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => router.push("/admin/medicines/import")}>
            <Upload className="h-4 w-4 mr-2" />
            Bulk Import
          </Button>
          <Button onClick={() => router.push("/admin/medicines/new")}>
            <Plus className="h-4 w-4 mr-2" />
            Add Medicine
          </Button>
        </div>
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
              <CardDescription>Total Salts (APIs)</CardDescription>
              <CardTitle className="text-3xl font-bold text-blue-600">
                {stats?.total_salts.toLocaleString() || "0"}
              </CardTitle>
            </CardHeader>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Total Brands</CardDescription>
              <CardTitle className="text-3xl font-bold text-green-600">
                {stats?.total_brands.toLocaleString() || "0"}
              </CardTitle>
            </CardHeader>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Manufacturers</CardDescription>
              <CardTitle className="text-3xl font-bold text-purple-600">
                {stats?.total_manufacturers.toLocaleString() || "0"}
              </CardTitle>
            </CardHeader>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Salt Strengths</CardDescription>
              <CardTitle className="text-3xl font-bold text-orange-600">
                {Math.round(stats?.total_strengths || 0).toLocaleString()}
              </CardTitle>
            </CardHeader>
          </Card>
        </div>
      )}

      {/* Search and Tabs */}
      <Card>
        <CardContent className="pt-6">
          <form onSubmit={handleSearch} className="flex flex-col gap-4">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
              <input
                type="text"
                placeholder={`Search ${activeTab === "salts" ? "salts (APIs)" : "brands"}...`}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
            </div>

            <div className="flex gap-2 items-center">
              <Button type="submit" variant="outline">
                Search
              </Button>
              {activeTab === "brands" && (
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
              )}
            </div>
          </form>
        </CardContent>
      </Card>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={handleTabChange}>
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="manufacturers" className="flex items-center gap-2">
            <Building2 className="h-4 w-4" />
            Manufacturers
          </TabsTrigger>
          <TabsTrigger value="salts" className="flex items-center gap-2">
            <Beaker className="h-4 w-4" />
            Salts (APIs)
          </TabsTrigger>
          <TabsTrigger value="brands" className="flex items-center gap-2">
            <Package className="h-4 w-4" />
            Brands
          </TabsTrigger>
        </TabsList>

        {/* Manufacturers Tab */}
        <TabsContent value="manufacturers">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle>Pharmaceutical Companies</CardTitle>
                <CardDescription>
                  {manufacturersData?.length || 0} total manufacturers
                </CardDescription>
              </div>
              <Button onClick={() => setShowCreateManufacturer(true)}>
                <Plus className="h-4 w-4 mr-2" />
                Add Manufacturer
              </Button>
            </CardHeader>
            <CardContent>
              {manufacturersLoading ? (
                <div className="flex justify-center py-8">
                  <Loader2 className="h-6 w-6 animate-spin" />
                </div>
              ) : manufacturersError ? (
                <div className="text-center py-8 text-destructive">
                  Error loading manufacturers: {(manufacturersError as Error).message}
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Name</TableHead>
                      <TableHead>Country</TableHead>
                      <TableHead>License Number</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {manufacturersData?.map((manufacturer: any) => (
                      <TableRow key={manufacturer.manufacturer_id}>
                        <TableCell className="font-medium">
                          <div className="flex items-center gap-2">
                            <Building2 className="h-4 w-4 text-muted-foreground" />
                            {manufacturer.manufacturer_name}
                          </div>
                        </TableCell>
                        <TableCell>{manufacturer.country || "—"}</TableCell>
                        <TableCell className="font-mono text-sm">{manufacturer.license_number || "—"}</TableCell>
                        <TableCell>
                          <Badge variant={manufacturer.is_active ? "default" : "secondary"}>
                            {manufacturer.is_active ? "Active" : "Inactive"}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-right">
                          <div className="flex justify-end gap-2">
                            <Button variant="ghost" size="sm" onClick={() => handleEditManufacturer(manufacturer)}>
                              <Edit className="h-4 w-4" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleDeleteManufacturer(manufacturer.manufacturer_id, manufacturer.manufacturer_name)}
                            >
                              <Trash2 className="h-4 w-4 text-destructive" />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Salts Tab */}
        <TabsContent value="salts">
          <div className="mb-4 flex justify-end">
            <Button onClick={() => setShowCreateSalt(true)}>
              <Plus className="h-4 w-4 mr-2" />
              Add Salt
            </Button>
          </div>
          <SaltsTable
            salts={saltsData?.salts || []}
            total={saltsData?.total || 0}
            page={currentPage}
            pages={saltsData?.pages || 0}
            isLoading={saltsLoading}
            error={saltsError as Error}
            onPageChange={setCurrentPage}
            onViewSalt={handleViewSalt}
            onViewBrands={handleViewSaltBrands}
            onEditSalt={handleEditSalt}
            onDeleteSalt={handleDeleteSalt}
          />
        </TabsContent>

        {/* Brands Tab */}
        <TabsContent value="brands">
          <BrandsTable
            brands={brandsData?.brands || []}
            total={brandsData?.total || 0}
            page={currentPage}
            pages={brandsData?.pages || 0}
            isLoading={brandsLoading}
            error={brandsError as Error}
            onPageChange={setCurrentPage}
            onViewBrand={handleViewBrand}
            onViewAlternatives={handleViewBrandAlternatives}
          />
        </TabsContent>
      </Tabs>

      {/* Salt Details Dialog */}
      <Dialog open={showSaltDetails} onOpenChange={setShowSaltDetails}>
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Beaker className="h-5 w-5" />
              {selectedSalt?.salt_name}
            </DialogTitle>
            <DialogDescription>Active Pharmaceutical Ingredient Details</DialogDescription>
          </DialogHeader>
          {selectedSalt && <SaltDetailsView salt={selectedSalt} />}
        </DialogContent>
      </Dialog>

      {/* Salt Brands Dialog */}
      <Dialog open={showSaltBrands} onOpenChange={setShowSaltBrands}>
        <DialogContent className="max-w-3xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <List className="h-5 w-5" />
              Brands Available
            </DialogTitle>
            <DialogDescription>
              Commercial products containing this salt
            </DialogDescription>
          </DialogHeader>
          {saltBrands && <SaltBrandsView brands={saltBrands} />}
        </DialogContent>
      </Dialog>

      {/* Brand Details Dialog */}
      <Dialog open={showBrandDetails} onOpenChange={setShowBrandDetails}>
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Package className="h-5 w-5" />
              {selectedBrand?.brand_name}
            </DialogTitle>
            <DialogDescription>Commercial Medicine Details</DialogDescription>
          </DialogHeader>
          {selectedBrand && <BrandDetailsView brand={selectedBrand} />}
        </DialogContent>
      </Dialog>

      {/* Brand Alternatives Dialog */}
      <Dialog open={showBrandAlternatives} onOpenChange={setShowBrandAlternatives}>
        <DialogContent className="max-w-3xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <List className="h-5 w-5" />
              Alternative Brands
            </DialogTitle>
            <DialogDescription>
              Other brands with same composition
            </DialogDescription>
          </DialogHeader>
          {brandAlternatives && <BrandAlternativesView alternatives={brandAlternatives} />}
        </DialogContent>
      </Dialog>

      {/* Create Manufacturer Dialog */}
      <Dialog open={showCreateManufacturer} onOpenChange={setShowCreateManufacturer}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create New Manufacturer</DialogTitle>
            <DialogDescription>Add a new pharmaceutical company</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div>
              <Label htmlFor="manufacturer_name">Manufacturer Name *</Label>
              <Input
                id="manufacturer_name"
                value={manufacturerFormData.manufacturer_name}
                onChange={(e) => setManufacturerFormData({ ...manufacturerFormData, manufacturer_name: e.target.value })}
                placeholder="e.g., GSK Pharmaceuticals"
              />
            </div>
            <div>
              <Label htmlFor="country">Country</Label>
              <Input
                id="country"
                value={manufacturerFormData.country}
                onChange={(e) => setManufacturerFormData({ ...manufacturerFormData, country: e.target.value })}
                placeholder="e.g., India"
              />
            </div>
            <div>
              <Label htmlFor="license_number">License Number</Label>
              <Input
                id="license_number"
                value={manufacturerFormData.license_number}
                onChange={(e) => setManufacturerFormData({ ...manufacturerFormData, license_number: e.target.value })}
                placeholder="Optional"
              />
            </div>
            <div className="flex items-center space-x-2">
              <Checkbox
                id="is_active"
                checked={manufacturerFormData.is_active}
                onCheckedChange={(checked) =>
                  setManufacturerFormData({ ...manufacturerFormData, is_active: !!checked })
                }
              />
              <Label htmlFor="is_active">Active</Label>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCreateManufacturer(false)}>
              Cancel
            </Button>
            <Button onClick={handleCreateManufacturer} disabled={createManufacturerMutation.isPending}>
              {createManufacturerMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Create
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Manufacturer Dialog */}
      <Dialog open={showEditManufacturer} onOpenChange={setShowEditManufacturer}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit Manufacturer</DialogTitle>
            <DialogDescription>Update manufacturer information</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div>
              <Label htmlFor="edit_manufacturer_name">Manufacturer Name *</Label>
              <Input
                id="edit_manufacturer_name"
                value={manufacturerFormData.manufacturer_name}
                onChange={(e) => setManufacturerFormData({ ...manufacturerFormData, manufacturer_name: e.target.value })}
              />
            </div>
            <div>
              <Label htmlFor="edit_country">Country</Label>
              <Input
                id="edit_country"
                value={manufacturerFormData.country}
                onChange={(e) => setManufacturerFormData({ ...manufacturerFormData, country: e.target.value })}
              />
            </div>
            <div>
              <Label htmlFor="edit_license_number">License Number</Label>
              <Input
                id="edit_license_number"
                value={manufacturerFormData.license_number}
                onChange={(e) => setManufacturerFormData({ ...manufacturerFormData, license_number: e.target.value })}
              />
            </div>
            <div className="flex items-center space-x-2">
              <Checkbox
                id="edit_is_active"
                checked={manufacturerFormData.is_active}
                onCheckedChange={(checked) =>
                  setManufacturerFormData({ ...manufacturerFormData, is_active: !!checked })
                }
              />
              <Label htmlFor="edit_is_active">Active</Label>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowEditManufacturer(false)}>
              Cancel
            </Button>
            <Button onClick={handleUpdateManufacturer} disabled={updateManufacturerMutation.isPending}>
              {updateManufacturerMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Update
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Create Salt Dialog */}
      <Dialog open={showCreateSalt} onOpenChange={setShowCreateSalt}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create New Salt</DialogTitle>
            <DialogDescription>Add a new active pharmaceutical ingredient</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div>
              <Label htmlFor="salt_name">Salt Name *</Label>
              <Input
                id="salt_name"
                value={saltFormData.salt_name}
                onChange={(e) => setSaltFormData({ ...saltFormData, salt_name: e.target.value })}
                placeholder="e.g., Paracetamol"
              />
            </div>
            <div>
              <Label htmlFor="description">Description</Label>
              <Textarea
                id="description"
                value={saltFormData.description}
                onChange={(e) => setSaltFormData({ ...saltFormData, description: e.target.value })}
                placeholder="Optional description"
              />
            </div>
            <div>
              <Label htmlFor="chemical_formula">Chemical Formula</Label>
              <Input
                id="chemical_formula"
                value={saltFormData.chemical_formula}
                onChange={(e) => setSaltFormData({ ...saltFormData, chemical_formula: e.target.value })}
                placeholder="e.g., C8H9NO2"
              />
            </div>
            <div className="flex items-center space-x-2">
              <Checkbox
                id="prescription_required"
                checked={saltFormData.prescription_required}
                onCheckedChange={(checked) =>
                  setSaltFormData({ ...saltFormData, prescription_required: !!checked })
                }
              />
              <Label htmlFor="prescription_required">Prescription Required</Label>
            </div>
            <div className="flex items-center space-x-2">
              <Checkbox
                id="habit_forming"
                checked={saltFormData.habit_forming}
                onCheckedChange={(checked) =>
                  setSaltFormData({ ...saltFormData, habit_forming: !!checked })
                }
              />
              <Label htmlFor="habit_forming">Habit Forming</Label>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCreateSalt(false)}>
              Cancel
            </Button>
            <Button onClick={handleCreateSalt} disabled={createSaltMutation.isPending}>
              {createSaltMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Create
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Salt Dialog */}
      <Dialog open={showEditSalt} onOpenChange={setShowEditSalt}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit Salt</DialogTitle>
            <DialogDescription>Update salt information</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div>
              <Label htmlFor="edit_salt_name">Salt Name *</Label>
              <Input
                id="edit_salt_name"
                value={saltFormData.salt_name}
                onChange={(e) => setSaltFormData({ ...saltFormData, salt_name: e.target.value })}
              />
            </div>
            <div>
              <Label htmlFor="edit_description">Description</Label>
              <Textarea
                id="edit_description"
                value={saltFormData.description}
                onChange={(e) => setSaltFormData({ ...saltFormData, description: e.target.value })}
              />
            </div>
            <div>
              <Label htmlFor="edit_chemical_formula">Chemical Formula</Label>
              <Input
                id="edit_chemical_formula"
                value={saltFormData.chemical_formula}
                onChange={(e) => setSaltFormData({ ...saltFormData, chemical_formula: e.target.value })}
              />
            </div>
            <div className="flex items-center space-x-2">
              <Checkbox
                id="edit_prescription_required"
                checked={saltFormData.prescription_required}
                onCheckedChange={(checked) =>
                  setSaltFormData({ ...saltFormData, prescription_required: !!checked })
                }
              />
              <Label htmlFor="edit_prescription_required">Prescription Required</Label>
            </div>
            <div className="flex items-center space-x-2">
              <Checkbox
                id="edit_habit_forming"
                checked={saltFormData.habit_forming}
                onCheckedChange={(checked) =>
                  setSaltFormData({ ...saltFormData, habit_forming: !!checked })
                }
              />
              <Label htmlFor="edit_habit_forming">Habit Forming</Label>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowEditSalt(false)}>
              Cancel
            </Button>
            <Button onClick={handleUpdateSalt} disabled={updateSaltMutation.isPending}>
              {updateSaltMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Update
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

// Salt Details View Component
function SaltDetailsView({ salt }: { salt: Salt }) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <div>
          <p className="text-sm font-medium text-gray-500">Chemical Formula</p>
          <p className="text-sm text-gray-900">{salt.chemical_formula || "—"}</p>
        </div>
        <div>
          <p className="text-sm font-medium text-gray-500">Therapeutic Class</p>
          <p className="text-sm text-gray-900">
            {salt.therapeutic_class?.class_name || "—"}
          </p>
        </div>
        <div>
          <p className="text-sm font-medium text-gray-500">Chemical Class</p>
          <p className="text-sm text-gray-900">
            {salt.chemical_class?.class_name || "—"}
          </p>
        </div>
        <div>
          <p className="text-sm font-medium text-gray-500">Action Class</p>
          <p className="text-sm text-gray-900">
            {salt.action_class?.class_name || "—"}
          </p>
        </div>
      </div>

      <div className="border-t pt-4">
        <p className="text-sm font-medium text-gray-500 mb-2">Safety Information</p>
        <div className="flex flex-wrap gap-2">
          {salt.habit_forming && (
            <Badge variant="destructive">Habit Forming</Badge>
          )}
          {salt.prescription_required && (
            <Badge variant="secondary">Prescription Required</Badge>
          )}
          {salt.schedule && (
            <Badge variant="outline">Schedule: {salt.schedule}</Badge>
          )}
          {salt.pregnancy_category && (
            <Badge variant="outline">Pregnancy: {salt.pregnancy_category}</Badge>
          )}
          {salt.lactation_safe !== null && (
            <Badge variant={salt.lactation_safe ? "default" : "destructive"}>
              Lactation: {salt.lactation_safe ? "Safe" : "Not Safe"}
            </Badge>
          )}
        </div>
      </div>

      <div className="border-t pt-4">
        <p className="text-sm font-medium text-gray-500 mb-2">
          Available Strengths ({salt.strengths.length})
        </p>
        <div className="flex flex-wrap gap-2">
          {salt.strengths.map((strength) => (
            <Badge key={strength.salt_strength_id} variant="outline">
              {strength.display_strength}
              {strength.pediatric_approved && " (Pediatric)"}
            </Badge>
          ))}
        </div>
      </div>

      {salt.description && (
        <div className="border-t pt-4">
          <p className="text-sm font-medium text-gray-500 mb-2">Description</p>
          <p className="text-sm text-gray-900">{salt.description}</p>
        </div>
      )}
    </div>
  );
}

// Salt Brands View Component
function SaltBrandsView({ brands }: { brands: BrandForSalt[] }) {
  return (
    <div className="space-y-2">
      {brands.length === 0 ? (
        <p className="text-center text-gray-500 py-8">No brands found</p>
      ) : (
        <div className="space-y-2">
          {brands.map((brand) => (
            <div
              key={brand.id}
              className="p-3 border rounded-lg hover:bg-gray-50"
            >
              <div className="flex items-start justify-between">
                <div>
                  <p className="font-medium text-gray-900">{brand.name}</p>
                  <p className="text-sm text-gray-500">{brand.manufacturer}</p>
                  <p className="text-xs text-gray-400 mt-1">{brand.composition}</p>
                </div>
                {brand.is_discontinued && (
                  <Badge variant="secondary">Discontinued</Badge>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// Brand Details View Component
function BrandDetailsView({ brand }: { brand: Brand }) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <div>
          <p className="text-sm font-medium text-gray-500">Manufacturer</p>
          <p className="text-sm text-gray-900">
            {brand.manufacturer?.manufacturer_name || "—"}
          </p>
        </div>
        <div>
          <p className="text-sm font-medium text-gray-500">Drug Type</p>
          <p className="text-sm text-gray-900 capitalize">{brand.drug_type}</p>
        </div>
        <div>
          <p className="text-sm font-medium text-gray-500">Status</p>
          <Badge variant={brand.is_discontinued ? "secondary" : "default"}>
            {brand.is_discontinued ? "Discontinued" : "Active"}
          </Badge>
        </div>
        <div>
          <p className="text-sm font-medium text-gray-500">Launch Date</p>
          <p className="text-sm text-gray-900">
            {brand.launch_date
              ? new Date(brand.launch_date).toLocaleDateString()
              : "—"}
          </p>
        </div>
      </div>

      <div className="border-t pt-4">
        <p className="text-sm font-medium text-gray-500 mb-3">Composition</p>
        <div className="space-y-2">
          {brand.compositions.map((comp) => (
            <div
              key={comp.composition_id}
              className="flex items-center justify-between p-2 bg-gray-50 rounded"
            >
              <div>
                <p className="text-sm font-medium text-gray-900">
                  {comp.salt_name}
                </p>
                <p className="text-xs text-gray-500">Sequence: {comp.sequence}</p>
              </div>
              <Badge variant="outline">{comp.display_strength}</Badge>
            </div>
          ))}
        </div>
      </div>

      <div className="border-t pt-4">
        <p className="text-sm font-medium text-gray-500 mb-2">
          Full Composition String
        </p>
        <p className="text-sm text-gray-900 bg-gray-50 p-2 rounded">
          {brand.salt_composition}
        </p>
      </div>
    </div>
  );
}

// Brand Alternatives View Component
function BrandAlternativesView({ alternatives }: { alternatives: Brand[] }) {
  return (
    <div className="space-y-2">
      {alternatives.length === 0 ? (
        <p className="text-center text-gray-500 py-8">No alternatives found</p>
      ) : (
        <div className="space-y-2">
          {alternatives.map((brand) => (
            <div
              key={brand.brand_id}
              className="p-3 border rounded-lg hover:bg-gray-50"
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <p className="font-medium text-gray-900">{brand.brand_name}</p>
                  <p className="text-sm text-gray-500">
                    {brand.manufacturer?.manufacturer_name}
                  </p>
                  <p className="text-xs text-gray-400 mt-1">
                    {brand.salt_composition}
                  </p>
                </div>
                <div className="flex gap-2">
                  {brand.is_discontinued && (
                    <Badge variant="secondary">Discontinued</Badge>
                  )}
                  <Badge variant="outline">{brand.drug_type}</Badge>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// Salts Table Component (updated with handlers)
function SaltsTable({
  salts,
  total,
  page,
  pages,
  isLoading,
  error,
  onPageChange,
  onViewSalt,
  onViewBrands,
  onEditSalt,
  onDeleteSalt,
}: {
  salts: Salt[];
  total: number;
  page: number;
  pages: number;
  isLoading: boolean;
  error: Error | null;
  onPageChange: (page: number) => void;
  onViewSalt: (saltId: string) => void;
  onViewBrands: (saltId: string) => void;
  onEditSalt: (salt: Salt) => void;
  onDeleteSalt: (id: string, name: string) => void;
}) {
  if (error) {
    return (
      <Card className="border-red-200 bg-red-50">
        <CardContent className="pt-6">
          <div className="flex gap-3">
            <AlertCircle className="h-5 w-5 text-red-600 flex-shrink-0" />
            <div>
              <h3 className="text-sm font-medium text-red-900">Failed to load salts</h3>
              <p className="mt-1 text-sm text-red-700">{error.message}</p>
            </div>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Active Pharmaceutical Ingredients (APIs)</CardTitle>
        <CardDescription>
          {isLoading
            ? "Loading salts..."
            : `Showing ${salts.length} of ${total.toLocaleString()} salts`}
        </CardDescription>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-8 w-8 animate-spin text-primary-600" />
            <span className="ml-2 text-gray-600">Loading salts...</span>
          </div>
        ) : salts.length === 0 ? (
          <div className="text-center py-12">
            <Beaker className="mx-auto h-12 w-12 text-gray-400" />
            <h3 className="mt-2 text-sm font-medium text-gray-900">No salts found</h3>
            <p className="mt-1 text-sm text-gray-500">Try adjusting your search</p>
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b text-left text-sm text-gray-500">
                    <th className="pb-3 font-medium">Salt Name</th>
                    <th className="pb-3 font-medium">Therapeutic Class</th>
                    <th className="pb-3 font-medium">Strengths Available</th>
                    <th className="pb-3 font-medium">Safety</th>
                    <th className="pb-3 font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {salts.map((salt) => (
                    <tr key={salt.salt_id} className="border-b last:border-0">
                      <td className="py-4">
                        <div className="flex items-center gap-3">
                          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-50">
                            <Beaker className="h-5 w-5 text-blue-600" />
                          </div>
                          <div>
                            <p className="font-medium text-gray-900">{salt.salt_name}</p>
                            {salt.chemical_formula && (
                              <p className="text-xs text-gray-500">{salt.chemical_formula}</p>
                            )}
                          </div>
                        </div>
                      </td>
                      <td className="py-4">
                        {salt.therapeutic_class ? (
                          <Badge variant="outline">{salt.therapeutic_class.class_name}</Badge>
                        ) : (
                          <span className="text-gray-400 text-xs">—</span>
                        )}
                      </td>
                      <td className="py-4">
                        <span className="text-sm text-gray-600">
                          {salt.strengths.length} strength{salt.strengths.length !== 1 ? "s" : ""}
                        </span>
                        {salt.strengths.length > 0 && (
                          <div className="text-xs text-gray-400 mt-1">
                            {salt.strengths.slice(0, 3).map((s) => s.display_strength).join(", ")}
                            {salt.strengths.length > 3 && " ..."}
                          </div>
                        )}
                      </td>
                      <td className="py-4">
                        <div className="flex flex-col gap-1">
                          {salt.habit_forming && (
                            <Badge variant="destructive" className="text-xs">
                              Habit Forming
                            </Badge>
                          )}
                          {salt.pregnancy_category && (
                            <Badge variant="secondary" className="text-xs">
                              Pregnancy: {salt.pregnancy_category}
                            </Badge>
                          )}
                        </div>
                      </td>
                      <td className="py-4">
                        <div className="flex gap-2">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => onViewSalt(salt.salt_id)}
                          >
                            <Info className="h-4 w-4 mr-1" />
                            View
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => onViewBrands(salt.salt_id)}
                          >
                            <List className="h-4 w-4 mr-1" />
                            Brands
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => onEditSalt(salt)}
                          >
                            <Edit className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => onDeleteSalt(salt.salt_id, salt.salt_name)}
                          >
                            <Trash2 className="h-4 w-4 text-destructive" />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            <Pagination
              page={page}
              pages={pages}
              total={total}
              limit={50}
              onPageChange={onPageChange}
            />
          </>
        )}
      </CardContent>
    </Card>
  );
}

// Brands Table Component (updated with handlers)
function BrandsTable({
  brands,
  total,
  page,
  pages,
  isLoading,
  error,
  onPageChange,
  onViewBrand,
  onViewAlternatives,
}: {
  brands: Brand[];
  total: number;
  page: number;
  pages: number;
  isLoading: boolean;
  error: Error | null;
  onPageChange: (page: number) => void;
  onViewBrand: (brandId: string) => void;
  onViewAlternatives: (brandId: string) => void;
}) {
  if (error) {
    return (
      <Card className="border-red-200 bg-red-50">
        <CardContent className="pt-6">
          <div className="flex gap-3">
            <AlertCircle className="h-5 w-5 text-red-600 flex-shrink-0" />
            <div>
              <h3 className="text-sm font-medium text-red-900">Failed to load brands</h3>
              <p className="mt-1 text-sm text-red-700">{error.message}</p>
            </div>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Commercial Medicines (Brands)</CardTitle>
        <CardDescription>
          {isLoading
            ? "Loading brands..."
            : `Showing ${brands.length} of ${total.toLocaleString()} brands`}
        </CardDescription>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-8 w-8 animate-spin text-primary-600" />
            <span className="ml-2 text-gray-600">Loading brands...</span>
          </div>
        ) : brands.length === 0 ? (
          <div className="text-center py-12">
            <Package className="mx-auto h-12 w-12 text-gray-400" />
            <h3 className="mt-2 text-sm font-medium text-gray-900">No brands found</h3>
            <p className="mt-1 text-sm text-gray-500">Try adjusting your search</p>
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b text-left text-sm text-gray-500">
                    <th className="pb-3 font-medium">Brand Name</th>
                    <th className="pb-3 font-medium">Manufacturer</th>
                    <th className="pb-3 font-medium">Composition</th>
                    <th className="pb-3 font-medium">Status</th>
                    <th className="pb-3 font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {brands.map((brand) => (
                    <tr key={brand.brand_id} className="border-b last:border-0">
                      <td className="py-4">
                        <div className="flex items-center gap-3">
                          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-green-50">
                            <Package className="h-5 w-5 text-green-600" />
                          </div>
                          <div>
                            <p className="font-medium text-gray-900">{brand.brand_name}</p>
                            <p className="text-xs text-gray-500">{brand.drug_type}</p>
                          </div>
                        </div>
                      </td>
                      <td className="py-4 text-sm text-gray-600">
                        {brand.manufacturer?.manufacturer_name || "—"}
                      </td>
                      <td className="py-4 text-sm text-gray-600 max-w-xs">
                        <div className="truncate" title={brand.salt_composition}>
                          {brand.salt_composition || "—"}
                        </div>
                      </td>
                      <td className="py-4">
                        <Badge
                          variant={brand.is_discontinued ? "secondary" : "default"}
                          className={
                            brand.is_discontinued
                              ? "bg-gray-100 text-gray-700"
                              : "bg-green-50 text-green-700"
                          }
                        >
                          {brand.is_discontinued ? "Discontinued" : "Active"}
                        </Badge>
                      </td>
                      <td className="py-4">
                        <div className="flex gap-2">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => onViewBrand(brand.brand_id)}
                          >
                            <Info className="h-4 w-4 mr-1" />
                            View
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => onViewAlternatives(brand.brand_id)}
                          >
                            <List className="h-4 w-4 mr-1" />
                            Alternatives
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            <Pagination
              page={page}
              pages={pages}
              total={total}
              limit={50}
              onPageChange={onPageChange}
            />
          </>
        )}
      </CardContent>
    </Card>
  );
}

// Pagination Component
function Pagination({
  page,
  pages,
  total,
  limit,
  onPageChange,
}: {
  page: number;
  pages: number;
  total: number;
  limit: number;
  onPageChange: (page: number) => void;
}) {
  return (
    <div className="mt-4 flex items-center justify-between">
      <p className="text-sm text-gray-500">
        Showing {(page - 1) * limit + 1}-{Math.min(page * limit, total)} of{" "}
        {total.toLocaleString()}
      </p>
      <div className="flex gap-2">
        <Button
          variant="outline"
          size="sm"
          disabled={page === 1}
          onClick={() => onPageChange(page - 1)}
        >
          Previous
        </Button>
        <span className="flex items-center px-3 text-sm text-gray-600">
          Page {page} of {pages}
        </span>
        <Button
          variant="outline"
          size="sm"
          disabled={page >= pages}
          onClick={() => onPageChange(page + 1)}
        >
          Next
        </Button>
      </div>
    </div>
  );
}
