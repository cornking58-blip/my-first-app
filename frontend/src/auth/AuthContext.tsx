import React, { createContext, useContext, useEffect, useState } from 'react';
import axios from 'axios';
import { getAIClientId } from '../utils/clientIdentity';
import {
  clearStoredAuthToken,
  getStoredAuthToken,
  setStoredAuthToken,
} from './sessionStorage';

const API_URL = process.env.EXPO_PUBLIC_BACKEND_URL || '';

export type AccessPlan = 'free' | 'trial' | 'pro';

export interface AuthUser {
  id: string;
  name: string;
  email: string;
  marketing_consent: boolean;
  access: {
    plan: AccessPlan;
    trial_ends_at?: string | null;
    pro_until?: string | null;
    subscription_status: string;
    can_use_ai: boolean;
  };
}

interface RequestCodeResult {
  sent: boolean;
  expires_in_seconds: number;
  dev_code?: string;
}

interface AuthContextValue {
  loading: boolean;
  token: string | null;
  user: AuthUser | null;
  requestCode: (
    name: string,
    email: string,
    marketingConsent: boolean,
  ) => Promise<RequestCodeResult>;
  verifyCode: (name: string, email: string, code: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshAccount: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [loading, setLoading] = useState(true);
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<AuthUser | null>(null);

  const clearSession = async () => {
    await clearStoredAuthToken();
    setToken(null);
    setUser(null);
  };

  const loadAccount = async (nextToken: string) => {
    const response = await axios.get(`${API_URL}/api/auth/me`, {
      headers: { Authorization: `Bearer ${nextToken}` },
    });
    setToken(nextToken);
    setUser(response.data.user);
  };

  useEffect(() => {
    const restoreSession = async () => {
      const storedToken = await getStoredAuthToken();
      if (storedToken) {
        try {
          await loadAccount(storedToken);
        } catch {
          await clearSession();
        }
      }
      setLoading(false);
    };
    restoreSession();
  }, []);

  const requestCode = async (
    name: string,
    email: string,
    marketingConsent: boolean,
  ) => {
    const response = await axios.post(`${API_URL}/api/auth/request-code`, {
      name: name.trim(),
      email: email.trim().toLowerCase(),
      marketing_consent: marketingConsent,
    });
    return response.data as RequestCodeResult;
  };

  const verifyCode = async (name: string, email: string, code: string) => {
    const clientId = await getAIClientId();
    const response = await axios.post(`${API_URL}/api/auth/verify-code`, {
      name: name.trim(),
      email: email.trim().toLowerCase(),
      code,
      client_id: clientId,
    });
    const nextToken = response.data.access_token as string;
    await setStoredAuthToken(nextToken);
    setToken(nextToken);
    setUser(response.data.user);
  };

  const logout = async () => {
    await clearSession();
  };

  const refreshAccount = async () => {
    if (!token) return;
    await loadAccount(token);
  };

  const value: AuthContextValue = {
    loading,
    token,
    user,
    requestCode,
    verifyCode,
    logout,
    refreshAccount,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used inside AuthProvider');
  }
  return context;
}
