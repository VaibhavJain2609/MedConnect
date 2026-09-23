"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
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
  listSalts,
  createSalt,
  updateSalt,
  deleteSalt,
  getApiErrorMessage,
} from "@/lib/api/medicines-emr";

export default function AdminSaltsPage() {
  const t = useTranslations("adminSalts");
  const tCommon = useTranslations("common");
  const tPagination = useTranslations("pagination");
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [searchQuery, setSearchQuery] = useState("");
  const [page, setPage] = useState(1);
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [showEditDialog, setShowEditDialog] = useState(false);
  const [editingSalt, setEditingSalt] = useState<any>(null);
  const [deletingSalt, setDeletingSalt] = useState<{ id: string; name: string } | null>(null);
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
    queryFn: () => listSalts({ search: searchQuery || undefined, page, limit: 50 }),
    staleTime: 30000,
  });

  // Create mutation
  const createMutation = useMutation({
    mutationFn: createSalt,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-salts-list"] });
      setShowCreateDialog(false);
      resetForm();
      toast({ title: t("toasts.created"), description: t("toasts.createdDesc") });
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
    mutationFn: ({ id, data }: { id: string; data: any }) => updateSalt(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-salts-list"] });
      setShowEditDialog(false);
      setEditingSalt(null);
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
    mutationFn: deleteSalt,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-salts-list"] });
      setDeletingSalt(null);
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
    setDeletingSalt({ id, name });
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
          {t("addSalt")}
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{t("listTitle")}</CardTitle>
          <CardDescription>
            {t("totalCount", { count: data?.total || 0 })}
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
                  <TableHead>{t("table.saltName")}</TableHead>
                  <TableHead>{t("table.description")}</TableHead>
                  <TableHead>{t("table.strengths")}</TableHead>
                  <TableHead>{t("table.properties")}</TableHead>
                  <TableHead className="text-right">{t("table.actions")}</TableHead>
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
                        {salt.prescription_required && <Badge variant="outline">{t("rxBadge")}</Badge>}
                        {salt.habit_forming && <Badge variant="destructive">{t("habitBadge")}</Badge>}
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
                {tPagination("previous")}
              </Button>
              <span>{tPagination("pageOf", { page, totalPages: data.pages })}</span>
              <Button
                variant="outline"
                onClick={() => setPage(p => Math.min(data.pages, p + 1))}
                disabled={page === data.pages}
              >
                {tPagination("next")}
              </Button>
            </div>
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
              <Label htmlFor="salt_name">{t("form.saltName")}</Label>
              <Input
                id="salt_name"
                value={formData.salt_name}
                onChange={(e) => setFormData({ ...formData, salt_name: e.target.value })}
                placeholder={t("form.saltNamePlaceholder")}
              />
            </div>
            <div>
              <Label htmlFor="description">{t("form.description")}</Label>
              <Textarea
                id="description"
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                placeholder={t("form.descriptionPlaceholder")}
              />
            </div>
            <div>
              <Label htmlFor="chemical_formula">{t("form.chemicalFormula")}</Label>
              <Input
                id="chemical_formula"
                value={formData.chemical_formula}
                onChange={(e) => setFormData({ ...formData, chemical_formula: e.target.value })}
                placeholder={t("form.formulaPlaceholder")}
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
              <Label htmlFor="prescription_required">{t("form.prescriptionRequired")}</Label>
            </div>
            <div className="flex items-center space-x-2">
              <Checkbox
                id="habit_forming"
                checked={formData.habit_forming}
                onCheckedChange={(checked) =>
                  setFormData({ ...formData, habit_forming: !!checked })
                }
              />
              <Label htmlFor="habit_forming">{t("form.habitForming")}</Label>
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
              <Label htmlFor="edit_salt_name">{t("form.saltName")}</Label>
              <Input
                id="edit_salt_name"
                value={formData.salt_name}
                onChange={(e) => setFormData({ ...formData, salt_name: e.target.value })}
              />
            </div>
            <div>
              <Label htmlFor="edit_description">{t("form.description")}</Label>
              <Textarea
                id="edit_description"
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              />
            </div>
            <div>
              <Label htmlFor="edit_chemical_formula">{t("form.chemicalFormula")}</Label>
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
              <Label htmlFor="edit_prescription_required">{t("form.prescriptionRequired")}</Label>
            </div>
            <div className="flex items-center space-x-2">
              <Checkbox
                id="edit_habit_forming"
                checked={formData.habit_forming}
                onCheckedChange={(checked) =>
                  setFormData({ ...formData, habit_forming: !!checked })
                }
              />
              <Label htmlFor="edit_habit_forming">{t("form.habitForming")}</Label>
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
        open={!!deletingSalt}
        onOpenChange={(open) => !open && setDeletingSalt(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t("deleteDialog.title")}</AlertDialogTitle>
            <AlertDialogDescription>
              {t("deleteDialog.desc", { name: deletingSalt?.name ?? "" })}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{tCommon("cancel")}</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => deletingSalt && deleteMutation.mutate(deletingSalt.id)}
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
