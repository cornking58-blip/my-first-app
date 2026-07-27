import { useCallback, useState } from 'react';
import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { colors } from '../src/theme/colors';
import { AuthProvider } from '../src/auth/AuthContext';
import { SplashIntro } from '../src/components/SplashIntro';

export default function RootLayout() {
  const [showIntro, setShowIntro] = useState(true);
  const finishIntro = useCallback(() => setShowIntro(false), []);

  return (
    <SafeAreaProvider>
      <AuthProvider>
        <StatusBar style="light" backgroundColor={colors.backgroundDeep} />
        <Stack
          screenOptions={{
            headerShown: false,
            animation: 'slide_from_right',
            contentStyle: { backgroundColor: colors.background },
          }}
        >
          <Stack.Screen name="(tabs)" />
          <Stack.Screen name="product/[key]" />
          <Stack.Screen name="compare" />
          <Stack.Screen name="ai" />
          <Stack.Screen name="photo-diagnosis" />
          <Stack.Screen name="insecticide-product/[key]" />
          <Stack.Screen name="insecticide-compare" />
          <Stack.Screen name="seed-treatment-product/[key]" />
          <Stack.Screen name="seed-treatment-compare" />
        </Stack>
        {showIntro ? <SplashIntro onFinish={finishIntro} /> : null}
      </AuthProvider>
    </SafeAreaProvider>
  );
}
