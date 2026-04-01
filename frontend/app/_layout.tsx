import { Stack, useGlobalSearchParams } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { useEffect } from 'react';
import { setToken } from '../src/api';

export default function RootLayout() {
  const { token } = useGlobalSearchParams<{ token?: string }>();

  useEffect(() => {
    if (token) {
      setToken(token as string);
    }
  }, [token]);

  return (
    <SafeAreaProvider>
      <StatusBar style="dark" />
      <Stack
        screenOptions={{
          headerShown: false,
          animation: 'slide_from_right',
          contentStyle: { backgroundColor: '#FFFFFF' },
        }}
      >
        <Stack.Screen name="index" />
        <Stack.Screen name="product/[key]" />
        <Stack.Screen name="compare" />
      </Stack>
    </SafeAreaProvider>
  );
}
