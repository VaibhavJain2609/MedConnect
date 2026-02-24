"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useMutation } from "@tanstack/react-query";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import * as z from "zod";
import { ArrowLeft, Plus, X, Loader2 } from "lucide-react";
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
import { Combobox } from "@/components/ui/combobox";
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
  id: string; // Temporary ID for UI list management
  salt_id: string;
  salt_name: string;
  salt_strength_id: string;
  display_strength: string;
  sequence: number;
}

export default function AddMedicinePage() {
  const router = useRouter();
  const { toast } = useToast();
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
    watch,
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

  // Create brand mutation
  const createMutation = useMutation({
    mutationFn: async (data: FormData) => {
      // Get auth token (you'll need to adapt this to your auth system)
      const token = localStorage.getItem("access_token") || "";
      return createBrand(data, token);
    },
    onSuccess: () => {
      toast({
        title: "Success",
        description: "Brand created successfully",
      });
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

  // Handle creating new manufacturer
  const handleCreateManufacturer = (manufacturerName: string) => {
    // Create a temporary ID for the new manufacturer
    const tempId = `new-${Date.now()}`;
    setNewManufacturerName(manufacturerName);
    setValue("manufacturer_id", tempId);
    toast({
      title: "Manufacturer Added",
      description: `"${manufacturerName}" will be created when you save the brand`,
    });
  };

  // Handle creating new salt (just store the name, will be created on backend)
  const handleSelectSalt = (saltValue: string) => {
    // Check if it's an existing salt or a search query
    const existingSalt = saltsData?.salts.find((s) => s.salt_id === saltValue);
    if (existingSalt) {
      setSelectedSaltId(existingSalt.salt_id);
      setSelectedSaltName(existingSalt.salt_name);
    } else {
      // It's a new salt name from search
      setSelectedSaltId("");
      setSelectedSaltName(saltValue);
    }
    setSelectedStrengthId("");
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
        title: "Validation Error",
        description: "Please add at least one composition",
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
          Back to Medicines
        </Button>
        <h1 className="text-3xl font-bold">Add New Medicine</h1>
        <p className="text-muted-foreground mt-2">
          Create a new brand (commercial medicine) in the database
        </p>
      </div>

      <form onSubmit={handleSubmit(onSubmit)}>
        <div className="space-y-6">
          {/* Basic Information */}
          <Card>
            <CardHeader>
              <CardTitle>Basic Information</CardTitle>
              <CardDescription>Enter the brand details</CardDescription>
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
                <Label htmlFor="manufacturer_id">Manufacturer * (type to search or create new)</Label>
                <Combobox
                  options={manufacturers.map((m: Manufacturer) => ({
                    value: m.manufacturer_id,
                    label: m.manufacturer_name,
                  }))}
                  value={watchManufacturerId}
                  onValueChange={(value) => setValue("manufacturer_id", value)}
                  onSearchChange={setManufacturerSearchQuery}
                  placeholder="Select or create manufacturer..."
                  searchPlaceholder="Search manufacturers..."
                  emptyText="No manufacturers found."
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
                Add one or more salt strengths (for combination drugs)
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Add composition form */}
              <div className="space-y-2">
                <div className="flex gap-2">
                  <div className="flex-1">
                    <Label>Select Salt (type to search)</Label>
                    <Combobox
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
                      placeholder="Select salt..."
                      searchPlaceholder="Search salts (e.g., Paracetamol)..."
                      emptyText="No salts found. Try different keywords."
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
                      Add
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
              Cancel
            </Button>
            <Button type="submit" disabled={createMutation.isPending}>
              {createMutation.isPending && (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              )}
              Create Brand
            </Button>
          </div>
        </div>
      </form>
    </div>
  );
}
