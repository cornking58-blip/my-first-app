import axios from 'axios';

const API_URL = process.env.EXPO_PUBLIC_BACKEND_URL || '';

// Токен хранится здесь — один раз установили, везде работает
let _token: string | null = null;

export function setToken(token: string) {
  _token = token;
}

export function getToken(): string | null {
  return _token;
}

// Axios-инстанс с автоматической подстановкой токена
export const api = axios.create({ baseURL: API_URL });

api.interceptors.request.use((config) => {
  if (_token) {
    config.params = { ...config.params, token: _token };
  }
  return config;
});
