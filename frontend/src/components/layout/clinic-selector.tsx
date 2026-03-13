"use client";

import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Building2, ChevronDown, Check } from "lucide-react";
import { getMyClinicss } from "@/lib/api/clinics";
import { useClinicStore } from "@/stores/clinic-store";

export function ClinicSelector() {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const { activeClinicId, clinics, setActiveClinic, setClinics } = useClinicStore();

  const { data } = useQuery({
    queryKey: ["my-clinics"],
    queryFn: getMyClinicss,
  });

  useEffect(() => {
    if (data?.data) {
      setClinics(data.data);
    }
  }, [data, setClinics]);

  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const activeClinic = clinics.find((c) => c.id === activeClinicId);

  if (clinics.length === 0) return null;

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 rounded-lg border border-dreams-border bg-white px-3 py-1.5 text-sm hover:bg-gray-50 transition-colors"
      >
        <Building2 className="h-4 w-4 text-dreams-blue shrink-0" />
        <span className="max-w-[140px] truncate font-medium text-dreams-textPrimary">
          {activeClinic?.name ?? "Select Clinic"}
        </span>
        <ChevronDown className="h-3.5 w-3.5 text-dreams-textSecondary shrink-0" />
      </button>

      {open && (
        <div className="absolute left-0 top-full z-50 mt-1 min-w-[200px] rounded-xl border border-dreams-border bg-white py-1 shadow-lg">
          {clinics.map((clinic) => (
            <button
              key={clinic.id}
              onClick={() => { setActiveClinic(clinic.id); setOpen(false); }}
              className="flex w-full items-center gap-3 px-3 py-2 text-left text-sm hover:bg-gray-50 transition-colors"
            >
              <Building2 className="h-4 w-4 text-dreams-textSecondary shrink-0" />
              <span className="flex-1 truncate text-dreams-textPrimary">{clinic.name}</span>
              {clinic.id === activeClinicId && (
                <Check className="h-4 w-4 text-dreams-blue shrink-0" />
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
