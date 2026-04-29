import { create } from 'zustand';

interface HerbicideStore {
  selectedForCompare: string[];
  toggleSelection: (productKey: string) => void;
  clearSelection: () => void;
  // Insecticides
  selectedInsecticidesForCompare: string[];
  toggleInsecticideSelection: (productKey: string) => void;
  clearInsecticideSelection: () => void;
  // Fungicides
  selectedFungicidesForCompare: string[];
  toggleFungicideSelection: (productKey: string) => void;
  clearFungicideSelection: () => void;
  // Seed Treatments
  selectedSeedTreatmentsForCompare: string[];
  toggleSeedTreatmentSelection: (productKey: string) => void;
  clearSeedTreatmentSelection: () => void;
}

export const useHerbicideStore = create<HerbicideStore>((set, get) => ({
  selectedForCompare: [],
  
  toggleSelection: (productKey: string) => {
    const current = get().selectedForCompare;
    if (current.includes(productKey)) {
      set({ selectedForCompare: current.filter(k => k !== productKey) });
    } else if (current.length < 2) {
      set({ selectedForCompare: [...current, productKey] });
    }
  },
  
  clearSelection: () => {
    set({ selectedForCompare: [] });
  },

  // Insecticides
  selectedInsecticidesForCompare: [],

  toggleInsecticideSelection: (productKey: string) => {
    const current = get().selectedInsecticidesForCompare;
    if (current.includes(productKey)) {
      set({ selectedInsecticidesForCompare: current.filter(k => k !== productKey) });
    } else if (current.length < 2) {
      set({ selectedInsecticidesForCompare: [...current, productKey] });
    }
  },

  clearInsecticideSelection: () => {
    set({ selectedInsecticidesForCompare: [] });
  },

  // Fungicides
  selectedFungicidesForCompare: [],

  toggleFungicideSelection: (productKey: string) => {
    const current = get().selectedFungicidesForCompare;
    if (current.includes(productKey)) {
      set({ selectedFungicidesForCompare: current.filter(k => k !== productKey) });
    } else if (current.length < 2) {
      set({ selectedFungicidesForCompare: [...current, productKey] });
    }
  },

  clearFungicideSelection: () => {
    set({ selectedFungicidesForCompare: [] });
  },

  // Seed Treatments
  selectedSeedTreatmentsForCompare: [],

  toggleSeedTreatmentSelection: (productKey: string) => {
    const current = get().selectedSeedTreatmentsForCompare;
    if (current.includes(productKey)) {
      set({ selectedSeedTreatmentsForCompare: current.filter(k => k !== productKey) });
    } else if (current.length < 2) {
      set({ selectedSeedTreatmentsForCompare: [...current, productKey] });
    }
  },

  clearSeedTreatmentSelection: () => {
    set({ selectedSeedTreatmentsForCompare: [] });
  },
}));
