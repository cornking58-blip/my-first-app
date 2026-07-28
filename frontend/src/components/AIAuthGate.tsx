import React, { useState } from 'react';
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { isAxiosError } from 'axios';
import { AmbientBackground } from './AmbientBackground';
import { BrandLogo } from './BrandLogo';
import { useAuth } from '../auth/AuthContext';
import { colors, shadows } from '../theme/colors';

type Step = 'details' | 'code';

interface AIAuthGateProps {
  onBack: () => void;
  detailsTitle?: string;
  detailsSubtitle?: string;
}

export function AIAuthGate({ onBack, detailsTitle, detailsSubtitle }: AIAuthGateProps) {
  const { requestCode, verifyCode } = useAuth();
  const [step, setStep] = useState<Step>('details');
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [marketingConsent, setMarketingConsent] = useState(false);
  const [code, setCode] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [devCode, setDevCode] = useState<string | null>(null);

  const getErrorText = (requestError: unknown) => {
    if (isAxiosError(requestError)) {
      const detail = requestError.response?.data?.detail;
      if (typeof detail === 'string') return detail;
    }
    return 'Не удалось выполнить вход. Попробуйте ещё раз.';
  };

  const handleRequestCode = async () => {
    if (name.trim().length < 2 || !email.includes('@') || loading) return;
    setLoading(true);
    setError(null);
    try {
      const response = await requestCode(name, email, marketingConsent);
      setDevCode(response.dev_code || null);
      setStep('code');
    } catch (requestError) {
      setError(getErrorText(requestError));
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyCode = async () => {
    if (code.length !== 6 || loading) return;
    setLoading(true);
    setError(null);
    try {
      await verifyCode(name, email, code);
    } catch (requestError) {
      setError(getErrorText(requestError));
    } finally {
      setLoading(false);
    }
  };

  return (
    <View style={styles.container}>
      <AmbientBackground />
      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      >
        <View style={styles.header}>
          <TouchableOpacity style={styles.headerButton} onPress={onBack}>
            <Ionicons name="arrow-back" size={22} color={colors.text} />
          </TouchableOpacity>
          <BrandLogo compact />
          <View style={styles.headerSpacer} />
        </View>

        <ScrollView
          contentContainerStyle={styles.content}
          keyboardShouldPersistTaps="handled"
        >
          <View style={styles.icon}>
            <Ionicons name="sparkles" size={28} color={colors.white} />
          </View>
          <Text style={styles.title}>
            {step === 'details' ? (detailsTitle || 'Откройте bAIkov AI') : 'Введите код из письма'}
          </Text>
          <Text style={styles.subtitle}>
            {step === 'details'
              ? (detailsSubtitle || '5 дней профессионального AI-доступа бесплатно. Банковская карта не нужна.')
              : `Мы отправили шестизначный код на ${email.trim().toLowerCase()}`}
          </Text>

          <View style={styles.card}>
            {step === 'details' ? (
              <>
                <Text style={styles.label}>Ваше имя</Text>
                <TextInput
                  style={styles.input}
                  placeholder="Например, Павел"
                  placeholderTextColor={colors.textMuted}
                  value={name}
                  onChangeText={setName}
                  autoCapitalize="words"
                  maxLength={80}
                />
                <Text style={styles.label}>Электронная почта</Text>
                <TextInput
                  style={styles.input}
                  placeholder="name@example.ru"
                  placeholderTextColor={colors.textMuted}
                  value={email}
                  onChangeText={setEmail}
                  keyboardType="email-address"
                  autoCapitalize="none"
                  autoCorrect={false}
                  maxLength={254}
                />
                <TouchableOpacity
                  style={styles.consentRow}
                  onPress={() => setMarketingConsent(current => !current)}
                  activeOpacity={0.75}
                  accessibilityRole="checkbox"
                  accessibilityState={{ checked: marketingConsent }}
                >
                  <Ionicons
                    name={marketingConsent ? 'checkbox' : 'square-outline'}
                    size={22}
                    color={marketingConsent ? colors.primaryBright : colors.textMuted}
                  />
                  <Text style={styles.consentText}>
                    Хочу получать новости, полезные материалы и специальные предложения bAIkov по электронной почте. Это необязательно.
                  </Text>
                </TouchableOpacity>
                <TouchableOpacity
                  style={[
                    styles.primaryButton,
                    (name.trim().length < 2 || !email.includes('@') || loading) && styles.buttonDisabled,
                  ]}
                  onPress={handleRequestCode}
                  disabled={name.trim().length < 2 || !email.includes('@') || loading}
                >
                  {loading
                    ? <ActivityIndicator size="small" color={colors.white} />
                    : <Text style={styles.primaryButtonText}>Получить код</Text>}
                </TouchableOpacity>
                <Text style={styles.legal}>
                  Продолжая, вы соглашаетесь с пользовательским соглашением и политикой конфиденциальности.
                </Text>
              </>
            ) : (
              <>
                <Text style={styles.label}>Код подтверждения</Text>
                <TextInput
                  style={[styles.input, styles.codeInput]}
                  placeholder="000000"
                  placeholderTextColor={colors.textMuted}
                  value={code}
                  onChangeText={value => setCode(value.replace(/\D/g, '').slice(0, 6))}
                  keyboardType="number-pad"
                  textContentType="oneTimeCode"
                  autoFocus
                  maxLength={6}
                />
                {devCode ? (
                  <Text style={styles.devCode}>Тестовый код: {devCode}</Text>
                ) : null}
                <TouchableOpacity
                  style={[
                    styles.primaryButton,
                    (code.length !== 6 || loading) && styles.buttonDisabled,
                  ]}
                  onPress={handleVerifyCode}
                  disabled={code.length !== 6 || loading}
                >
                  {loading
                    ? <ActivityIndicator size="small" color={colors.white} />
                    : <Text style={styles.primaryButtonText}>Войти</Text>}
                </TouchableOpacity>
                <TouchableOpacity
                  style={styles.secondaryButton}
                  onPress={() => {
                    setCode('');
                    setError(null);
                    setStep('details');
                  }}
                >
                  <Text style={styles.secondaryButtonText}>Изменить почту</Text>
                </TouchableOpacity>
              </>
            )}

            {error ? (
              <View style={styles.error}>
                <Ionicons name="alert-circle-outline" size={17} color={colors.danger} />
                <Text style={styles.errorText}>{error}</Text>
              </View>
            ) : null}
          </View>

          <View style={styles.features}>
            <View style={styles.feature}>
              <Ionicons name="chatbubbles-outline" size={17} color={colors.primaryBright} />
              <Text style={styles.featureText}>История сохранится в вашем аккаунте</Text>
            </View>
            <View style={styles.feature}>
              <Ionicons name="phone-portrait-outline" size={17} color={colors.primaryBright} />
              <Text style={styles.featureText}>Один аккаунт на всех устройствах</Text>
            </View>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  flex: { flex: 1 },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
    backgroundColor: 'rgba(7,10,28,0.9)',
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  headerButton: {
    width: 40,
    height: 40,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 13,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
  },
  headerSpacer: { width: 40 },
  content: {
    flexGrow: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 20,
    paddingBottom: 24,
  },
  icon: {
    width: 62,
    height: 62,
    borderRadius: 21,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.primary,
    borderWidth: 1,
    borderColor: colors.primaryBright,
    ...shadows.glow,
  },
  title: {
    color: colors.text,
    fontSize: 24,
    fontWeight: '800',
    textAlign: 'center',
    marginTop: 18,
  },
  subtitle: {
    maxWidth: 430,
    color: colors.textSecondary,
    fontSize: 13,
    lineHeight: 19,
    textAlign: 'center',
    marginTop: 8,
  },
  card: {
    width: '100%',
    maxWidth: 430,
    marginTop: 24,
    padding: 18,
    borderRadius: 18,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.borderStrong,
    ...shadows.card,
  },
  label: {
    color: colors.textSecondary,
    fontSize: 11,
    fontWeight: '700',
    marginBottom: 7,
    marginTop: 4,
  },
  input: {
    minHeight: 50,
    color: colors.text,
    fontSize: 15,
    paddingHorizontal: 14,
    borderRadius: 13,
    backgroundColor: colors.surfaceElevated,
    borderWidth: 1,
    borderColor: colors.border,
    marginBottom: 14,
    outlineStyle: 'none',
  } as any,
  codeInput: {
    textAlign: 'center',
    fontSize: 24,
    fontWeight: '800',
    letterSpacing: 8,
  },
  primaryButton: {
    minHeight: 50,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 14,
    backgroundColor: colors.primary,
    marginTop: 4,
  },
  buttonDisabled: { opacity: 0.45 },
  primaryButtonText: { color: colors.white, fontSize: 14, fontWeight: '800' },
  consentRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 9,
    marginBottom: 12,
  },
  consentText: {
    flex: 1,
    color: colors.textSecondary,
    fontSize: 10,
    lineHeight: 15,
  },
  secondaryButton: { alignItems: 'center', paddingVertical: 12 },
  secondaryButtonText: { color: colors.primaryBright, fontSize: 12, fontWeight: '700' },
  legal: {
    color: colors.textMuted,
    fontSize: 9,
    lineHeight: 14,
    textAlign: 'center',
    marginTop: 12,
  },
  devCode: {
    color: colors.warning,
    fontSize: 12,
    textAlign: 'center',
    marginTop: -4,
    marginBottom: 12,
  },
  error: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 10,
    borderRadius: 11,
    backgroundColor: colors.dangerSoft,
    marginTop: 12,
  },
  errorText: { flex: 1, color: colors.text, fontSize: 11, marginLeft: 7 },
  features: { width: '100%', maxWidth: 430, marginTop: 18, gap: 9 },
  feature: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8 },
  featureText: { color: colors.textMuted, fontSize: 10 },
});
