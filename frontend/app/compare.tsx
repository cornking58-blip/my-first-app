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
import { useRouter } from 'expo-router';
import axios from 'axios';
import { useHerbicideStore } from '../src/store/herbicideStore';

const API_URL = process.env.EXPO_PUBLIC_BACKEND_URL || '';

interface ProductInfo {
  product_key: string;
  product_name: string;
  formulation: string | null;
  active_substances_raw: string | null;
  manufacturer: string | null;
  registration_number: string | null;
  registration_status: string | null;
  registration_start_date: string | null;
  registration_end_date: string | null;
  crops: string[];
  targets: string[];
  rates: string[];
  applications_count: number;
}

interface CompareResult {
  left: ProductInfo;
  right: ProductInfo;
  comparison: {
    common_crops: string[];
    left_only_crops: string[];
    right_only_crops: string[];
  };
}

export default function CompareScreen() {
  const router = useRouter();
  const { selectedForCompare, clearSelection } = useHerbicideStore();
  const [compareData, setCompareData] = useState<CompareResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (selectedForCompare.length === 2) {
      fetchCompareData();
    }
  }, [selectedForCompare]);

  const fetchCompareData = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await axios.post(`${API_URL}/api/herbicides/compare`, {
        left_key: selectedForCompare[0],
        right_key: selectedForCompare[1],
      });
      setCompareData(response.data);
    } catch (err) {
      console.error('Compare failed:', err);
      setError('Не удалось сравнить препараты');
    } finally {
      setLoading(false);
    }
  };

  const handleBack = () => {
    clearSelection();
    router.back();
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
        <View style={styles.header}>
          <TouchableOpacity style={styles.backButton} onPress={handleBack}>
            <Ionicons name="arrow-back" size={24} color="#111827" />
          </TouchableOpacity>
          <Text style={styles.headerTitle}>Сравнение</Text>
          <View style={{ width: 40 }} />
        </View>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#3B82F6" />
          <Text style={styles.loadingText}>Загрузка...</Text>
        </View>
      </SafeAreaView>
    );
  }

  if (error || !compareData) {
    return (
      <SafeAreaView style={styles.container} edges={['top']}>
        <View style={styles.header}>
          <TouchableOpacity style={styles.backButton} onPress={handleBack}>
            <Ionicons name="arrow-back" size={24} color="#111827" />
          </TouchableOpacity>
          <Text style={styles.headerTitle}>Сравнение</Text>
          <View style={{ width: 40 }} />
        </View>
        <View style={styles.errorContainer}>
          <Ionicons name="warning-outline" size={64} color="#EF4444" />
          <Text style={styles.errorText}>{error || 'Ошибка загрузки'}</Text>
          <TouchableOpacity style={styles.retryButton} onPress={fetchCompareData}>
            <Text style={styles.retryText}>Повторить</Text>
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    );
  }

  const { left, right, comparison } = compareData;

  const CompareRow = ({ label, leftValue, rightValue, highlight }: { 
    label: string; 
    leftValue: string; 
    rightValue: string;
    highlight?: 'left' | 'right' | 'both' | 'none';
  }) => (
    <View style={styles.compareRow}>
      <View style={styles.compareLabel}>
        <Text style={styles.compareLabelText}>{label}</Text>
      </View>
      <View style={[
        styles.compareValue, 
        styles.compareValueLeft,
        highlight === 'left' || highlight === 'both' ? styles.compareValueHighlight : null
      ]}>
        <Text style={styles.compareValueText}>{leftValue}</Text>
      </View>
      <View style={[
        styles.compareValue, 
        styles.compareValueRight,
        highlight === 'right' || highlight === 'both' ? styles.compareValueHighlight : null
      ]}>
        <Text style={styles.compareValueText}>{rightValue}</Text>
      </View>
    </View>
  );

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <TouchableOpacity style={styles.backButton} onPress={handleBack}>
          <Ionicons name="arrow-back" size={24} color="#111827" />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Сравнение препаратов</Text>
        <View style={{ width: 40 }} />
      </View>

      <ScrollView style={styles.content} showsVerticalScrollIndicator={false}>
        {/* Product Headers */}
        <View style={styles.productHeaders}>
          <View style={styles.productHeaderLeft}>
            <Text style={styles.productHeaderName} numberOfLines={2}>{left.product_name}</Text>
            {left.formulation && (
              <View style={styles.formulationBadge}>
                <Text style={styles.formulationText}>{left.formulation}</Text>
              </View>
            )}
            <View style={[
              styles.statusBadgeMini,
              isActive(left.registration_status) ? styles.statusActiveMini : styles.statusInactiveMini
            ]}>
              <Text style={[
                styles.statusTextMini,
                isActive(left.registration_status) ? styles.statusTextActiveMini : styles.statusTextInactiveMini
              ]}>
                {isActive(left.registration_status) ? 'Действует' : 'Не действует'}
              </Text>
            </View>
          </View>
          
          <View style={styles.vsContainer}>
            <Text style={styles.vsText}>VS</Text>
          </View>
          
          <View style={styles.productHeaderRight}>
            <Text style={styles.productHeaderName} numberOfLines={2}>{right.product_name}</Text>
            {right.formulation && (
              <View style={styles.formulationBadge}>
                <Text style={styles.formulationText}>{right.formulation}</Text>
              </View>
            )}
            <View style={[
              styles.statusBadgeMini,
              isActive(right.registration_status) ? styles.statusActiveMini : styles.statusInactiveMini
            ]}>
              <Text style={[
                styles.statusTextMini,
                isActive(right.registration_status) ? styles.statusTextActiveMini : styles.statusTextInactiveMini
              ]}>
                {isActive(right.registration_status) ? 'Действует' : 'Не действует'}
              </Text>
            </View>
          </View>
        </View>

        {/* Comparison Table */}
        <View style={styles.comparisonTable}>
          <Text style={styles.sectionTitle}>Основные характеристики</Text>
          
          <CompareRow 
            label="Д/В" 
            leftValue={formatValue(left.active_substances_raw)}
            rightValue={formatValue(right.active_substances_raw)}
          />
          
          <CompareRow 
            label="Производитель" 
            leftValue={formatValue(left.manufacturer)}
            rightValue={formatValue(right.manufacturer)}
          />
          
          <CompareRow 
            label="Рег. номер" 
            leftValue={formatValue(left.registration_number)}
            rightValue={formatValue(right.registration_number)}
          />
          
          <CompareRow 
            label="Применений" 
            leftValue={String(left.applications_count)}
            rightValue={String(right.applications_count)}
            highlight={left.applications_count > right.applications_count ? 'left' : 
                      right.applications_count > left.applications_count ? 'right' : 'none'}
          />
          
          <CompareRow 
            label="Нормы расхода" 
            leftValue={left.rates.length > 0 ? left.rates.join('; ') : '—'}
            rightValue={right.rates.length > 0 ? right.rates.join('; ') : '—'}
          />
        </View>

        {/* Crops Comparison */}
        <View style={styles.cropsSection}>
          <Text style={styles.sectionTitle}>Культуры</Text>
          
          {comparison.common_crops.length > 0 && (
            <View style={styles.cropsBlock}>
              <View style={styles.cropsBlockHeader}>
                <Ionicons name="checkmark-circle" size={18} color="#10B981" />
                <Text style={styles.cropsBlockTitle}>Общие культуры ({comparison.common_crops.length})</Text>
              </View>
              <View style={styles.cropsList}>
                {comparison.common_crops.map((crop, idx) => (
                  <View key={idx} style={[styles.cropTag, styles.cropTagCommon]}>
                    <Text style={styles.cropTagText}>{crop}</Text>
                  </View>
                ))}
              </View>
            </View>
          )}
          
          {comparison.left_only_crops.length > 0 && (
            <View style={styles.cropsBlock}>
              <View style={styles.cropsBlockHeader}>
                <View style={[styles.cropDot, { backgroundColor: '#3B82F6' }]} />
                <Text style={styles.cropsBlockTitle}>Только {left.product_name} ({comparison.left_only_crops.length})</Text>
              </View>
              <View style={styles.cropsList}>
                {comparison.left_only_crops.map((crop, idx) => (
                  <View key={idx} style={[styles.cropTag, styles.cropTagLeft]}>
                    <Text style={styles.cropTagText}>{crop}</Text>
                  </View>
                ))}
              </View>
            </View>
          )}
          
          {comparison.right_only_crops.length > 0 && (
            <View style={styles.cropsBlock}>
              <View style={styles.cropsBlockHeader}>
                <View style={[styles.cropDot, { backgroundColor: '#8B5CF6' }]} />
                <Text style={styles.cropsBlockTitle}>Только {right.product_name} ({comparison.right_only_crops.length})</Text>
              </View>
              <View style={styles.cropsList}>
                {comparison.right_only_crops.map((crop, idx) => (
                  <View key={idx} style={[styles.cropTag, styles.cropTagRight]}>
                    <Text style={styles.cropTagText}>{crop}</Text>
                  </View>
                ))}
              </View>
            </View>
          )}
        </View>

        <View style={{ height: 40 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F9FAFB',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: '#FFFFFF',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#E5E7EB',
  },
  backButton: {
    width: 40,
    height: 40,
    justifyContent: 'center',
    alignItems: 'center',
  },
  headerTitle: {
    fontSize: 17,
    fontWeight: '600',
    color: '#111827',
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
    color: '#6B7280',
  },
  errorContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 20,
  },
  errorText: {
    fontSize: 16,
    color: '#EF4444',
    marginTop: 16,
    textAlign: 'center',
  },
  retryButton: {
    marginTop: 20,
    paddingHorizontal: 24,
    paddingVertical: 12,
    backgroundColor: '#3B82F6',
    borderRadius: 8,
  },
  retryText: {
    color: '#FFFFFF',
    fontSize: 14,
    fontWeight: '600',
  },
  productHeaders: {
    flexDirection: 'row',
    backgroundColor: '#FFFFFF',
    padding: 16,
    margin: 16,
    borderRadius: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.05,
    shadowRadius: 8,
    elevation: 3,
  },
  productHeaderLeft: {
    flex: 1,
    alignItems: 'center',
    paddingRight: 8,
  },
  productHeaderRight: {
    flex: 1,
    alignItems: 'center',
    paddingLeft: 8,
  },
  productHeaderName: {
    fontSize: 16,
    fontWeight: '700',
    color: '#111827',
    textAlign: 'center',
    marginBottom: 8,
  },
  vsContainer: {
    width: 40,
    justifyContent: 'center',
    alignItems: 'center',
  },
  vsText: {
    fontSize: 14,
    fontWeight: '700',
    color: '#9CA3AF',
  },
  formulationBadge: {
    backgroundColor: '#F3F4F6',
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 4,
    marginBottom: 8,
  },
  formulationText: {
    fontSize: 12,
    color: '#6B7280',
    fontWeight: '500',
  },
  statusBadgeMini: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 4,
  },
  statusActiveMini: {
    backgroundColor: '#D1FAE5',
  },
  statusInactiveMini: {
    backgroundColor: '#FEE2E2',
  },
  statusTextMini: {
    fontSize: 11,
    fontWeight: '600',
  },
  statusTextActiveMini: {
    color: '#059669',
  },
  statusTextInactiveMini: {
    color: '#DC2626',
  },
  comparisonTable: {
    backgroundColor: '#FFFFFF',
    marginHorizontal: 16,
    borderRadius: 16,
    padding: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.03,
    shadowRadius: 4,
    elevation: 1,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#374151',
    marginBottom: 16,
  },
  compareRow: {
    flexDirection: 'row',
    borderBottomWidth: 1,
    borderBottomColor: '#F3F4F6',
    paddingVertical: 12,
  },
  compareLabel: {
    width: 100,
    justifyContent: 'center',
  },
  compareLabelText: {
    fontSize: 12,
    color: '#9CA3AF',
    fontWeight: '500',
  },
  compareValue: {
    flex: 1,
    padding: 8,
    borderRadius: 6,
  },
  compareValueLeft: {
    marginRight: 4,
    backgroundColor: '#EFF6FF',
  },
  compareValueRight: {
    marginLeft: 4,
    backgroundColor: '#F5F3FF',
  },
  compareValueHighlight: {
    backgroundColor: '#D1FAE5',
  },
  compareValueText: {
    fontSize: 13,
    color: '#374151',
    lineHeight: 18,
  },
  cropsSection: {
    backgroundColor: '#FFFFFF',
    margin: 16,
    borderRadius: 16,
    padding: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.03,
    shadowRadius: 4,
    elevation: 1,
  },
  cropsBlock: {
    marginBottom: 16,
  },
  cropsBlockHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 10,
  },
  cropsBlockTitle: {
    fontSize: 14,
    fontWeight: '500',
    color: '#374151',
    marginLeft: 8,
  },
  cropDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
  },
  cropsList: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  cropTag: {
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 6,
  },
  cropTagCommon: {
    backgroundColor: '#D1FAE5',
  },
  cropTagLeft: {
    backgroundColor: '#DBEAFE',
  },
  cropTagRight: {
    backgroundColor: '#EDE9FE',
  },
  cropTagText: {
    fontSize: 12,
    color: '#374151',
  },
});
