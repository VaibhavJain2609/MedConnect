"use client";

import { useState, KeyboardEvent } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "@/lib/api";
import { Breadcrumb } from "@/components/ui/breadcrumb";

const BLOOD_GROUPS = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"];

function TagInput({
  tags,
  onChange,
  placeholder,
}: {
  tags: string[];
  onChange: (tags: string[]) => void;
  placeholder: string;
}) {
  const [input, setInput] = useState("");

  const addTag = (value: string) => {
    const trimmed = value.trim();
    if (trimmed && !tags.includes(trimmed)) {
      onChange([...tags, trimmed]);
    }
    setInput("");
  };

  const removeTag = (index: number) => {
    onChange(tags.filter((_, i) => i !== index));
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      addTag(input);
    } else if (e.key === "Backspace" && !input && tags.length > 0) {
      removeTag(tags.length - 1);
    }
  };

  return (
    <div className="min-h-10 flex flex-wrap gap-1.5 rounded-lg border border-dreams-border px-3 py-2 bg-white focus-within:border-dreams-blue focus-within:ring-2 focus-within:ring-dreams-blue/20">
      {tags.map((tag, i) => (
        <span
          key={i}
          className="inline-flex items-center gap-1 rounded-md bg-dreams-blue/10 px-2 py-0.5 text-sm text-dreams-blue"
        >
          {tag}
          <button
            type="button"
            onClick={() => removeTag(i)}
            className="text-dreams-blue/60 hover:text-dreams-blue leading-none"
          >
            ×
          </button>
        </span>
      ))}
      <input
        type="text"
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={handleKeyDown}
        onBlur={() => addTag(input)}
        placeholder={tags.length === 0 ? placeholder : ""}
        className="flex-1 min-w-[120px] text-sm outline-none bg-transparent placeholder:text-dreams-textSecondary/50"
      />
    </div>
  );
}

export default function MedicalHistoryPage() {
  const queryClient = useQueryClient();
  const [saved, setSaved] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["medical-history"],
    queryFn: async () => {
      const res = await api.get("/api/v1/patients/medical-history");
      return res.data;
    },
  });

  const [form, setForm] = useState({
    blood_group: "",
    allergies: [] as string[],
    chronic_conditions: [] as string[],
    height_cm: "",
    weight_kg: "",
  });

  const [initialized, setInitialized] = useState(false);
  if (data && !initialized) {
    setForm({
      blood_group: data.blood_group ?? "",
      allergies: data.allergies ?? [],
      chronic_conditions: data.chronic_conditions ?? [],
      height_cm: data.height_cm != null ? String(data.height_cm) : "",
      weight_kg: data.weight_kg != null ? String(data.weight_kg) : "",
    });
    setInitialized(true);
  }

  const mutation = useMutation({
    mutationFn: async (values: typeof form) => {
      const payload: Record<string, unknown> = {
        blood_group: values.blood_group || null,
        allergies: values.allergies,
        chronic_conditions: values.chronic_conditions,
        height_cm: values.height_cm ? parseFloat(values.height_cm) : null,
        weight_kg: values.weight_kg ? parseFloat(values.weight_kg) : null,
      };
      const res = await api.put("/api/v1/patients/medical-history", payload);
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["medical-history"] });
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    },
  });

  const bmi =
    form.height_cm && form.weight_kg
      ? (parseFloat(form.weight_kg) / Math.pow(parseFloat(form.height_cm) / 100, 2)).toFixed(1)
      : null;

  if (isLoading) {
    return (
      <div className="flex justify-center py-12">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-dreams-blue/20 border-t-dreams-blue" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <Breadcrumb items={[{ label: "Medical History" }]} />

      <div>
        <h1 className="text-3xl font-bold text-dreams-textPrimary">Medical History</h1>
        <p className="text-dreams-textSecondary mt-1">Your allergies, chronic conditions, and vital stats</p>
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          mutation.mutate(form);
        }}
        className="space-y-6 max-w-2xl"
      >
        {/* Vitals */}
        <div className="bg-white rounded-lg shadow-card p-6 space-y-4">
          <h2 className="text-lg font-semibold text-dreams-textPrimary border-b border-dreams-border pb-3">
            Vital Information
          </h2>

          <div className="space-y-2">
            <label className="text-sm font-medium text-dreams-textPrimary">Blood Group</label>
            <div className="flex flex-wrap gap-2">
              {BLOOD_GROUPS.map((bg) => (
                <button
                  key={bg}
                  type="button"
                  onClick={() =>
                    setForm((f) => ({ ...f, blood_group: f.blood_group === bg ? "" : bg }))
                  }
                  className={`px-3 py-1.5 rounded-lg text-sm font-medium border transition-colors ${
                    form.blood_group === bg
                      ? "bg-dreams-blue text-white border-dreams-blue"
                      : "bg-white text-dreams-textPrimary border-dreams-border hover:border-dreams-blue/50"
                  }`}
                >
                  {bg}
                </button>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="text-sm font-medium text-dreams-textPrimary" htmlFor="height">
                Height (cm)
              </label>
              <input
                id="height"
                type="number"
                min="50"
                max="300"
                step="0.1"
                value={form.height_cm}
                onChange={(e) => setForm((f) => ({ ...f, height_cm: e.target.value }))}
                placeholder="e.g. 170"
                className="w-full h-10 rounded-lg border border-dreams-border px-3 py-2 text-sm bg-white focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20"
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-dreams-textPrimary" htmlFor="weight">
                Weight (kg)
              </label>
              <input
                id="weight"
                type="number"
                min="1"
                max="500"
                step="0.1"
                value={form.weight_kg}
                onChange={(e) => setForm((f) => ({ ...f, weight_kg: e.target.value }))}
                placeholder="e.g. 65"
                className="w-full h-10 rounded-lg border border-dreams-border px-3 py-2 text-sm bg-white focus:border-dreams-blue focus:outline-none focus:ring-2 focus:ring-dreams-blue/20"
              />
            </div>
          </div>

          {bmi && (
            <div className="rounded-lg bg-dreams-lightBg border border-dreams-border px-4 py-3">
              <p className="text-sm text-dreams-textSecondary">
                BMI:{" "}
                <span className="font-semibold text-dreams-textPrimary">{bmi}</span>
                {" "}
                <span className="text-xs">
                  {parseFloat(bmi) < 18.5
                    ? "(Underweight)"
                    : parseFloat(bmi) < 25
                    ? "(Normal)"
                    : parseFloat(bmi) < 30
                    ? "(Overweight)"
                    : "(Obese)"}
                </span>
              </p>
            </div>
          )}
        </div>

        {/* Allergies */}
        <div className="bg-white rounded-lg shadow-card p-6 space-y-4">
          <h2 className="text-lg font-semibold text-dreams-textPrimary border-b border-dreams-border pb-3">
            Allergies
          </h2>
          <div className="space-y-2">
            <label className="text-sm font-medium text-dreams-textPrimary">
              Known Allergies
            </label>
            <TagInput
              tags={form.allergies}
              onChange={(tags) => setForm((f) => ({ ...f, allergies: tags }))}
              placeholder="Type an allergy and press Enter (e.g. Penicillin, Peanuts)"
            />
            <p className="text-xs text-dreams-textSecondary/60">Press Enter or comma to add each item</p>
          </div>
        </div>

        {/* Chronic Conditions */}
        <div className="bg-white rounded-lg shadow-card p-6 space-y-4">
          <h2 className="text-lg font-semibold text-dreams-textPrimary border-b border-dreams-border pb-3">
            Chronic Conditions
          </h2>
          <div className="space-y-2">
            <label className="text-sm font-medium text-dreams-textPrimary">
              Ongoing Conditions
            </label>
            <TagInput
              tags={form.chronic_conditions}
              onChange={(tags) => setForm((f) => ({ ...f, chronic_conditions: tags }))}
              placeholder="Type a condition and press Enter (e.g. Diabetes, Hypertension)"
            />
            <p className="text-xs text-dreams-textSecondary/60">Press Enter or comma to add each item</p>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <button
            type="submit"
            disabled={mutation.isPending}
            className="h-10 px-6 rounded-lg bg-dreams-blue text-white text-sm font-medium hover:bg-dreams-blue/90 disabled:opacity-60 transition-colors"
          >
            {mutation.isPending ? "Saving..." : "Save Changes"}
          </button>
          {saved && (
            <p className="text-sm text-green-600 font-medium">Medical history updated successfully.</p>
          )}
          {mutation.isError && (
            <p className="text-sm text-red-600">Failed to save. Please try again.</p>
          )}
        </div>
      </form>
    </div>
  );
}
