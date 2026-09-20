import { create } from 'zustand'

/**
 * Small UI store for cross-component chrome state.
 * Currently tracks the global search modal open state so that both the
 * ⌘K/Ctrl+K shortcut (inside GlobalSearch) and the header trigger button
 * share the same source of truth.
 */
interface UiState {
  searchOpen: boolean
  openSearch: () => void
  closeSearch: () => void
  setSearchOpen: (open: boolean) => void
}

export const useUiStore = create<UiState>()((set) => ({
  searchOpen: false,
  openSearch: () => set({ searchOpen: true }),
  closeSearch: () => set({ searchOpen: false }),
  setSearchOpen: (open) => set({ searchOpen: open }),
}))
