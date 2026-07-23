import { Platform } from 'react-native';
import * as SecureStore from 'expo-secure-store';

const TOKEN_KEY = 'baikov_auth_token';

export const getStoredAuthToken = async () => {
  if (Platform.OS === 'web' && typeof window !== 'undefined') {
    return window.localStorage.getItem(TOKEN_KEY);
  }
  return SecureStore.getItemAsync(TOKEN_KEY);
};

export const setStoredAuthToken = async (token: string) => {
  if (Platform.OS === 'web' && typeof window !== 'undefined') {
    window.localStorage.setItem(TOKEN_KEY, token);
    return;
  }
  await SecureStore.setItemAsync(TOKEN_KEY, token);
};

export const clearStoredAuthToken = async () => {
  if (Platform.OS === 'web' && typeof window !== 'undefined') {
    window.localStorage.removeItem(TOKEN_KEY);
    return;
  }
  await SecureStore.deleteItemAsync(TOKEN_KEY);
};
