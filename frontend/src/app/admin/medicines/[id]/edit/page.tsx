"use client";

import { useMemo, useState, useEffect } from "react";
import { useTranslations } from "next-intl";
import { useRouter, useParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm, useWatch } from "react-hook-form";
import * as z from "zod";
import { ArrowLeft, Plus, X, Loader2, Trash2 } from "lucide-react";
import { getAccessToken } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { Autocomplete } from "@/components/ui/autocomplete";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { useToast } from "@/hooks/use-toast";
import {
  listManufacturers,
  listSalts,
  getSaltStrengths,
  getBrand,
  updateBrand,
  deleteBrand,
  type Manufacturer,
  type Salt,
  type SaltStrength,
  type Brand,
  type BrandCompositionInput,
} from "@/lib/api/medicines-emr";

// Form validation schema shape (messages are translated inside the component)
const formSchemaShape = {
  brand_name: z.string().min(1).max(255),
  manufacturer_id: z.string().uuid(),
  drug_type: z.enum(["allopathy", "ayurveda", "homeopathy"]),
  is_discontinued: z.boolean().default(false),
  launch_date: z.string().optional(),
  discontinuation_date: z.string().optional(),
  ndhm_code: z.string().max(50).optional(),
  compositions: z
    .array(
      z.object({
        salt_strength_id: z.string().uuid(),
        sequence: z.number().int().positive(),
      })
    )
    .min(1),
};

type FormData = z.infer<z.ZodObject<typeof formSchemaShape>>;

interface CompositionEntry {
  id: string;
  salt_id: string;
  salt_name: string;
  salt_strength_id: string;
  display_strength: string;
  sequence: number;
}

function toCompositionEntries(brand?: Brand): CompositionEntry[] {
  if (!brand) return [];
  return brand.compositions.map((comp) => ({
    id: `existing-${comp.composition_id}`,
    salt_id: "", // We don't have this in the response, would need to fetch if needed
    salt_name: comp.salt_name,
    salt_strength_id: "", // Would need to map this from the composition data
    display_strength: comp.display_strength,
    sequence: comp.sequence,
  }));
}

export default function EditMedicinePage() {
  const t = useTranslations("adminMedicines.form");
  const tCommon = useTranslations("common");
  const router = useRouter();
  const params = useParams();
  const brandId = params.id as string;
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const formSchema = useMemo(
    () =>
      z.object({
        ...formSchemaShape,
        brand_name: z.string().min(1, t("brandNameRequired")).max(255),
        manufacturer_id: z.string().uuid(t("manufacturerRequired")),
        compositions: z
          .array(formSchemaShape.compositions.element)
          .min(1, t("compositionRequired")),
      }),
    [t]
  );

  // null while the user hasn't touched the list — `compositions` below then
  // falls back to the entries loaded with the brand.
  const [editedCompositions, setEditedCompositions] = useState<CompositionEntry[] | null>(null);
  const [selectedSaltId, setSelectedSaltId] = useState<string>("");
  const [selectedSaltName, setSelectedSaltName] = useState<string>("");
  const [selectedStrengthId, setSelectedStrengthId] = useState<string>("");
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);

  // Fetch brand details
  const {
    data: brand,
    isLoading: brandLoading,
    error: brandError,
  } = useQuery({
    queryKey: ["brand", brandId],
    queryFn: () => getBrand(brandId),
  });

  // Fetch manufacturers (with search)
  const [manufacturerSearchQuery, setManufacturerSearchQuery] = useState("");
  const { data: manufacturers = [] } = useQuery({
    queryKey: ["manufacturers", manufacturerSearchQuery],
    queryFn: () => listManufacturers(manufacturerSearchQuery || undefined),
  });

  // Fetch salts for composition selection (with search)
  const [saltSearchQuery, setSaltSearchQuery] = useState("");
  const { data: saltsData } = useQuery({
    queryKey: ["salts-for-composition", saltSearchQuery],
    queryFn: () => listSalts({ search: saltSearchQuery || undefined, limit: 50 }),
    enabled: saltSearchQuery.length > 0,
  });

  // Fetch strengths for selected salt
  const { data: saltStrengths = [] } = useQuery({
    queryKey: ["salt-strengths", selectedSaltId],
    queryFn: () => getSaltStrengths(selectedSaltId),
    enabled: !!selectedSaltId,
  });

  // Form setup
  const {
    register,
    handleSubmit,
    setValue,
    control,
    reset,
    formState: { errors },
  } = useForm<FormData>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      drug_type: "allopathy",
      is_discontinued: false,
      compositions: [],
    },
  });

  const watchManufacturerId = useWatch({ control, name: "manufacturer_id" });
  const watchDrugType = useWatch({ control, name: "drug_type" });
  const watchIsDiscontinued = useWatch({ control, name: "is_discontinued" });

  // The composition list shown in the UI: the user's edits once they add or
  // remove an entry, otherwise the entries loaded with the brand.
  const compositions = editedCompositions ?? toCompositionEntries(brand);

  // Initialize the RHF form fields once the brand data arrives (the
  // compositions list is derived from `brand` above and needs no syncing).
  useEffect(() => {
    if (brand) {
      reset({
        brand_name: brand.brand_name,
        manufacturer_id: brand.manufacturer?.manufacturer_id || "",
        drug_type: brand.drug_type as "allopathy" | "ayurveda" | "homeopathy",
        is_discontinued: brand.is_discontinued,
        launch_date: brand.launch_date || "",
        discontinuation_date: brand.discontinuation_date || "",
        ndhm_code: brand.ndhm_code || "",
        compositions: [],
      });
    }
  }, [brand, reset]);

  // Update brand mutation
  const updateMutation = useMutation({
    mutationFn: async (data: FormData) => {
      const token = getAccessToken() || "";
      return updateBrand(brandId, data, token);
    },
    onSuccess: () => {
      toast({
        title: t("successTitle"),
        description: t("brandUpdated"),
      });
      queryClient.invalidateQueries({ queryKey: ["brand", brandId] });
      queryClient.invalidateQueries({ queryKey: ["admin-brands"] });
      router.push("/admin/medicines");
    },
    onError: (error: Error) => {
      toast({
        title: t("errorTitle"),
        description: error.message,
        variant: "destructive",
      });
    },
  });

  // Delete brand mutation
  const deleteMutation = useMutation({
    mutationFn: async () => {
      const token = getAccessToken() || "";
      return deleteBrand(brandId, token);
    },
    onSuccess: () => {
      toast({
        title: t("successTitle"),
        description: t("brandDeleted"),
      });
      queryClient.invalidateQueries({ queryKey: ["admin-brands"] });
      router.push("/admin/medicines");
    },
    onError: (error: Error) => {
      toast({
        title: t("errorTitle"),
        description: error.message,
        variant: "destructive",
      });
    },
  });

  // Handle creating new salt
  const handleCreateSalt = (saltName: string) => {
    const tempId = `new-salt-${Date.now()}`;
    setSelectedSaltId(tempId);
    setSelectedSaltName(saltName);
    setSelectedStrengthId("");
    toast({
      title: t("saltAddedTitle"),
      description: t("saltAddedDesc", { name: saltName }),
    });
  };

  // Add composition to list
  const handleAddComposition = () => {
    if (!selectedSaltId || !selectedStrengthId) {
      toast({
        title: t("validationError"),
        description: t("selectBoth"),
        variant: "destructive",
      });
      return;
    }

    const salt = saltsData?.salts.find((s) => s.salt_id === selectedSaltId);
    const strength = saltStrengths.find((s) => s.salt_strength_id === selectedStrengthId);

    if (!salt || !strength) return;

    const newComposition: CompositionEntry = {
      id: `${Date.now()}-${Math.random()}`,
      salt_id: salt.salt_id,
      salt_name: salt.salt_name,
      salt_strength_id: strength.salt_strength_id,
      display_strength: strength.display_strength,
      sequence: compositions.length + 1,
    };

    const updatedCompositions = [...compositions, newComposition];
    setEditedCompositions(updatedCompositions);

    setValue(
      "compositions",
      updatedCompositions.map((c) => ({
        salt_strength_id: c.salt_strength_id,
        sequence: c.sequence,
      }))
    );

    setSelectedSaltId("");
    setSelectedStrengthId("");
  };

  // Remove composition from list
  const handleRemoveComposition = (id: string) => {
    const updatedCompositions = compositions
      .filter((c) => c.id !== id)
      .map((c, index) => ({ ...c, sequence: index + 1 }));

    setEditedCompositions(updatedCompositions);
    setValue(
      "compositions",
      updatedCompositions.map((c) => ({
        salt_strength_id: c.salt_strength_id,
        sequence: c.sequence,
      }))
    );
  };

  const onSubmit = (data: FormData) => {
    if (compositions.length === 0) {
      toast({
        title: t("validationError"),
        description: t("addOneComposition"),
        variant: "destructive",
      });
      return;
    }

    updateMutation.mutate(data);
  };

  const handleDelete = () => {
    deleteMutation.mutate();
    setIsDeleteDialogOpen(false);
  };

  if (brandLoading) {
    return (
      <div className="container mx-auto py-6 flex justify-center">
        <Loader2 className="h-8 w-8 animate-spin" />
      </div>
    );
  }

  if (brandError || !brand) {
    return (
      <div className="container mx-auto py-6">
        <Card>
          <CardHeader>
            <CardTitle>{t("errorTitle")}</CardTitle>
            <CardDescription>{t("brandNotFound")}</CardDescription>
          </CardHeader>
          <CardContent>
            <Button onClick={() => router.push("/admin/medicines")}>
              {t("backToMedicines")}
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="container mx-auto py-6 max-w-4xl">
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
            <h1 className="text-3xl font-bold">{t("editTitle")}</h1>
            <p className="text-muted-foreground mt-2">
              {t("editSubtitle")}
            </p>
          </div>
          <AlertDialog open={isDeleteDialogOpen} onOpenChange={setIsDeleteDialogOpen}>
            <AlertDialogTrigger asChild>
              <Button variant="destructive" size="sm">
                <Trash2 className="h-4 w-4 mr-2" />
                {t("delete")}
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>{t("deleteTitle")}</AlertDialogTitle>
                <AlertDialogDescription>
                  {t("deleteDesc", { name: brand.brand_name })}
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>{tCommon("cancel")}</AlertDialogCancel>
                <AlertDialogAction
                  onClick={handleDelete}
                  className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                >
                  {deleteMutation.isPending && (
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  )}
                  {t("delete")}
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </div>
      </div>

      <form onSubmit={handleSubmit(onSubmit)}>
        <div className="space-y-6">
          {/* Basic Information */}
          <Card>
            <CardHeader>
              <CardTitle>{t("basicInfo")}</CardTitle>
              <CardDescription>{t("basicInfoDescEdit")}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label htmlFor="brand_name">{t("brandName")}</Label>
                <Input
                  id="brand_name"
                  {...register("brand_name")}
                  placeholder={t("brandNamePlaceholder")}
                />
                {errors.brand_name && (
                  <p className="text-sm text-destructive mt-1">{errors.brand_name.message}</p>
                )}
              </div>

              <div>
                <Label htmlFor="manufacturer_id">{t("manufacturerEdit")}</Label>
                <Autocomplete
                  options={manufacturers.map((m: Manufacturer) => ({
                    value: m.manufacturer_id,
                    label: m.manufacturer_name,
                  }))}
                  value={watchManufacturerId}
                  onValueChange={(value) => setValue("manufacturer_id", value)}
                  onSearchChange={setManufacturerSearchQuery}
                  placeholder={t("manufacturerPlaceholder")}
                  emptyText={t("noManufacturers")}
                />
                {errors.manufacturer_id && (
                  <p className="text-sm text-destructive mt-1">
                    {errors.manufacturer_id.message}
                  </p>
                )}
              </div>

              <div>
                <Label htmlFor="drug_type">{t("drugType")}</Label>
                <Select
                  value={watchDrugType}
                  onValueChange={(value: "allopathy" | "ayurveda" | "homeopathy") =>
                    setValue("drug_type", value)
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="allopathy">{t("drugTypes.allopathy")}</SelectItem>
                    <SelectItem value="ayurveda">{t("drugTypes.ayurveda")}</SelectItem>
                    <SelectItem value="homeopathy">{t("drugTypes.homeopathy")}</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="flex items-center space-x-2">
                <Checkbox
                  id="is_discontinued"
                  checked={watchIsDiscontinued}
                  onCheckedChange={(checked) =>
                    setValue("is_discontinued", checked as boolean)
                  }
                />
                <Label htmlFor="is_discontinued" className="font-normal cursor-pointer">
                  {t("markDiscontinued")}
                </Label>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="launch_date">{t("launchDate")}</Label>
                  <Input
                    id="launch_date"
                    type="date"
                    {...register("launch_date")}
                  />
                </div>

                {watchIsDiscontinued && (
                  <div>
                    <Label htmlFor="discontinuation_date">{t("discontinuationDate")}</Label>
                    <Input
                      id="discontinuation_date"
                      type="date"
                      {...register("discontinuation_date")}
                    />
                  </div>
                )}
              </div>

              <div>
                <Label htmlFor="ndhm_code">{t("ndhmCode")}</Label>
                <Input
                  id="ndhm_code"
                  {...register("ndhm_code")}
                  placeholder={t("ndhmPlaceholder")}
                />
              </div>
            </CardContent>
          </Card>

          {/* Composition */}
          <Card>
            <CardHeader>
              <CardTitle>{t("compositionTitle")}</CardTitle>
              <CardDescription>
                {t("compositionDescEdit")}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Current compositions (read-only display) */}
              <div>
                <Label className="text-sm text-muted-foreground">{t("currentComposition")}</Label>
                <p className="text-sm mt-1">{brand.salt_composition}</p>
              </div>

              {/* Add composition form */}
              <div className="space-y-2">
                <div className="flex gap-2">
                  <div className="flex-1">
                    <Label>{t("selectSalt")}</Label>
                    <Autocomplete
                      options={(saltsData?.salts || []).map((salt: Salt) => ({
                        value: salt.salt_id,
                        label: salt.salt_name,
                      }))}
                      value={selectedSaltId}
                      onValueChange={(value) => {
                        setSelectedSaltId(value);
                        setSelectedStrengthId("");
                      }}
                      onSearchChange={setSaltSearchQuery}
                      placeholder={t("saltPlaceholder")}
                      emptyText={t("noSalts")}
                      allowCreate={true}
                      onCreateNew={handleCreateSalt}
                    />
                  </div>

                  <div className="flex-1">
                    <Label>{t("selectStrength")}</Label>
                    <Select
                      value={selectedStrengthId}
                      onValueChange={setSelectedStrengthId}
                      disabled={!selectedSaltId}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder={!selectedSaltId ? t("selectSaltFirst") : t("selectStrengthPlaceholder")} />
                      </SelectTrigger>
                      <SelectContent>
                        {saltStrengths.map((strength: SaltStrength) => (
                          <SelectItem
                            key={strength.salt_strength_id}
                            value={strength.salt_strength_id}
                          >
                            {strength.display_strength}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="flex items-end">
                    <Button
                      type="button"
                      onClick={handleAddComposition}
                      disabled={!selectedSaltId || !selectedStrengthId}
                    >
                      <Plus className="h-4 w-4 mr-2" />
                      {t("add")}
                    </Button>
                  </div>
                </div>
              </div>

              {/* New composition list (if modified) */}
              {compositions.length > 0 && (
                <div className="space-y-2">
                  <Label className="text-sm text-muted-foreground">
                    {t("newComposition")}
                  </Label>
                  {compositions.map((comp) => (
                    <div
                      key={comp.id}
                      className="flex items-center justify-between p-3 bg-muted rounded-md"
                    >
                      <div>
                        <span className="font-medium">{comp.salt_name}</span>
                        <span className="text-muted-foreground ml-2">
                          ({comp.display_strength})
                        </span>
                        <span className="text-sm text-muted-foreground ml-2">
                          #{comp.sequence}
                        </span>
                      </div>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => handleRemoveComposition(comp.id)}
                      >
                        <X className="h-4 w-4" />
                      </Button>
                    </div>
                  ))}
                </div>
              )}

              {errors.compositions && (
                <p className="text-sm text-destructive">{errors.compositions.message}</p>
              )}
            </CardContent>
          </Card>

          {/* Actions */}
          <div className="flex justify-end space-x-4">
            <Button
              type="button"
              variant="outline"
              onClick={() => router.push("/admin/medicines")}
              disabled={updateMutation.isPending}
            >
              {tCommon("cancel")}
            </Button>
            <Button type="submit" disabled={updateMutation.isPending}>
              {updateMutation.isPending && (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              )}
              {t("updateBrand")}
            </Button>
          </div>
        </div>
      </form>
    </div>
  );
}
