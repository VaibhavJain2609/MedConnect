"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { Breadcrumb } from "@/components/ui/breadcrumb";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
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
import {
  listFamilyMembers,
  createFamilyMember,
  updateFamilyMember,
  deleteFamilyMember,
  FAMILY_RELATIONSHIPS,
  type FamilyMember,
  type FamilyRelationship,
} from "@/lib/api/family";
import { Pencil, Trash2, UserPlus, Users } from "lucide-react";

const BLOOD_GROUPS = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"];
const GENDERS = ["male", "female", "other"] as const;
type Gender = (typeof GENDERS)[number];

interface MemberFormState {
  full_name: string;
  dob: string;
  relationship: FamilyRelationship;
  gender: string;
  blood_group: string;
  notes: string;
}

const EMPTY_FORM: MemberFormState = {
  full_name: "",
  dob: "",
  relationship: "child",
  gender: "",
  blood_group: "",
  notes: "",
};

export default function FamilyMembersPage() {
  const t = useTranslations("family");
  const queryClient = useQueryClient();

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<FamilyMember | null>(null);
  const [form, setForm] = useState<MemberFormState>(EMPTY_FORM);
  const [formError, setFormError] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<FamilyMember | null>(null);

  const { data: members = [], isLoading, isError } = useQuery({
    queryKey: ["family-members"],
    queryFn: listFamilyMembers,
  });

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ["family-members"] });

  const saveMutation = useMutation({
    mutationFn: async () => {
      const payload = {
        full_name: form.full_name.trim(),
        dob: form.dob,
        relationship: form.relationship,
        gender: form.gender || null,
        blood_group: form.blood_group || null,
        notes: form.notes.trim() || null,
      };
      if (editing) {
        return updateFamilyMember(editing.member_id, payload);
      }
      return createFamilyMember(payload);
    },
    onSuccess: () => {
      invalidate();
      setDialogOpen(false);
      setEditing(null);
      setForm(EMPTY_FORM);
      setFormError("");
    },
    onError: () => setFormError(t("saveError")),
  });

  const deleteMutation = useMutation({
    mutationFn: (memberId: string) => deleteFamilyMember(memberId),
    onSuccess: () => {
      invalidate();
      setDeleteTarget(null);
    },
  });

  const openAdd = () => {
    setEditing(null);
    setForm(EMPTY_FORM);
    setFormError("");
    setDialogOpen(true);
  };

  const openEdit = (member: FamilyMember) => {
    setEditing(member);
    setForm({
      full_name: member.full_name,
      dob: member.dob,
      relationship: member.relationship,
      gender: member.gender ?? "",
      blood_group: member.blood_group ?? "",
      notes: member.notes ?? "",
    });
    setFormError("");
    setDialogOpen(true);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setFormError("");
    if (!form.full_name.trim() || !form.dob) {
      setFormError(t("requiredFields"));
      return;
    }
    saveMutation.mutate();
  };

  return (
    <div className="space-y-6">
      <Breadcrumb items={[{ label: t("breadcrumb") }]} />

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-dreams-textPrimary">{t("title")}</h1>
          <p className="text-dreams-textSecondary mt-1">{t("subtitle")}</p>
        </div>
        <button
          type="button"
          onClick={openAdd}
          className="flex items-center gap-2 px-4 py-2 bg-dreams-blue text-white rounded-lg hover:opacity-90 transition-opacity text-sm font-medium"
        >
          <UserPlus className="h-4 w-4" />
          {t("addMember")}
        </button>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-12">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary-200 border-t-primary-600" />
        </div>
      ) : isError ? (
        <div className="bg-white rounded-lg shadow-card p-12 text-center">
          <p className="text-red-500 font-medium">{t("loadError")}</p>
          <p className="mt-1 text-sm text-dreams-textSecondary">{t("loadErrorHint")}</p>
        </div>
      ) : members.length === 0 ? (
        <div className="bg-white rounded-lg shadow-card p-12 text-center">
          <Users className="h-12 w-12 text-dreams-textSecondary mx-auto mb-4" />
          <p className="text-dreams-textSecondary font-medium">{t("emptyTitle")}</p>
          <p className="mt-1 text-sm text-dreams-textSecondary/70">{t("emptyHint")}</p>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {members.map((member) => (
            <div
              key={member.member_id}
              className="bg-white rounded-lg shadow-card p-5 border border-dreams-border"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="font-semibold text-dreams-textPrimary truncate">
                    {member.full_name}
                  </p>
                  <p className="mt-0.5 text-sm text-dreams-textSecondary">
                    {t(`relationships.${member.relationship}`)}
                    {" · "}
                    {t("ageYears", { age: member.age })}
                    {member.gender && (
                      <>
                        {" · "}
                        {(GENDERS as readonly string[]).includes(member.gender)
                          ? t(`genders.${member.gender as Gender}`)
                          : member.gender}
                      </>
                    )}
                  </p>
                </div>
                <div className="flex items-center gap-1 flex-shrink-0">
                  <button
                    type="button"
                    onClick={() => openEdit(member)}
                    className="p-2 rounded-lg text-dreams-textSecondary hover:text-dreams-blue hover:bg-dreams-lightBg transition-colors"
                    aria-label={t("editMember")}
                  >
                    <Pencil className="h-4 w-4" />
                  </button>
                  <button
                    type="button"
                    onClick={() => setDeleteTarget(member)}
                    className="p-2 rounded-lg text-dreams-textSecondary hover:text-red-600 hover:bg-red-50 transition-colors"
                    aria-label={t("deleteMember")}
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>
              {member.blood_group && (
                <p className="mt-2 text-xs text-dreams-textSecondary">
                  {t("fields.bloodGroup")}: {member.blood_group}
                </p>
              )}
              {member.notes && (
                <p className="mt-1 text-xs text-dreams-textSecondary line-clamp-2">
                  {member.notes}
                </p>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Add / edit dialog */}
      <Dialog
        open={dialogOpen}
        onOpenChange={(open) => {
          setDialogOpen(open);
          if (!open) {
            setEditing(null);
            setForm(EMPTY_FORM);
            setFormError("");
          }
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {editing ? t("editMember") : t("addMember")}
            </DialogTitle>
            <DialogDescription>{t("dialogDescription")}</DialogDescription>
          </DialogHeader>
          <form onSubmit={handleSubmit} className="space-y-4">
            {formError && <p className="text-sm text-red-600">{formError}</p>}

            <div>
              <Label htmlFor="fm-name">{t("fields.fullName")} *</Label>
              <Input
                id="fm-name"
                value={form.full_name}
                onChange={(e) =>
                  setForm((f) => ({ ...f, full_name: e.target.value }))
                }
                maxLength={255}
                required
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label htmlFor="fm-dob">{t("fields.dob")} *</Label>
                <Input
                  id="fm-dob"
                  type="date"
                  value={form.dob}
                  max={new Date().toISOString().slice(0, 10)}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, dob: e.target.value }))
                  }
                  required
                />
              </div>
              <div>
                <Label htmlFor="fm-rel">{t("fields.relationship")} *</Label>
                <select
                  id="fm-rel"
                  value={form.relationship}
                  onChange={(e) =>
                    setForm((f) => ({
                      ...f,
                      relationship: e.target.value as FamilyRelationship,
                    }))
                  }
                  className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  {FAMILY_RELATIONSHIPS.map((rel) => (
                    <option key={rel} value={rel}>
                      {t(`relationships.${rel}`)}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label htmlFor="fm-gender">{t("fields.gender")}</Label>
                <select
                  id="fm-gender"
                  value={form.gender}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, gender: e.target.value }))
                  }
                  className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <option value="">—</option>
                  {GENDERS.map((g) => (
                    <option key={g} value={g}>
                      {t(`genders.${g}`)}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <Label htmlFor="fm-blood">{t("fields.bloodGroup")}</Label>
                <select
                  id="fm-blood"
                  value={form.blood_group}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, blood_group: e.target.value }))
                  }
                  className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <option value="">—</option>
                  {BLOOD_GROUPS.map((bg) => (
                    <option key={bg} value={bg}>
                      {bg}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div>
              <Label htmlFor="fm-notes">{t("fields.notes")}</Label>
              <Textarea
                id="fm-notes"
                value={form.notes}
                onChange={(e) =>
                  setForm((f) => ({ ...f, notes: e.target.value }))
                }
                rows={2}
                maxLength={2000}
              />
            </div>

            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => setDialogOpen(false)}
                disabled={saveMutation.isPending}
              >
                {t("cancel")}
              </Button>
              <Button type="submit" disabled={saveMutation.isPending}>
                {saveMutation.isPending ? t("saving") : t("save")}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Delete confirm */}
      <AlertDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t("deleteTitle")}</AlertDialogTitle>
            <AlertDialogDescription>
              {t("deleteDescription", { name: deleteTarget?.full_name ?? "" })}
            </AlertDialogDescription>
          </AlertDialogHeader>
          {deleteMutation.isError && (
            <p className="text-sm text-red-600">{t("deleteError")}</p>
          )}
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleteMutation.isPending}>
              {t("cancel")}
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={() =>
                deleteTarget && deleteMutation.mutate(deleteTarget.member_id)
              }
              disabled={deleteMutation.isPending}
              className="bg-red-600 hover:bg-red-700"
            >
              {deleteMutation.isPending ? t("deleting") : t("deleteAction")}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
