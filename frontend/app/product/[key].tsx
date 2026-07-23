import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useLocalSearchParams, useRouter } from 'expo-router';
import axios from 'axios';
import { AmbientBackground } from '../../src/components/AmbientBackground';
import { BrandLogo } from '../../src/components/BrandLogo';
import { RetryErrorCard } from '../../src/components/RetryErrorCard';
import { colors } from '../../src/theme/colors';

const API_URL = process.env.EXPO_PUBLIC_BACKEND_URL || '';

interface Application {
  crop: string | null;
  target_object: string | null;
  rate_raw: string | null;
  application_method: string | null;
  waiting_period: string | null;
  reentry_period_manual: string | null;
  reentry_period_mech: string | null;
  restrictions: string | null;
}

interface ProductCard {
  product_key: string;
  product_name: string;
  formulation: string | null;
  active_substances_raw: string | null;
  manufacturer: string | null;
  display_manufacturer: string | null;
  registration_number: string | null;
  registration_start_date: string | null;
  registration_end_date: string | null;
  registration_status: string | null;
  applications: Application[];
}

export default function ProductDetailScreen() {
  const { key } = useLocalSearchParams<{ key: string }>();
  const router = useRouter();
  const [product, setProduct] = useState<ProductCard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedApp, setExpandedApp] = useState<number | null>(0);

  useEffect(() => {
    fetchProduct();
  }, [key]);

  const fetchProduct = async () => {
    if (!key) return;
    
    setLoading(true);
    setError(null);
    
    try {
      const response = await axios.get(`${API_URL}/api/herbicides/${encodeURIComponent(key)}`);
      setProduct(response.data);
    } catch (err) {
      console.error('Failed to fetch product:', err);
      setError('Не удалось загрузить данные');
    } finally {
      setLoading(false);
    }
  };

  const isActive = (status: string | null) => {
    return status?.toLowerCase().trim() === 'действует';
  };

  const formatValue = (value: string | null | undefined): string => {
    if (!value || value === 'нет данных') return '—';
    return value;
  };

  if (loading) {
    return (
      <SafeAreaView style={styles.container} edges={['top']}>
        <AmbientBackground />
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={colors.primaryBright} />
          <Text style={styles.loadingText}>Загрузка...</Text>
        </View>
      </SafeAreaView>
    );
  }

  if (error || !product) {
    return (
      <SafeAreaView style={styles.container} edges={['top']}>
        <AmbientBackground />
        <View style={styles.header}>
          <TouchableOpacity style={styles.backButton} onPress={() => router.back()}>
            <Ionicons name="arrow-back" size={22} color={colors.text} />
          </TouchableOpacity>
        </View>
        <View style={styles.errorContainer}>
          <RetryErrorCard onRetry={fetchProduct} />
        </View>
      </SafeAreaView>
    );
  }

  const active = isActive(product.registration_status);

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <AmbientBackground />
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity style={styles.backButton} onPress={() => router.back()}>
          <Ionicons name="arrow-back" size={22} color={colors.text} />
        </TouchableOpacity>
        <BrandLogo compact />
        <View style={{ width: 40 }} />
      </View>

      <ScrollView style={styles.content} showsVerticalScrollIndicator={false}>
        {/* Product Info Card */}
        <View style={styles.productCard}>
          <View style={styles.productHeader}>
            <View style={styles.productTitleRow}>
              <Text style={styles.productName}>{product.product_name}</Text>
              {(product.formulation?.trim().length ?? 0) > 0 ? (
                <View style={styles.formulationBadge}>
                  <Text style={styles.formulationText}>{product.formulation}</Text>
                </View>
              ) : null}
            </View>
            <View style={[
              styles.statusBadge,
              active ? styles.statusActive : styles.statusInactive
            ]}>
              <View style={[
                styles.statusDot,
                active ? styles.statusDotActive : styles.statusDotInactive
              ]} />
              <Text style={[
                styles.statusText,
                active ? styles.statusTextActive : styles.statusTextInactive
              ]}>
                {product.registration_status || 'Нет данных'}
              </Text>
            </View>
          </View>

          {/* Details Grid */}
          <View style={styles.detailsGrid}>
            <View style={styles.detailItem}>
              <Text style={styles.detailLabel}>Действующее вещество</Text>
              <Text style={styles.detailValue}>{formatValue(product.active_substances_raw)}</Text>
            </View>

            <View style={styles.detailItem}>
              <Text style={styles.detailLabel}>Производитель</Text>
              <Text style={styles.detailValue}>{formatValue(product.display_manufacturer)}</Text>
            </View>

            <View style={styles.detailRow}>
              <View style={[styles.detailItem, { flex: 1 }]}>
                <Text style={styles.detailLabel}>Рег. номер</Text>
                <Text style={styles.detailValue}>{formatValue(product.registration_number)}</Text>
              </View>
              <View style={[styles.detailItem, { flex: 1 }]}>
                <Text style={styles.detailLabel}>Срок действия</Text>
                <Text style={styles.detailValue}>
                  {product.registration_start_date && product.registration_end_date
                    ? `${product.registration_start_date} — ${product.registration_end_date}`
                    : '—'}
                </Text>
              </View>
            </View>
          </View>
        </View>

        {/* Applications Section */}
        <View style={styles.applicationsSection}>
          <Text style={styles.sectionTitle}>
            <Ionicons name="layers-outline" size={18} color={colors.primaryBright} />
            {' '}Применения ({product.applications.length})
          </Text>

          {product.applications.map((app, index) => (
            <TouchableOpacity
              key={index}
              style={styles.applicationCard}
              onPress={() => setExpandedApp(expandedApp === index ? null : index)}
              activeOpacity={0.7}
            >
              <View style={styles.applicationHeader}>
                <View style={styles.applicationTitleRow}>
                  <View style={styles.applicationNumber}>
                    <Text style={styles.applicationNumberText}>{index + 1}</Text>
                  </View>
                  <View style={styles.applicationInfo}>
                    <Text style={styles.cropText} numberOfLines={expandedApp === index ? undefined : 1}>
                      {app.crop || 'Нет данных о культуре'}
                    </Text>
                    {app.target_object && (
                      <Text style={styles.targetText} numberOfLines={expandedApp === index ? undefined : 1}>
                        {app.target_object}
                      </Text>
                    )}
                  </View>
                </View>
                <Ionicons 
                  name={expandedApp === index ? "chevron-up" : "chevron-down"} 
                  size={20} 
                  color={colors.textMuted}
                />
              </View>

              {expandedApp === index && (
                <View style={styles.applicationDetails}>
                  <View style={styles.applicationDetailRow}>
                    <Text style={styles.applicationDetailLabel}>Норма расхода</Text>
                    <Text style={styles.applicationDetailValue}>{formatValue(app.rate_raw)} л/га</Text>
                  </View>

                  {app.application_method && app.application_method !== 'нет данных' && (
                    <View style={styles.applicationDetailRow}>
                      <Text style={styles.applicationDetailLabel}>Способ применения</Text>
                      <Text style={styles.applicationDetailValue}>{app.application_method}</Text>
                    </View>
                  )}

                  <View style={styles.applicationDetailRow}>
                    <Text style={styles.applicationDetailLabel}>Срок ожидания</Text>
                    <Text style={styles.applicationDetailValue}>{formatValue(app.waiting_period)}</Text>
                  </View>

                  <View style={styles.applicationDetailRow}>
                    <Text style={styles.applicationDetailLabel}>Выход на работы (ручн.)</Text>
                    <Text style={styles.applicationDetailValue}>{formatValue(app.reentry_period_manual)}</Text>
                  </View>

                  <View style={styles.applicationDetailRow}>
                    <Text style={styles.applicationDetailLabel}>Выход на работы (мех.)</Text>
                    <Text style={styles.applicationDetailValue}>{formatValue(app.reentry_period_mech)}</Text>
                  </View>

                  {app.restrictions && app.restrictions !== 'нет данных' && (
                    <View style={styles.applicationDetailRow}>
                      <Text style={styles.applicationDetailLabel}>Ограничения</Text>
                      <Text style={styles.applicationDetailValue}>{app.restrictions}</Text>
                    </View>
                  )}
                </View>
              )}
            </TouchableOpacity>
          ))}

          {product.applications.length === 0 && (
            <View style={styles.noApplications}>
              <Text style={styles.noApplicationsText}>Нет данных о применениях</Text>
            </View>
          )}
        </View>

        <View style={{ height: 40 }} />
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
    backgroundColor: 'rgba(7,10,28,0.88)',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  backButton: {
    width: 40,
    height: 40,
    justifyContent: 'center',
    alignItems: 'center',
    borderRadius: 13,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
  },
  headerTitle: {
    fontSize: 17,
    fontWeight: '600',
    color: colors.text,
    flex: 1,
    textAlign: 'center',
  },
  content: {
    flex: 1,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingText: {
    marginTop: 12,
    fontSize: 14,
    color: colors.textSecondary,
  },
  errorContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 20,
  },
  errorText: {
    fontSize: 16,
    color: colors.danger,
    marginTop: 16,
    textAlign: 'center',
  },
  retryButton: {
    marginTop: 20,
    paddingHorizontal: 24,
    paddingVertical: 12,
    backgroundColor: colors.primary,
    borderRadius: 8,
  },
  retryText: {
    color: '#FFFFFF',
    fontSize: 14,
    fontWeight: '600',
  },
  productCard: {
    backgroundColor: colors.surface,
    margin: 16,
    borderRadius: 16,
    padding: 20,
    shadowColor: colors.black,
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.24,
    shadowRadius: 8,
    elevation: 7,
    borderWidth: 1,
    borderColor: colors.border,
  },
  productHeader: {
    marginBottom: 20,
  },
  productTitleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    flexWrap: 'wrap',
    marginBottom: 12,
  },
  productName: {
    fontSize: 24,
    fontWeight: '700',
    color: colors.text,
    marginRight: 12,
  },
  formulationBadge: {
    backgroundColor: colors.surfaceSoft,
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 6,
  },
  formulationText: {
    fontSize: 14,
    color: colors.textSecondary,
    fontWeight: '500',
  },
  statusBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 8,
  },
  statusActive: {
    backgroundColor: colors.successSoft,
  },
  statusInactive: {
    backgroundColor: colors.dangerSoft,
  },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginRight: 8,
  },
  statusDotActive: {
    backgroundColor: colors.success,
  },
  statusDotInactive: {
    backgroundColor: colors.danger,
  },
  statusText: {
    fontSize: 13,
    fontWeight: '600',
  },
  statusTextActive: {
    color: colors.success,
  },
  statusTextInactive: {
    color: colors.danger,
  },
  detailsGrid: {
    gap: 16,
  },
  detailItem: {
    marginBottom: 4,
  },
  detailRow: {
    flexDirection: 'row',
    gap: 16,
  },
  detailLabel: {
    fontSize: 12,
    color: colors.textMuted,
    marginBottom: 4,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  detailValue: {
    fontSize: 15,
    color: colors.textSecondary,
    lineHeight: 22,
  },
  applicationsSection: {
    paddingHorizontal: 16,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: colors.text,
    marginBottom: 16,
  },
  applicationCard: {
    backgroundColor: colors.surface,
    borderRadius: 12,
    marginBottom: 12,
    overflow: 'hidden',
    shadowColor: colors.black,
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.2,
    shadowRadius: 4,
    elevation: 1,
    borderWidth: 1,
    borderColor: colors.border,
  },
  applicationHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: 16,
  },
  applicationTitleRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    flex: 1,
  },
  applicationNumber: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: colors.primarySoft,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  applicationNumberText: {
    fontSize: 13,
    fontWeight: '600',
    color: colors.primaryBright,
  },
  applicationInfo: {
    flex: 1,
  },
  cropText: {
    fontSize: 15,
    fontWeight: '600',
    color: colors.text,
  },
  targetText: {
    fontSize: 13,
    color: colors.textSecondary,
    marginTop: 2,
  },
  applicationDetails: {
    padding: 16,
    paddingTop: 0,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  applicationDetailRow: {
    flexDirection: 'column',
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  applicationDetailLabel: {
    fontSize: 12,
    color: colors.textMuted,
    marginBottom: 4,
  },
  applicationDetailValue: {
    fontSize: 14,
    color: colors.textSecondary,
    lineHeight: 20,
  },
  noApplications: {
    padding: 40,
    alignItems: 'center',
  },
  noApplicationsText: {
    fontSize: 14,
    color: colors.textMuted,
  },
});
