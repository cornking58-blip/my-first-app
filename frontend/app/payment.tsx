import React, { useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Linking,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import axios from 'axios';
import { AIAuthGate } from '../src/components/AIAuthGate';
import { AmbientBackground } from '../src/components/AmbientBackground';
import { BrandLogo } from '../src/components/BrandLogo';
import { useAuth } from '../src/auth/AuthContext';
import { colors } from '../src/theme/colors';

const API_URL = process.env.EXPO_PUBLIC_BACKEND_URL || '';

type PaymentStatus = 'pending' | 'succeeded' | 'canceled';

type PaymentRecord = {
  id: string;
  provider: 'mock' | 'yookassa';
  provider_payment_id?: string | null;
  status: PaymentStatus;
  paid: boolean;
  test: boolean;
  amount: string;
  currency: string;
  plan: string;
  duration_days: number;
  confirmation_url?: string | null;
  created_at: string;
  activated_at?: string | null;
  pro_until?: string | null;
};

type PaymentConfig = {
  mode: 'mock' | 'yookassa';
  test: boolean;
  price: number;
  currency: string;
  duration_days: number;
  provider_ready: boolean;
};

const STATUS_TEXT: Record<PaymentStatus, string> = {
  pending: 'Ожидает подтверждения',
  succeeded: 'Оплата подтверждена',
  canceled: 'Платёж отменён',
};

function formatDate(value?: string | null) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return new Intl.DateTimeFormat('ru-RU', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
}

export default function PaymentScreen() {
  const router = useRouter();
  const { loading: authLoading, token, user, refreshAccount } = useAuth();
  const [config, setConfig] = useState<PaymentConfig | null>(null);
  const [history, setHistory] = useState<PaymentRecord[]>([]);
  const [current, setCurrent] = useState<PaymentRecord | null>(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const authHeaders = token ? { Authorization: `Bearer ${token}` } : undefined;

  const loadConfig = async () => {
    const response = await axios.get(`${API_URL}/api/payments/config`);
    setConfig(response.data);
  };

  const loadHistory = async () => {
    if (!token) return;
    const response = await axios.get(`${API_URL}/api/payments/history`, { headers: authHeaders });
    const payments = response.data.payments || [];
    setHistory(payments);
    const pending = payments.find((item: PaymentRecord) => item.status === 'pending');
    setCurrent(pending || payments[0] || null);
  };

  useEffect(() => {
    loadConfig().catch(() => setMessage('Не удалось загрузить настройки оплаты.'));
  }, []);

  useEffect(() => {
    if (token) {
      loadHistory().catch(() => setMessage('Не удалось загрузить историю платежей.'));
    }
  }, [token]);

  const createPayment = async () => {
    if (!token || loading) return;
    setLoading(true);
    setMessage(null);
    try {
      const response = await axios.post(`${API_URL}/api/payments/pro/create`, {}, { headers: authHeaders });
      const payment = response.data.payment as PaymentRecord;
      setCurrent(payment);
      await loadHistory();
      if (payment.confirmation_url) {
        await Linking.openURL(payment.confirmation_url);
      } else {
        setMessage('Тестовый платёж создан. Подтвердите его кнопкой ниже.');
      }
    } catch (error: any) {
      setMessage(error?.response?.data?.detail || 'Не удалось создать платёж.');
    } finally {
      setLoading(false);
    }
  };

  const completeMock = async () => {
    if (!token || !current || loading) return;
    setLoading(true);
    setMessage(null);
    try {
      const response = await axios.post(
        `${API_URL}/api/payments/mock/${current.id}/complete`,
        {},
        { headers: authHeaders },
      );
      setCurrent(response.data.payment);
      await refreshAccount();
      await loadHistory();
      setMessage('Тестовая оплата подтверждена. PRO активирован на 30 дней.');
    } catch (error: any) {
      setMessage(error?.response?.data?.detail || 'Не удалось подтвердить тестовый платёж.');
    } finally {
      setLoading(false);
    }
  };

  const checkStatus = async () => {
    if (!token || !current || loading) return;
    setLoading(true);
    setMessage(null);
    try {
      const response = await axios.get(`${API_URL}/api/payments/${current.id}`, { headers: authHeaders });
      setCurrent(response.data.payment);
      if (response.data.payment.status === 'succeeded') {
        await refreshAccount();
        setMessage('Оплата подтверждена. PRO активирован.');
      } else {
        setMessage('Платёж пока ожидает подтверждения.');
      }
      await loadHistory();
    } catch (error: any) {
      setMessage(error?.response?.data?.detail || 'Не удалось проверить платёж.');
    } finally {
      setLoading(false);
    }
  };

  if (authLoading) {
    return (
      <SafeAreaView style={styles.container} edges={['top']}>
        <AmbientBackground />
        <View style={styles.centerState}>
          <ActivityIndicator color={colors.primaryBright} />
          <Text style={styles.muted}>Загружаем оплату...</Text>
        </View>
      </SafeAreaView>
    );
  }

  if (!user) {
    return (
      <AIAuthGate
        onBack={() => router.back()}
        detailsTitle="Войдите для оформления PRO"
        detailsSubtitle="Платёж будет связан с вашим аккаунтом и автоматически включит PRO."
      />
    );
  }

  const isOwner = user.access.plan === 'owner';
  const isMock = (current?.provider || config?.mode) === 'mock';

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <AmbientBackground />
      <View style={styles.header}>
        <TouchableOpacity style={styles.headerButton} onPress={() => router.back()}>
          <Ionicons name="arrow-back" size={22} color={colors.text} />
        </TouchableOpacity>
        <BrandLogo compact />
        <View style={styles.headerSpacer} />
      </View>

      <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.title}>bAIkov PRO</Text>
        <Text style={styles.subtitle}>Тестируем полный цикл оплаты без списания настоящих денег.</Text>

        <View style={styles.testNotice}>
          <Ionicons name="flask-outline" size={19} color={colors.primaryBright} />
          <View style={styles.noticeTextBlock}>
            <Text style={styles.noticeTitle}>Тестовый режим</Text>
            <Text style={styles.noticeText}>
              Сейчас платёж только имитируется. Реальные карты и деньги не используются.
            </Text>
          </View>
        </View>

        <View style={styles.tariffCard}>
          <View style={styles.priceRow}>
            <View>
              <Text style={styles.tariffName}>PRO на 30 дней</Text>
              <Text style={styles.tariffCaption}>Расширенные AI-лимиты</Text>
            </View>
            <Text style={styles.price}>{config?.price || 740} ₽</Text>
          </View>
          <View style={styles.divider} />
          <Text style={styles.feature}>80 обычных AI-запросов</Text>
          <Text style={styles.feature}>10 поисков в интернете</Text>
          <Text style={styles.feature}>15 фотодиагностик</Text>
          <Text style={styles.feature}>Справочник и сравнение без ограничений</Text>
        </View>

        {isOwner ? (
          <View style={styles.ownerCard}>
            <Ionicons name="infinite-outline" size={20} color={colors.primaryBright} />
            <Text style={styles.ownerText}>У владельца уже включён безлимитный доступ.</Text>
          </View>
        ) : (
          <TouchableOpacity
            style={[styles.primaryButton, loading && styles.buttonDisabled]}
            onPress={createPayment}
            disabled={loading}
          >
            {loading ? (
              <ActivityIndicator color={colors.white} />
            ) : (
              <>
                <Text style={styles.primaryButtonText}>
                  {user.access.plan === 'pro' ? 'Продлить PRO' : 'Создать тестовый платёж'}
                </Text>
                <Ionicons name="arrow-forward" size={18} color={colors.white} />
              </>
            )}
          </TouchableOpacity>
        )}

        {current ? (
          <View style={styles.paymentCard}>
            <View style={styles.paymentHeader}>
              <Text style={styles.sectionTitle}>Текущий платёж</Text>
              <Text style={[
                styles.status,
                current.status === 'succeeded' && styles.statusSuccess,
                current.status === 'canceled' && styles.statusCanceled,
              ]}>
                {STATUS_TEXT[current.status]}
              </Text>
            </View>
            <Text style={styles.paymentId}>{current.id}</Text>
            <Text style={styles.paymentMeta}>{current.amount} ₽ · {formatDate(current.created_at)}</Text>

            {current.status === 'pending' && isMock ? (
              <TouchableOpacity style={styles.secondaryButton} onPress={completeMock} disabled={loading}>
                <Ionicons name="checkmark-circle-outline" size={18} color={colors.primaryBright} />
                <Text style={styles.secondaryButtonText}>Подтвердить тестовую оплату</Text>
              </TouchableOpacity>
            ) : null}

            {current.status === 'pending' && current.confirmation_url ? (
              <TouchableOpacity
                style={styles.secondaryButton}
                onPress={() => Linking.openURL(current.confirmation_url as string)}
              >
                <Ionicons name="open-outline" size={18} color={colors.primaryBright} />
                <Text style={styles.secondaryButtonText}>Открыть страницу ЮKassa</Text>
              </TouchableOpacity>
            ) : null}

            {current.status === 'pending' ? (
              <TouchableOpacity style={styles.secondaryButton} onPress={checkStatus} disabled={loading}>
                <Ionicons name="refresh-outline" size={18} color={colors.primaryBright} />
                <Text style={styles.secondaryButtonText}>Проверить статус</Text>
              </TouchableOpacity>
            ) : null}
          </View>
        ) : null}

        {message ? <Text style={styles.message}>{message}</Text> : null}

        {history.length > 0 ? (
          <View style={styles.historySection}>
            <Text style={styles.sectionTitle}>История платежей</Text>
            {history.map(item => (
              <View key={item.id} style={styles.historyRow}>
                <View>
                  <Text style={styles.historyAmount}>{item.amount} ₽</Text>
                  <Text style={styles.historyDate}>{formatDate(item.created_at)}</Text>
                </View>
                <Text style={styles.historyStatus}>{STATUS_TEXT[item.status]}</Text>
              </View>
            ))}
          </View>
        ) : null}

        <TouchableOpacity style={styles.backToAccount} onPress={() => router.replace('/account' as never)}>
          <Text style={styles.backToAccountText}>Вернуться в личный кабинет</Text>
        </TouchableOpacity>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  header: {
    height: 58,
    paddingHorizontal: 18,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  headerButton: {
    width: 38,
    height: 38,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: colors.border,
  },
  headerSpacer: { width: 38 },
  content: { padding: 18, paddingBottom: 42 },
  title: { color: colors.text, fontSize: 28, fontWeight: '800' },
  subtitle: { color: colors.textSecondary, fontSize: 14, lineHeight: 20, marginTop: 7 },
  testNotice: {
    marginTop: 18,
    padding: 14,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: colors.primaryBorder,
    flexDirection: 'row',
    backgroundColor: colors.surface,
  },
  noticeTextBlock: { flex: 1, marginLeft: 11 },
  noticeTitle: { color: colors.text, fontSize: 14, fontWeight: '750' },
  noticeText: { color: colors.textMuted, fontSize: 12, lineHeight: 17, marginTop: 4 },
  tariffCard: {
    marginTop: 14,
    padding: 17,
    borderRadius: 18,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
  },
  priceRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  tariffName: { color: colors.text, fontSize: 19, fontWeight: '800' },
  tariffCaption: { color: colors.textMuted, fontSize: 12, marginTop: 4 },
  price: { color: colors.primaryBright, fontSize: 25, fontWeight: '850' },
  divider: { height: 1, backgroundColor: colors.border, marginVertical: 15 },
  feature: { color: colors.textSecondary, fontSize: 13, marginBottom: 9 },
  primaryButton: {
    marginTop: 14,
    minHeight: 52,
    paddingHorizontal: 18,
    borderRadius: 16,
    backgroundColor: colors.primary,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 9,
  },
  primaryButtonText: { color: colors.white, fontSize: 14, fontWeight: '800' },
  buttonDisabled: { opacity: 0.6 },
  ownerCard: {
    marginTop: 14,
    padding: 15,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: colors.primaryBorder,
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
  },
  ownerText: { color: colors.textSecondary, fontSize: 13, marginLeft: 10, flex: 1 },
  paymentCard: {
    marginTop: 18,
    padding: 16,
    borderRadius: 18,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
  },
  paymentHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  sectionTitle: { color: colors.text, fontSize: 16, fontWeight: '800' },
  status: { color: colors.primaryBright, fontSize: 11, fontWeight: '750' },
  statusSuccess: { color: colors.success },
  statusCanceled: { color: colors.error },
  paymentId: { color: colors.textMuted, fontSize: 10, marginTop: 12 },
  paymentMeta: { color: colors.textSecondary, fontSize: 12, marginTop: 5 },
  secondaryButton: {
    minHeight: 44,
    marginTop: 12,
    paddingHorizontal: 14,
    borderRadius: 13,
    borderWidth: 1,
    borderColor: colors.primaryBorder,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
  },
  secondaryButtonText: { color: colors.primaryBright, fontSize: 12, fontWeight: '750' },
  message: {
    color: colors.textSecondary,
    fontSize: 12,
    lineHeight: 18,
    marginTop: 14,
    paddingHorizontal: 4,
  },
  historySection: { marginTop: 24 },
  historyRow: {
    marginTop: 9,
    padding: 13,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  historyAmount: { color: colors.text, fontSize: 13, fontWeight: '750' },
  historyDate: { color: colors.textMuted, fontSize: 10, marginTop: 4 },
  historyStatus: { color: colors.textSecondary, fontSize: 10, maxWidth: 130, textAlign: 'right' },
  backToAccount: { alignItems: 'center', marginTop: 24, paddingVertical: 12 },
  backToAccountText: { color: colors.textSecondary, fontSize: 12, fontWeight: '650' },
  centerState: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 10 },
  muted: { color: colors.textMuted, fontSize: 12 },
});
