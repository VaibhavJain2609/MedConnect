"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Search, Plus, Trash2, Edit, Loader2, Building2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";

// API functions
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

export default function AdminManufacturersPage() {
  const queryClient = useQueryClient();
  const [searchQuery, setSearchQuery] = useState("");
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [showEditDialog, setShowEditDialog] = useState(false);
  const [editingManufacturer, setEditingManufacturer] = useState<any>(null);
  const [formData, setFormData] = useState({
    manufacturer_name: "",
    country: "",
    license_number: "",
    is_active: true,
  });

  // Fetch manufacturers
  const { data, isLoading, error } = useQuery({
    queryKey: ["admin-manufacturers-list", searchQuery],
    queryFn: () => listManufacturers({ search: searchQuery || undefined }),
    staleTime: 30000,
  });

  // Create mutation
  const createMutation = useMutation({
    mutationFn: createManufacturer,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-manufacturers-list"] });
      setShowCreateDialog(false);
      resetForm();
    },
  });

  // Update mutation
  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) => updateManufacturer(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-manufacturers-list"] });
      setShowEditDialog(false);
      setEditingManufacturer(null);
      resetForm();
    },
  });

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: deleteManufacturer,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-manufacturers-list"] });
    },
  });

  const resetForm = () => {
    setFormData({
      manufacturer_name: "",
      country: "",
      license_number: "",
      is_active: true,
    });
  };

  const handleCreate = () => {
    createMutation.mutate(formData);
  };

  const handleEdit = (manufacturer: any) => {
    setEditingManufacturer(manufacturer);
    setFormData({
      manufacturer_name: manufacturer.manufacturer_name,
      country: manufacturer.country || "",
      license_number: manufacturer.license_number || "",
      is_active: manufacturer.is_active,
    });
    setShowEditDialog(true);
  };

  const handleUpdate = () => {
    if (!editingManufacturer) return;
    updateMutation.mutate({ id: editingManufacturer.manufacturer_id, data: formData });
  };

  const handleDelete = (id: string, name: string) => {
    if (confirm(`Delete manufacturer "${name}"? This will fail if the manufacturer has any brands.`)) {
      deleteMutation.mutate(id);
    }
  };

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Manufacturers Management</h1>
          <p className="text-muted-foreground">Manage pharmaceutical companies</p>
        </div>
        <Button onClick={() => setShowCreateDialog(true)}>
          <Plus className="h-4 w-4 mr-2" />
          Add Manufacturer
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Manufacturers List</CardTitle>
          <CardDescription>
            {data?.length || 0} total manufacturers
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Search */}
          <div className="flex gap-2">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search manufacturers..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9"
              />
            </div>
          </div>

          {/* Table */}
          {isLoading ? (
            <div className="flex justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin" />
            </div>
          ) : error ? (
            <div className="text-center py-8 text-destructive">
              Error loading manufacturers: {(error as Error).message}
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
                {data?.map((manufacturer: any) => (
                  <TableRow key={manufacturer.manufacturer_id}>
                    <TableCell className="font-medium">
                      <div className="flex items-center gap-2">
                        <Building2 className="h-4 w-4 text-muted-foreground" />
                        {manufacturer.manufacturer_name}
                      </div>
                    </TableCell>
                    <TableCell>{manufacturer.country || "-"}</TableCell>
                    <TableCell className="font-mono text-sm">{manufacturer.license_number || "-"}</TableCell>
                    <TableCell>
                      <Badge variant={manufacturer.is_active ? "default" : "secondary"}>
                        {manufacturer.is_active ? "Active" : "Inactive"}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-2">
                        <Button variant="ghost" size="sm" onClick={() => handleEdit(manufacturer)}>
                          <Edit className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDelete(manufacturer.manufacturer_id, manufacturer.manufacturer_name)}
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

      {/* Create Dialog */}
      <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
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
                value={formData.manufacturer_name}
                onChange={(e) => setFormData({ ...formData, manufacturer_name: e.target.value })}
                placeholder="e.g., GSK Pharmaceuticals"
              />
            </div>
            <div>
              <Label htmlFor="country">Country</Label>
              <Input
                id="country"
                value={formData.country}
                onChange={(e) => setFormData({ ...formData, country: e.target.value })}
                placeholder="e.g., India"
              />
            </div>
            <div>
              <Label htmlFor="license_number">License Number</Label>
              <Input
                id="license_number"
                value={formData.license_number}
                onChange={(e) => setFormData({ ...formData, license_number: e.target.value })}
                placeholder="Optional"
              />
            </div>
            <div className="flex items-center space-x-2">
              <Checkbox
                id="is_active"
                checked={formData.is_active}
                onCheckedChange={(checked) =>
                  setFormData({ ...formData, is_active: !!checked })
                }
              />
              <Label htmlFor="is_active">Active</Label>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCreateDialog(false)}>
              Cancel
            </Button>
            <Button onClick={handleCreate} disabled={createMutation.isPending}>
              {createMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Create
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Dialog */}
      <Dialog open={showEditDialog} onOpenChange={setShowEditDialog}>
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
                value={formData.manufacturer_name}
                onChange={(e) => setFormData({ ...formData, manufacturer_name: e.target.value })}
              />
            </div>
            <div>
              <Label htmlFor="edit_country">Country</Label>
              <Input
                id="edit_country"
                value={formData.country}
                onChange={(e) => setFormData({ ...formData, country: e.target.value })}
              />
            </div>
            <div>
              <Label htmlFor="edit_license_number">License Number</Label>
              <Input
                id="edit_license_number"
                value={formData.license_number}
                onChange={(e) => setFormData({ ...formData, license_number: e.target.value })}
              />
            </div>
            <div className="flex items-center space-x-2">
              <Checkbox
                id="edit_is_active"
                checked={formData.is_active}
                onCheckedChange={(checked) =>
                  setFormData({ ...formData, is_active: !!checked })
                }
              />
              <Label htmlFor="edit_is_active">Active</Label>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowEditDialog(false)}>
              Cancel
            </Button>
            <Button onClick={handleUpdate} disabled={updateMutation.isPending}>
              {updateMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Update
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
