import { create } from 'zustand';

interface HerbicideStore {
  selectedForCompare: string[];
  toggleSelection: (productKey: string) => void;
  clearSelection: () => void;
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
}));
