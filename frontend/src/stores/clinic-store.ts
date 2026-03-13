import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { Clinic } from '@/lib/api/clinics'

interface ClinicState {
  activeClinicId: string | null
  clinics: Clinic[]
  setActiveClinic: (id: string | null) => void
  setClinics: (clinics: Clinic[]) => void
  clearClinics: () => void
}

export const useClinicStore = create<ClinicState>()(
  persist(
    (set) => ({
      activeClinicId: null,
      clinics: [],
      setActiveClinic: (id) => set({ activeClinicId: id }),
      setClinics: (clinics) =>
        set((state) => ({
          clinics,
          // Auto-select first clinic if none selected or if current is no longer in list
          activeClinicId:
            state.activeClinicId && clinics.some((c) => c.id === state.activeClinicId)
              ? state.activeClinicId
              : clinics[0]?.id ?? null,
        })),
      clearClinics: () => set({ activeClinicId: null, clinics: [] }),
    }),
    {
      name: 'clinic-store',
      partialize: (state) => ({ activeClinicId: state.activeClinicId }),
    }
  )
)
