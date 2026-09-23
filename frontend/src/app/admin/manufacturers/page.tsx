"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
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
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { useToast } from "@/hooks/use-toast";
import {
  listManufacturers,
  createManufacturer,
  updateManufacturer,
  deleteManufacturer,
  getApiErrorMessage,
} from "@/lib/api/medicines-emr";

export default function AdminManufacturersPage() {
  const t = useTranslations("adminManufacturers");
  const tCommon = useTranslations("common");
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [searchQuery, setSearchQuery] = useState("");
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [showEditDialog, setShowEditDialog] = useState(false);
  const [editingManufacturer, setEditingManufacturer] = useState<any>(null);
  const [deletingManufacturer, setDeletingManufacturer] = useState<{ id: string; name: string } | null>(null);
  const [formData, setFormData] = useState({
    manufacturer_name: "",
    country: "",
    license_number: "",
    is_active: true,
  });

  // Fetch manufacturers
  const { data, isLoading, error } = useQuery({
    queryKey: ["admin-manufacturers-list", searchQuery],
    queryFn: () => listManufacturers(searchQuery || undefined, undefined, 50, 0),
    staleTime: 30000,
  });

  // Create mutation
  const createMutation = useMutation({
    mutationFn: createManufacturer,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-manufacturers-list"] });
      setShowCreateDialog(false);
      resetForm();
      toast({ title: t("toasts.created") });
    },
    onError: (err) => {
      toast({
        title: t("toasts.createFailed"),
        description: getApiErrorMessage(err),
        variant: "destructive",
      });
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
      toast({ title: t("toasts.updated") });
    },
    onError: (err) => {
      toast({
        title: t("toasts.updateFailed"),
        description: getApiErrorMessage(err),
        variant: "destructive",
      });
    },
  });

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: deleteManufacturer,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-manufacturers-list"] });
      setDeletingManufacturer(null);
      toast({ title: t("toasts.deleted") });
    },
    onError: (err) => {
      toast({
        title: t("toasts.deleteFailed"),
        description: getApiErrorMessage(err),
        variant: "destructive",
      });
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
    setDeletingManufacturer({ id, name });
  };

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">{t("title")}</h1>
          <p className="text-muted-foreground">{t("subtitle")}</p>
        </div>
        <Button onClick={() => setShowCreateDialog(true)}>
          <Plus className="h-4 w-4 mr-2" />
          {t("addManufacturer")}
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{t("listTitle")}</CardTitle>
          <CardDescription>
            {t("totalCount", { count: data?.length || 0 })}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Search */}
          <div className="flex gap-2">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder={t("searchPlaceholder")}
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
              {t("loadError", { message: (error as Error).message })}
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("table.name")}</TableHead>
                  <TableHead>{t("table.country")}</TableHead>
                  <TableHead>{t("table.licenseNumber")}</TableHead>
                  <TableHead>{t("table.status")}</TableHead>
                  <TableHead className="text-right">{t("table.actions")}</TableHead>
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
                        {manufacturer.is_active ? t("active") : t("inactive")}
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
            <DialogTitle>{t("createDialog.title")}</DialogTitle>
            <DialogDescription>{t("createDialog.desc")}</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div>
              <Label htmlFor="manufacturer_name">{t("form.name")}</Label>
              <Input
                id="manufacturer_name"
                value={formData.manufacturer_name}
                onChange={(e) => setFormData({ ...formData, manufacturer_name: e.target.value })}
                placeholder={t("form.namePlaceholder")}
              />
            </div>
            <div>
              <Label htmlFor="country">{t("form.country")}</Label>
              <Input
                id="country"
                value={formData.country}
                onChange={(e) => setFormData({ ...formData, country: e.target.value })}
                placeholder={t("form.countryPlaceholder")}
              />
            </div>
            <div>
              <Label htmlFor="license_number">{t("form.licenseNumber")}</Label>
              <Input
                id="license_number"
                value={formData.license_number}
                onChange={(e) => setFormData({ ...formData, license_number: e.target.value })}
                placeholder={t("form.licensePlaceholder")}
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
              <Label htmlFor="is_active">{t("form.active")}</Label>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCreateDialog(false)}>
              {tCommon("cancel")}
            </Button>
            <Button onClick={handleCreate} disabled={createMutation.isPending}>
              {createMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {t("create")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Dialog */}
      <Dialog open={showEditDialog} onOpenChange={setShowEditDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("editDialog.title")}</DialogTitle>
            <DialogDescription>{t("editDialog.desc")}</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div>
              <Label htmlFor="edit_manufacturer_name">{t("form.name")}</Label>
              <Input
                id="edit_manufacturer_name"
                value={formData.manufacturer_name}
                onChange={(e) => setFormData({ ...formData, manufacturer_name: e.target.value })}
              />
            </div>
            <div>
              <Label htmlFor="edit_country">{t("form.country")}</Label>
              <Input
                id="edit_country"
                value={formData.country}
                onChange={(e) => setFormData({ ...formData, country: e.target.value })}
              />
            </div>
            <div>
              <Label htmlFor="edit_license_number">{t("form.licenseNumber")}</Label>
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
              <Label htmlFor="edit_is_active">{t("form.active")}</Label>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowEditDialog(false)}>
              {tCommon("cancel")}
            </Button>
            <Button onClick={handleUpdate} disabled={updateMutation.isPending}>
              {updateMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {t("update")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation */}
      <AlertDialog
        open={!!deletingManufacturer}
        onOpenChange={(open) => !open && setDeletingManufacturer(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t("deleteDialog.title")}</AlertDialogTitle>
            <AlertDialogDescription>
              {t("deleteDialog.desc", { name: deletingManufacturer?.name ?? "" })}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{tCommon("cancel")}</AlertDialogCancel>
            <AlertDialogAction
              onClick={() =>
                deletingManufacturer && deleteMutation.mutate(deletingManufacturer.id)
              }
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              disabled={deleteMutation.isPending}
            >
              {deleteMutation.isPending ? t("deleteDialog.deleting") : t("deleteDialog.confirm")}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
