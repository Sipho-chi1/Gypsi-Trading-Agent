/**
 * Lightweight UI store — sidebar/mobile-nav + layout state.
 * Not for server data (that belongs in TanStack Query).
 */

import { create } from "zustand";

interface UiState {
  /** Desktop sidebar collapsed (icon rail). */
  sidebarCollapsed: boolean;
  /** Mobile slide-in drawer open. */
  mobileNavOpen: boolean;
  setSidebarCollapsed: (v: boolean) => void;
  setMobileNavOpen: (v: boolean) => void;
}

export const useUiStore = create<UiState>()((set) => ({
  sidebarCollapsed: false,
  mobileNavOpen: false,
  setSidebarCollapsed: (sidebarCollapsed) => set({ sidebarCollapsed }),
  setMobileNavOpen: (mobileNavOpen) => set({ mobileNavOpen }),
}));
