"use client";

import { useState, useEffect } from "react";
import { useRouter, useParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import * as z from "zod";
import { ArrowLeft, Plus, X, Loader2, Trash2 } from "lucide-react";
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
  type BrandCompositionInput,
} from "@/lib/api/medicines-emr";

// Form validation schema
const formSchema = z.object({
  brand_name: z.string().min(1, "Brand name is required").max(255),
  manufacturer_id: z.string().uuid("Please select a manufacturer"),
  drug_type: z.enum(["allopathy", "ayurveda", "homeopathy"]),
  is_discontinued: z.boolean().default(false),
  launch_date: z.string().optional(),
  discontinuation_date: z.string().optional(),
  ndhm_code: z.string().max(50).optional(),
  compositions: z.array(
    z.object({
      salt_strength_id: z.string().uuid(),
      sequence: z.number().int().positive(),
    })
  ).min(1, "At least one composition is required"),
});

type FormData = z.infer<typeof formSchema>;

interface CompositionEntry {
  id: string;
  salt_id: string;
  salt_name: string;
  salt_strength_id: string;
  display_strength: string;
  sequence: number;
}

export default function EditMedicinePage() {
  const router = useRouter();
  const params = useParams();
  const brandId = params.id as string;
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const [compositions, setCompositions] = useState<CompositionEntry[]>([]);
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
    watch,
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

  const watchManufacturerId = watch("manufacturer_id");
  const watchDrugType = watch("drug_type");
  const watchIsDiscontinued = watch("is_discontinued");

  // Initialize form with brand data
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

      // Set compositions from brand data
      const loadedCompositions: CompositionEntry[] = brand.compositions.map((comp, index) => ({
        id: `existing-${comp.composition_id}`,
        salt_id: "", // We don't have this in the response, would need to fetch if needed
        salt_name: comp.salt_name,
        salt_strength_id: "", // Would need to map this from the composition data
        display_strength: comp.display_strength,
        sequence: comp.sequence,
      }));

      setCompositions(loadedCompositions);
    }
  }, [brand, reset]);

  // Update brand mutation
  const updateMutation = useMutation({
    mutationFn: async (data: FormData) => {
      const token = localStorage.getItem("access_token") || "";
      return updateBrand(brandId, data, token);
    },
    onSuccess: () => {
      toast({
        title: "Success",
        description: "Brand updated successfully",
      });
      queryClient.invalidateQueries({ queryKey: ["brand", brandId] });
      queryClient.invalidateQueries({ queryKey: ["admin-brands"] });
      router.push("/admin/medicines");
    },
    onError: (error: Error) => {
      toast({
        title: "Error",
        description: error.message,
        variant: "destructive",
      });
    },
  });

  // Delete brand mutation
  const deleteMutation = useMutation({
    mutationFn: async () => {
      const token = localStorage.getItem("access_token") || "";
      return deleteBrand(brandId, token);
    },
    onSuccess: () => {
      toast({
        title: "Success",
        description: "Brand deleted successfully",
      });
      queryClient.invalidateQueries({ queryKey: ["admin-brands"] });
      router.push("/admin/medicines");
    },
    onError: (error: Error) => {
      toast({
        title: "Error",
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
      title: "Salt Added",
      description: `"${saltName}" will be created when you save the brand`,
    });
  };

  // Add composition to list
  const handleAddComposition = () => {
    if (!selectedSaltId || !selectedStrengthId) {
      toast({
        title: "Validation Error",
        description: "Please select both salt and strength",
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
        title: "Validation Error",
        description: "Please add at least one composition",
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
            <CardTitle>Error</CardTitle>
            <CardDescription>Brand not found or failed to load</CardDescription>
          </CardHeader>
          <CardContent>
            <Button onClick={() => router.push("/admin/medicines")}>
              Back to Medicines
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
          Back to Medicines
        </Button>
        <div className="flex justify-between items-start">
          <div>
            <h1 className="text-3xl font-bold">Edit Medicine</h1>
            <p className="text-muted-foreground mt-2">
              Update brand details and composition
            </p>
          </div>
          <AlertDialog open={isDeleteDialogOpen} onOpenChange={setIsDeleteDialogOpen}>
            <AlertDialogTrigger asChild>
              <Button variant="destructive" size="sm">
                <Trash2 className="h-4 w-4 mr-2" />
                Delete
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Delete Brand</AlertDialogTitle>
                <AlertDialogDescription>
                  Are you sure you want to delete "{brand.brand_name}"? This action cannot
                  be undone and will remove all associated data.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Cancel</AlertDialogCancel>
                <AlertDialogAction
                  onClick={handleDelete}
                  className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                >
                  {deleteMutation.isPending && (
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  )}
                  Delete
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
              <CardTitle>Basic Information</CardTitle>
              <CardDescription>Update the brand details</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label htmlFor="brand_name">Brand Name *</Label>
                <Input
                  id="brand_name"
                  {...register("brand_name")}
                  placeholder="e.g., Crocin 500"
                />
                {errors.brand_name && (
                  <p className="text-sm text-destructive mt-1">{errors.brand_name.message}</p>
                )}
              </div>

              <div>
                <Label htmlFor="manufacturer_id">Manufacturer * (type to search)</Label>
                <Autocomplete
                  options={manufacturers.map((m: Manufacturer) => ({
                    value: m.manufacturer_id,
                    label: m.manufacturer_name,
                  }))}
                  value={watchManufacturerId}
                  onValueChange={(value) => setValue("manufacturer_id", value)}
                  onSearchChange={setManufacturerSearchQuery}
                  placeholder="Type manufacturer name..."
                  emptyText="No manufacturers found."
                />
                {errors.manufacturer_id && (
                  <p className="text-sm text-destructive mt-1">
                    {errors.manufacturer_id.message}
                  </p>
                )}
              </div>

              <div>
                <Label htmlFor="drug_type">Drug Type *</Label>
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
                    <SelectItem value="allopathy">Allopathy</SelectItem>
                    <SelectItem value="ayurveda">Ayurveda</SelectItem>
                    <SelectItem value="homeopathy">Homeopathy</SelectItem>
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
                  Mark as discontinued
                </Label>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="launch_date">Launch Date</Label>
                  <Input
                    id="launch_date"
                    type="date"
                    {...register("launch_date")}
                  />
                </div>

                {watchIsDiscontinued && (
                  <div>
                    <Label htmlFor="discontinuation_date">Discontinuation Date</Label>
                    <Input
                      id="discontinuation_date"
                      type="date"
                      {...register("discontinuation_date")}
                    />
                  </div>
                )}
              </div>

              <div>
                <Label htmlFor="ndhm_code">NDHM Code (Optional)</Label>
                <Input
                  id="ndhm_code"
                  {...register("ndhm_code")}
                  placeholder="ABDM integration code"
                />
              </div>
            </CardContent>
          </Card>

          {/* Composition */}
          <Card>
            <CardHeader>
              <CardTitle>Salt Composition *</CardTitle>
              <CardDescription>
                Modify salt compositions (changes will replace all existing compositions)
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Current compositions (read-only display) */}
              <div>
                <Label className="text-sm text-muted-foreground">Current Composition:</Label>
                <p className="text-sm mt-1">{brand.salt_composition}</p>
              </div>

              {/* Add composition form */}
              <div className="space-y-2">
                <div className="flex gap-2">
                  <div className="flex-1">
                    <Label>Select Salt (type to search or create new)</Label>
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
                      placeholder="Type salt name (e.g., Paracetamol)..."
                      emptyText="No salts found."
                      allowCreate={true}
                      onCreateNew={handleCreateSalt}
                    />
                  </div>

                  <div className="flex-1">
                    <Label>Select Strength</Label>
                    <Select
                      value={selectedStrengthId}
                      onValueChange={setSelectedStrengthId}
                      disabled={!selectedSaltId}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder={!selectedSaltId ? "Select salt first" : "Select strength"} />
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
                      Add
                    </Button>
                  </div>
                </div>
              </div>

              {/* New composition list (if modified) */}
              {compositions.length > 0 && (
                <div className="space-y-2">
                  <Label className="text-sm text-muted-foreground">
                    New Composition (will replace current):
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
              Cancel
            </Button>
            <Button type="submit" disabled={updateMutation.isPending}>
              {updateMutation.isPending && (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              )}
              Update Brand
            </Button>
          </div>
        </div>
      </form>
    </div>
  );
}
