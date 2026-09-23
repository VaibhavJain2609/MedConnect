"use client";

import { useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { useQuery, useMutation } from "@tanstack/react-query";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm, useWatch } from "react-hook-form";
import * as z from "zod";
import { ArrowLeft, Plus, X, Loader2 } from "lucide-react";
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
import { useToast } from "@/hooks/use-toast";
import {
  listManufacturers,
  listSalts,
  getSaltStrengths,
  createBrand,
  type Manufacturer,
  type Salt,
  type SaltStrength,
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
  id: string; // Temporary ID for UI list management
  salt_id: string;
  salt_name: string;
  salt_strength_id: string;
  display_strength: string;
  sequence: number;
}

export default function AddMedicinePage() {
  const t = useTranslations("adminMedicines.form");
  const tCommon = useTranslations("common");
  const router = useRouter();
  const { toast } = useToast();
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
  const [compositions, setCompositions] = useState<CompositionEntry[]>([]);
  const [selectedSaltId, setSelectedSaltId] = useState<string>("");
  const [selectedSaltName, setSelectedSaltName] = useState<string>("");
  const [selectedStrengthId, setSelectedStrengthId] = useState<string>("");
  const [newManufacturerName, setNewManufacturerName] = useState<string>("");

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

  // Create brand mutation
  const createMutation = useMutation({
    mutationFn: async (data: FormData) => {
      const token = getAccessToken() || "";
      return createBrand(data, token);
    },
    onSuccess: () => {
      toast({
        title: t("successTitle"),
        description: t("brandCreated"),
      });
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

  // Handle creating new manufacturer
  const handleCreateManufacturer = (manufacturerName: string) => {
    // Create a temporary ID for the new manufacturer
    const tempId = `new-${Date.now()}`;
    setNewManufacturerName(manufacturerName);
    setValue("manufacturer_id", tempId);
    toast({
      title: t("manufacturerAddedTitle"),
      description: t("manufacturerAddedDesc", { name: manufacturerName }),
    });
  };

  // Handle creating new salt
  const handleCreateSalt = (saltName: string) => {
    // Create a temporary ID for the new salt
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
    setCompositions(updatedCompositions);

    // Update form value
    setValue(
      "compositions",
      updatedCompositions.map((c) => ({
        salt_strength_id: c.salt_strength_id,
        sequence: c.sequence,
      }))
    );

    // Reset selection
    setSelectedSaltId("");
    setSelectedStrengthId("");
  };

  // Remove composition from list
  const handleRemoveComposition = (id: string) => {
    const updatedCompositions = compositions
      .filter((c) => c.id !== id)
      .map((c, index) => ({ ...c, sequence: index + 1 }));

    setCompositions(updatedCompositions);
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

    createMutation.mutate(data);
  };

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
        <h1 className="text-3xl font-bold">{t("newTitle")}</h1>
        <p className="text-muted-foreground mt-2">
          {t("newSubtitle")}
        </p>
      </div>

      <form onSubmit={handleSubmit(onSubmit)}>
        <div className="space-y-6">
          {/* Basic Information */}
          <Card>
            <CardHeader>
              <CardTitle>{t("basicInfo")}</CardTitle>
              <CardDescription>{t("basicInfoDescNew")}</CardDescription>
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
                <Label htmlFor="manufacturer_id">{t("manufacturerNew")}</Label>
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
                  allowCreate={true}
                  onCreateNew={handleCreateManufacturer}
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
                {t("compositionDescNew")}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
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
                          <SelectItem key={strength.salt_strength_id} value={strength.salt_strength_id}>
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

              {/* Composition list */}
              {compositions.length > 0 && (
                <div className="space-y-2">
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
              disabled={createMutation.isPending}
            >
              {tCommon("cancel")}
            </Button>
            <Button type="submit" disabled={createMutation.isPending}>
              {createMutation.isPending && (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              )}
              {t("createBrand")}
            </Button>
          </div>
        </div>
      </form>
    </div>
  );
}
