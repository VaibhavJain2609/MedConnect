"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Search, Plus, Trash2, Edit, Loader2 } from "lucide-react";
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
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";

// API functions
async function listSalts(params: { search?: string; page?: number }) {
  const queryParams = new URLSearchParams();
  if (params.search) queryParams.append("search", params.search);
  if (params.page) queryParams.append("page", params.page.toString());
  queryParams.append("limit", "50");

  const res = await fetch(`/api/v1/salts?${queryParams}`);
  if (!res.ok) throw new Error("Failed to fetch salts");
  return res.json();
}

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

export default function AdminSaltsPage() {
  const queryClient = useQueryClient();
  const [searchQuery, setSearchQuery] = useState("");
  const [page, setPage] = useState(1);
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [showEditDialog, setShowEditDialog] = useState(false);
  const [editingSalt, setEditingSalt] = useState<any>(null);
  const [formData, setFormData] = useState({
    salt_name: "",
    description: "",
    chemical_formula: "",
    habit_forming: false,
    prescription_required: true,
    pregnancy_category: "",
  });

  // Fetch salts
  const { data, isLoading, error } = useQuery({
    queryKey: ["admin-salts-list", searchQuery, page],
    queryFn: () => listSalts({ search: searchQuery || undefined, page }),
    staleTime: 30000,
  });

  // Create mutation
  const createMutation = useMutation({
    mutationFn: createSalt,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-salts-list"] });
      setShowCreateDialog(false);
      resetForm();
    },
  });

  // Update mutation
  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) => updateSalt(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-salts-list"] });
      setShowEditDialog(false);
      setEditingSalt(null);
      resetForm();
    },
  });

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: deleteSalt,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-salts-list"] });
    },
  });

  const resetForm = () => {
    setFormData({
      salt_name: "",
      description: "",
      chemical_formula: "",
      habit_forming: false,
      prescription_required: true,
      pregnancy_category: "",
    });
  };

  const handleCreate = () => {
    createMutation.mutate(formData);
  };

  const handleEdit = (salt: any) => {
    setEditingSalt(salt);
    setFormData({
      salt_name: salt.salt_name,
      description: salt.description || "",
      chemical_formula: salt.chemical_formula || "",
      habit_forming: salt.habit_forming,
      prescription_required: salt.prescription_required,
      pregnancy_category: salt.pregnancy_category || "",
    });
    setShowEditDialog(true);
  };

  const handleUpdate = () => {
    if (!editingSalt) return;
    updateMutation.mutate({ id: editingSalt.salt_id, data: formData });
  };

  const handleDelete = (id: string, name: string) => {
    if (confirm(`Delete salt "${name}"? This will fail if the salt has any strengths.`)) {
      deleteMutation.mutate(id);
    }
  };

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Salts Management</h1>
          <p className="text-muted-foreground">Manage active pharmaceutical ingredients (APIs)</p>
        </div>
        <Button onClick={() => setShowCreateDialog(true)}>
          <Plus className="h-4 w-4 mr-2" />
          Add Salt
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Salts List</CardTitle>
          <CardDescription>
            {data?.total || 0} total salts
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Search */}
          <div className="flex gap-2">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search salts..."
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
              Error loading salts: {(error as Error).message}
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Salt Name</TableHead>
                  <TableHead>Description</TableHead>
                  <TableHead>Strengths</TableHead>
                  <TableHead>Properties</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data?.salts?.map((salt: any) => (
                  <TableRow key={salt.salt_id}>
                    <TableCell className="font-medium">{salt.salt_name}</TableCell>
                    <TableCell className="max-w-xs truncate">{salt.description}</TableCell>
                    <TableCell>{salt.strengths?.length || 0}</TableCell>
                    <TableCell>
                      <div className="flex gap-1">
                        {salt.prescription_required && <Badge variant="outline">Rx</Badge>}
                        {salt.habit_forming && <Badge variant="destructive">Habit</Badge>}
                      </div>
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-2">
                        <Button variant="ghost" size="sm" onClick={() => handleEdit(salt)}>
                          <Edit className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDelete(salt.salt_id, salt.salt_name)}
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

          {/* Pagination */}
          {data && data.pages > 1 && (
            <div className="flex justify-between items-center">
              <Button
                variant="outline"
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page === 1}
              >
                Previous
              </Button>
              <span>Page {page} of {data.pages}</span>
              <Button
                variant="outline"
                onClick={() => setPage(p => Math.min(data.pages, p + 1))}
                disabled={page === data.pages}
              >
                Next
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Create Dialog */}
      <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
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
                value={formData.salt_name}
                onChange={(e) => setFormData({ ...formData, salt_name: e.target.value })}
                placeholder="e.g., Paracetamol"
              />
            </div>
            <div>
              <Label htmlFor="description">Description</Label>
              <Textarea
                id="description"
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                placeholder="Optional description"
              />
            </div>
            <div>
              <Label htmlFor="chemical_formula">Chemical Formula</Label>
              <Input
                id="chemical_formula"
                value={formData.chemical_formula}
                onChange={(e) => setFormData({ ...formData, chemical_formula: e.target.value })}
                placeholder="e.g., C8H9NO2"
              />
            </div>
            <div className="flex items-center space-x-2">
              <Checkbox
                id="prescription_required"
                checked={formData.prescription_required}
                onCheckedChange={(checked) =>
                  setFormData({ ...formData, prescription_required: !!checked })
                }
              />
              <Label htmlFor="prescription_required">Prescription Required</Label>
            </div>
            <div className="flex items-center space-x-2">
              <Checkbox
                id="habit_forming"
                checked={formData.habit_forming}
                onCheckedChange={(checked) =>
                  setFormData({ ...formData, habit_forming: !!checked })
                }
              />
              <Label htmlFor="habit_forming">Habit Forming</Label>
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
            <DialogTitle>Edit Salt</DialogTitle>
            <DialogDescription>Update salt information</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div>
              <Label htmlFor="edit_salt_name">Salt Name *</Label>
              <Input
                id="edit_salt_name"
                value={formData.salt_name}
                onChange={(e) => setFormData({ ...formData, salt_name: e.target.value })}
              />
            </div>
            <div>
              <Label htmlFor="edit_description">Description</Label>
              <Textarea
                id="edit_description"
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              />
            </div>
            <div>
              <Label htmlFor="edit_chemical_formula">Chemical Formula</Label>
              <Input
                id="edit_chemical_formula"
                value={formData.chemical_formula}
                onChange={(e) => setFormData({ ...formData, chemical_formula: e.target.value })}
              />
            </div>
            <div className="flex items-center space-x-2">
              <Checkbox
                id="edit_prescription_required"
                checked={formData.prescription_required}
                onCheckedChange={(checked) =>
                  setFormData({ ...formData, prescription_required: !!checked })
                }
              />
              <Label htmlFor="edit_prescription_required">Prescription Required</Label>
            </div>
            <div className="flex items-center space-x-2">
              <Checkbox
                id="edit_habit_forming"
                checked={formData.habit_forming}
                onCheckedChange={(checked) =>
                  setFormData({ ...formData, habit_forming: !!checked })
                }
              />
              <Label htmlFor="edit_habit_forming">Habit Forming</Label>
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
