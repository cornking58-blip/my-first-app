import { Platform } from 'react-native';

const STORAGE_KEY = 'baikov_ai_client_id';
let memoryClientId: string | null = null;

const createClientId = () => {
  const randomPart = Math.random().toString(36).slice(2, 14);
  return `baikov-${Date.now().toString(36)}-${randomPart}`;
};

export const getAIClientId = async () => {
  if (memoryClientId) return memoryClientId;

  if (Platform.OS === 'web' && typeof window !== 'undefined') {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored) {
      memoryClientId = stored;
      return stored;
    }

    const created = createClientId();
    window.localStorage.setItem(STORAGE_KEY, created);
    memoryClientId = created;
    return created;
  }

  memoryClientId = createClientId();
  return memoryClientId;
};
