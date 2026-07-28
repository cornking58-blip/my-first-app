import React, { useEffect } from 'react';
import {
  ActivityIndicator,
  Alert,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { AIAuthGate } from '../src/components/AIAuthGate';
import { AmbientBackground } from '../src/components/AmbientBackground';
import { BrandLogo } from '../src/components/BrandLogo';
import { useAuth, type AccessPlan, type UsageItem } from '../src/auth/AuthContext';
import { colors } from '../src/theme/colors';

const PLAN_TITLES: Record<AccessPlan, string> = {
  free: 'Бесплатный доступ',
  trial: 'Пробный период',
  pro: 'bAIkov PRO',
  owner: 'Владелец',
};

const PLAN_DESCRIPTIONS: Record<AccessPlan, string> = {
  free: 'Справочник доступен. AI-функции требуют PRO.',
  trial: 'Полный доступ к AI-функциям на 5 дней.',
  pro: 'Расширенные месячные лимиты AI-функций.',
  owner: 'Все функции доступны без ограничений.',
};

const USAGE_ICONS: Record<string, keyof typeof Ionicons.glyphMap> = {
  ai_requests: 'sparkles-outline',
  web_requests: 'globe-outline',
  photo_diagnostics: 'camera-outline',
};

function formatDate(value?: string | null) {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return new Intl.DateTimeFormat('ru-RU', {
    day: '2-digit',
    month: 'long',
    year: 'numeric',
  }).format(date);
}

function UsageRow({ itemKey, item, unlimited }: {
  itemKey: string;
  item?: UsageItem;
  unlimited: boolean;
}) {
  const limit = item?.limit ?? 0;
  const used = item?.used ?? 0;
  const progress = unlimited || limit <= 0 ? 0 : Math.min(1, used / limit);

  return (
    <View style={styles.usageRow}>
      <View style={styles.usageHeader}>
        <View style={styles.usageTitleRow}>
          <View style={styles.usageIcon}>
            <Ionicons
              name={USAGE_ICONS[itemKey] || 'ellipse-outline'}
              size={17}
              color={colors.primaryBright}
            />
          </View>
          <Text style={styles.usageLabel}>{item?.label || itemKey}</Text>
        </View>
        <Text style={styles.usageValue}>
          {unlimited ? 'Без ограничений' : `${item?.remaining ?? 0} из ${limit}`}
        </Text>
      </View>
      {!unlimited ? (
        <View style={styles.progressTrack}>
          <View style={[styles.progressFill, { width: `${progress * 100}%` }]} />
        </View>
      ) : null}
      {!unlimited ? (
        <Text style={styles.usageCaption}>Использовано: {used}</Text>
      ) : null}
    </View>
  );
}

export default function AccountScreen() {
  const router = useRouter();
  const { loading, user, usage, logout, refreshAccount } = useAuth();

  useEffect(() => {
    refreshAccount().catch(() => undefined);
  }, []);

  if (loading) {
    return (
      <SafeAreaView style={styles.container} edges={['top']}>
        <AmbientBackground />
        <View style={styles.centerState}>
          <ActivityIndicator color={colors.primaryBright} />
          <Text style={styles.centerText}>Загружаем кабинет...</Text>
        </View>
      </SafeAreaView>
    );
  }

  if (!user) {
    return (
      <AIAuthGate
        onBack={() => router.back()}
        detailsTitle="Войдите в личный кабинет"
        detailsSubtitle="Здесь будут ваш тариф, срок доступа и остатки AI-лимитов."
      />
    );
  }

  const plan = usage?.plan || user.access.plan;
  const periodEnd = formatDate(usage?.period_ends_at || user.access.trial_ends_at || user.access.pro_until);
  const unlimited = Boolean(usage?.unlimited || plan === 'owner');

  const handleLogout = () => {
    Alert.alert('Выйти из аккаунта?', 'История чатов останется в вашем аккаунте.', [
      { text: 'Отмена', style: 'cancel' },
      {
        text: 'Выйти',
        style: 'destructive',
        onPress: async () => {
          await logout();
          router.replace('/' as never);
        },
      },
    ]);
  };

  const handlePro = () => {
    Alert.alert(
      'bAIkov PRO — 740 ₽/месяц',
      'Тариф и лимиты уже зафиксированы. Подключение оплаты — следующий этап разработки.',
      [{ text: 'Понятно' }],
    );
  };

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
        <Text style={styles.pageTitle}>Личный кабинет</Text>

        <View style={styles.accountCard}>
          <View style={styles.avatar}>
            <Text style={styles.avatarText}>{(user.name || user.email).slice(0, 1).toUpperCase()}</Text>
          </View>
          <View style={styles.accountInfo}>
            <Text style={styles.userName}>{user.name || 'Пользователь bAIkov'}</Text>
            <Text style={styles.userEmail}>{user.email}</Text>
          </View>
        </View>

        <View style={styles.planCard}>
          <View style={styles.planTopRow}>
            <View>
              <Text style={styles.sectionCaption}>Текущий статус</Text>
              <Text style={styles.planTitle}>{PLAN_TITLES[plan]}</Text>
            </View>
            <View style={styles.planBadge}>
              <Ionicons
                name={plan === 'owner' ? 'infinite-outline' : plan === 'pro' ? 'diamond-outline' : 'time-outline'}
                size={18}
                color={colors.primaryBright}
              />
            </View>
          </View>
          <Text style={styles.planDescription}>{PLAN_DESCRIPTIONS[plan]}</Text>
          {periodEnd ? (
            <Text style={styles.periodText}>
              {plan === 'trial' ? 'Пробный период до' : 'Доступ до'}: {periodEnd}
            </Text>
          ) : null}
        </View>

        <View style={styles.sectionHeader}>
          <Text style={styles.sectionTitle}>Лимиты</Text>
          <TouchableOpacity onPress={() => refreshAccount()}>
            <Ionicons name="refresh-outline" size={19} color={colors.textSecondary} />
          </TouchableOpacity>
        </View>

        <View style={styles.limitsCard}>
          <UsageRow itemKey="ai_requests" item={usage?.items.ai_requests} unlimited={unlimited} />
          <View style={styles.divider} />
          <UsageRow itemKey="web_requests" item={usage?.items.web_requests} unlimited={unlimited} />
          <View style={styles.divider} />
          <UsageRow itemKey="photo_diagnostics" item={usage?.items.photo_diagnostics} unlimited={unlimited} />
        </View>

        <View style={styles.unlimitedCard}>
          <Ionicons name="checkmark-circle-outline" size={20} color={colors.success} />
          <Text style={styles.unlimitedText}>
            Поиск по каталогу, карточки препаратов и сравнение доступны без ограничений.
          </Text>
        </View>

        {plan === 'trial' || plan === 'free' ? (
          <TouchableOpacity style={styles.proButton} onPress={handlePro} activeOpacity={0.82}>
            <View>
              <Text style={styles.proButtonTitle}>Оформить bAIkov PRO</Text>
              <Text style={styles.proButtonSubtitle}>740 ₽ в месяц</Text>
            </View>
            <Ionicons name="arrow-forward" size={21} color={colors.white} />
          </TouchableOpacity>
        ) : null}

        <TouchableOpacity style={styles.logoutButton} onPress={handleLogout}>
          <Ionicons name="log-out-outline" size={20} color={colors.danger} />
          <Text style={styles.logoutText}>Выйти из аккаунта</Text>
        </TouchableOpacity>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    backgroundColor: colors.surfaceGlass,
  },
  headerButton: {
    width: 40,
    height: 40,
    borderRadius: 13,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
  },
  headerSpacer: { width: 40 },
  content: { padding: 18, paddingBottom: 42 },
  pageTitle: { color: colors.text, fontSize: 26, fontWeight: '800', marginBottom: 18 },
  accountCard: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 16,
    borderRadius: 18,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
  },
  avatar: {
    width: 48,
    height: 48,
    borderRadius: 16,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: colors.primaryBorder,
    backgroundColor: colors.primarySoft,
  },
  avatarText: { color: colors.primaryBright, fontSize: 20, fontWeight: '800' },
  accountInfo: { flex: 1, marginLeft: 13 },
  userName: { color: colors.text, fontSize: 17, fontWeight: '750' },
  userEmail: { color: colors.textMuted, fontSize: 12, marginTop: 4 },
  planCard: {
    marginTop: 12,
    padding: 16,
    borderRadius: 18,
    borderWidth: 1,
    borderColor: colors.primaryBorder,
    backgroundColor: colors.surface,
  },
  planTopRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  sectionCaption: { color: colors.textMuted, fontSize: 11, textTransform: 'uppercase', letterSpacing: 0.7 },
  planTitle: { color: colors.text, fontSize: 21, fontWeight: '800', marginTop: 5 },
  planBadge: {
    width: 42,
    height: 42,
    borderRadius: 14,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: colors.primaryBorder,
    backgroundColor: colors.primarySoft,
  },
  planDescription: { color: colors.textSecondary, fontSize: 13, lineHeight: 19, marginTop: 12 },
  periodText: { color: colors.primaryBright, fontSize: 12, fontWeight: '650', marginTop: 10 },
  sectionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 22,
    marginBottom: 9,
  },
  sectionTitle: { color: colors.text, fontSize: 17, fontWeight: '750' },
  limitsCard: {
    paddingHorizontal: 15,
    borderRadius: 18,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
  },
  usageRow: { paddingVertical: 15 },
  usageHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  usageTitleRow: { flexDirection: 'row', alignItems: 'center', flex: 1 },
  usageIcon: {
    width: 32,
    height: 32,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: colors.border,
  },
  usageLabel: { color: colors.text, fontSize: 13, fontWeight: '650', marginLeft: 10 },
  usageValue: { color: colors.textSecondary, fontSize: 12, fontWeight: '700' },
  progressTrack: {
    height: 4,
    borderRadius: 2,
    backgroundColor: colors.border,
    overflow: 'hidden',
    marginTop: 11,
  },
  progressFill: { height: 4, borderRadius: 2, backgroundColor: colors.primaryBright },
  usageCaption: { color: colors.textMuted, fontSize: 10, marginTop: 6 },
  divider: { height: 1, backgroundColor: colors.border },
  unlimitedCard: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    padding: 14,
    marginTop: 12,
    borderRadius: 15,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
  },
  unlimitedText: { flex: 1, color: colors.textSecondary, fontSize: 12, lineHeight: 18, marginLeft: 9 },
  proButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 17,
    paddingVertical: 15,
    marginTop: 16,
    borderRadius: 16,
    backgroundColor: colors.primary,
  },
  proButtonTitle: { color: colors.white, fontSize: 15, fontWeight: '800' },
  proButtonSubtitle: { color: 'rgba(255,255,255,0.72)', fontSize: 11, marginTop: 3 },
  logoutButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 14,
    marginTop: 13,
    borderRadius: 15,
    borderWidth: 1,
    borderColor: 'rgba(255,113,142,0.28)',
    backgroundColor: colors.surface,
  },
  logoutText: { color: colors.danger, fontSize: 13, fontWeight: '700', marginLeft: 8 },
  centerState: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  centerText: { color: colors.textSecondary, fontSize: 13, marginTop: 12 },
});
