import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
  TextInput,
  KeyboardAvoidingView,
  Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import axios from 'axios';
import { useHerbicideStore } from '../src/store/herbicideStore';

const API_URL = process.env.EXPO_PUBLIC_BACKEND_URL || '';

// Logo Component
const Logo = () => (
  <View style={styles.logoContainer}>
    <Text style={styles.logoText}>
      <Text style={styles.logoB}>b</Text>
      <Text style={styles.logoAI}>AI</Text>
      <Text style={styles.logoKov}>kov</Text>
    </Text>
  </View>
);

interface Substance {
  name: string;
  concentration: number;
  unit: string;
  is_antidote: boolean;
  resistance_system?: string | null;
  resistance_group?: string | null;
  resistance_group_name?: string;
  category?: string;
  per_ha?: number;
}

interface IdenticalSubstance {
  name: string;
  left_concentration: number;
  left_unit: string;
  right_concentration: number;
  right_unit: string;
  left_per_ha: number | null;
  right_per_ha: number | null;
  winner: 'left' | 'right' | 'equal';
}

interface SimilarCategory {
  category: string;
  left_substances: { name: string; concentration: number; unit: string }[];
  right_substances: { name: string; concentration: number; unit: string }[];
}

interface ProductInfo {
  product_key: string;
  product_name: string;
  formulation: string | null;
  active_substances_raw: string | null;
  registration_status: string | null;
  max_rate: number | null;
  rate_used?: number | null;
  rate_source?: 'manual' | 'max_registered';
  substances: Substance[];
  antidotes: Substance[];
  total_concentration: number;
  total_per_ha: number | null;
  substance_count: number;
}

interface GroupAnalysis {
  identical_active_set?: boolean;
  reference_groups?: {
    substance: string;
    system: string | null;
    group: string | null;
    group_name: string;
  }[];
  same_group_matches: {
    system: string;
    group: string;
    group_name: string;
    left_substances: string[];
    right_substances: string[];
    warning: string;
  }[];
  different_group_matches: {
    left_substance: string;
    left_group: string;
    right_substance: string;
    right_group: string;
    message: string;
  }[];
  unknown_group_substances: {
    side: 'left' | 'right';
    substance: string;
  }[];
  plain_explanation: string;
}

interface PriceAnalysis {
  left_price_per_unit: number | null;
  right_price_per_unit: number | null;
  left_cost_per_ha: number | null;
  right_cost_per_ha: number | null;
  left_cost_per_gram_ai: number | null;
  right_cost_per_gram_ai: number | null;
  substances_cost: {
    side: 'left' | 'right';
    name: string;
    substance_name?: string;
    concentration: number;
    unit?: string;
    rate_used?: number;
    grams_per_ha?: number;
    estimated_cost_share_per_ha?: number;
    estimated_cost_per_gram?: number | null;
    cost_contribution_pct: number;
  }[];
}

interface CropRegistration {
  crop: string;
  left: { has_registration: boolean; message: string };
  right: { has_registration: boolean; message: string };
}

interface CompareResult {
  left: ProductInfo;
  right: ProductInfo;
  analysis: {
    identical_substances: IdenticalSubstance[];
    similar_by_category: SimilarCategory[];
    left_unique_substances: (Substance & { category: string; per_ha: number | null })[];
    right_unique_substances: (Substance & { category: string; per_ha: number | null })[];
  };
  group_analysis?: GroupAnalysis;
  crop_registration?: CropRegistration | null;
  price_analysis: PriceAnalysis | null;
}

export default function SeedTreatmentCompareScreen() {
  const router = useRouter();
  const { selectedSeedTreatmentsForCompare, clearSeedTreatmentSelection } = useHerbicideStore();
  const [compareData, setCompareData] = useState<CompareResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [leftPrice, setLeftPrice] = useState('');
  const [rightPrice, setRightPrice] = useState('');
  const [leftRate, setLeftRate] = useState('');
  const [rightRate, setRightRate] = useState('');
  const [crop, setCrop] = useState('');
  const [priceLoading, setPriceLoading] = useState(false);

  useEffect(() => {
    if (selectedSeedTreatmentsForCompare.length === 2) {
      fetchCompareData();
    }
  }, [selectedSeedTreatmentsForCompare]);

  const parseOptionalNumber = (value: string) => {
    const normalized = value.trim().replace(',', '.');
    if (!normalized) return undefined;
    const parsed = parseFloat(normalized);
    return Number.isFinite(parsed) ? parsed : undefined;
  };

  const fetchCompareData = async (options?: { inlineLoading?: boolean }) => {
    if (options?.inlineLoading) {
      setPriceLoading(true);
    } else {
      setLoading(true);
    }
    setError(null);
    
    try {
      const body: any = {
        left_key: selectedSeedTreatmentsForCompare[0],
        right_key: selectedSeedTreatmentsForCompare[1],
      };

      const lPrice = parseOptionalNumber(leftPrice);
      const rPrice = parseOptionalNumber(rightPrice);
      const lRate = parseOptionalNumber(leftRate);
      const rRate = parseOptionalNumber(rightRate);
      const cropValue = crop.trim();
      
      if (lPrice !== undefined) body.left_price = lPrice;
      if (rPrice !== undefined) body.right_price = rPrice;
      if (lRate !== undefined) body.left_rate = lRate;
      if (rRate !== undefined) body.right_rate = rRate;
      if (cropValue) body.crop = cropValue;
      
      const response = await axios.post(`${API_URL}/api/seed-treatments/compare-advanced`, body);
      setCompareData(response.data);
    } catch (err) {
      console.error('Compare failed:', err);
      setError('Не удалось сравнить препараты');
    } finally {
      setLoading(false);
      setPriceLoading(false);
    }
  };

  const handlePriceCalculation = () => {
    fetchCompareData({ inlineLoading: true });
  };

  const handleBack = () => {
    clearSeedTreatmentSelection();
    router.back();
  };

  const isActive = (status: string | null) => {
    return status?.toLowerCase().trim() === 'действует';
  };

  if (loading) {
    return (
      <SafeAreaView style={styles.container} edges={['top']}>
        <View style={styles.header}>
          <TouchableOpacity style={styles.backButton} onPress={handleBack}>
            <Ionicons name="arrow-back" size={24} color="#111827" />
          </TouchableOpacity>
          <Logo />
          <View style={{ width: 40 }} />
        </View>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#3B82F6" />
          <Text style={styles.loadingText}>Анализ действующих веществ...</Text>
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
          <Logo />
          <View style={{ width: 40 }} />
        </View>
        <View style={styles.errorContainer}>
          <Ionicons name="warning-outline" size={64} color="#EF4444" />
          <Text style={styles.errorText}>{error || 'Ошибка загрузки'}</Text>
          <TouchableOpacity style={styles.retryButton} onPress={() => fetchCompareData()}>
            <Text style={styles.retryText}>Повторить</Text>
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    );
  }

  const { left, right, analysis, group_analysis, crop_registration, price_analysis } = compareData;

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={{ flex: 1 }}
      >
        <View style={styles.header}>
          <TouchableOpacity style={styles.backButton} onPress={handleBack}>
            <Ionicons name="arrow-back" size={24} color="#111827" />
          </TouchableOpacity>
          <Logo />
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

          {/* Summary Stats */}
          <View style={styles.summarySection}>
            <Text style={styles.sectionTitle}>Общая информация</Text>
            <View style={styles.summaryGrid}>
              <View style={styles.summaryRow}>
                <Text style={styles.summaryLabel}>ДВ (без антидотов)</Text>
                <View style={styles.summaryValues}>
                  <Text style={[styles.summaryValue, styles.leftValue]}>{left.substance_count}</Text>
                  <Text style={[styles.summaryValue, styles.rightValue]}>{right.substance_count}</Text>
                </View>
              </View>
              <View style={styles.summaryRow}>
                <Text style={styles.summaryLabel}>Сумма ДВ, г/л</Text>
                <View style={styles.summaryValues}>
                  <Text style={[styles.summaryValue, styles.leftValue]}>{left.total_concentration}</Text>
                  <Text style={[styles.summaryValue, styles.rightValue]}>{right.total_concentration}</Text>
                </View>
              </View>
              <View style={styles.summaryRow}>
                <Text style={styles.summaryLabel}>Макс. норма, л/га</Text>
                <View style={styles.summaryValues}>
                  <Text style={[styles.summaryValue, styles.leftValue]}>{left.max_rate ?? '—'}</Text>
                  <Text style={[styles.summaryValue, styles.rightValue]}>{right.max_rate ?? '—'}</Text>
                </View>
              </View>
              <View style={styles.summaryRow}>
                <Text style={styles.summaryLabel}>ДВ на 1 га, г</Text>
                <View style={styles.summaryValues}>
                  <Text style={[styles.summaryValue, styles.leftValue, left.total_per_ha && right.total_per_ha && left.total_per_ha > right.total_per_ha ? styles.winnerValue : null]}>
                    {left.total_per_ha ?? '—'}
                  </Text>
                  <Text style={[styles.summaryValue, styles.rightValue, left.total_per_ha && right.total_per_ha && right.total_per_ha > left.total_per_ha ? styles.winnerValue : null]}>
                    {right.total_per_ha ?? '—'}
                  </Text>
                </View>
              </View>
            </View>
          </View>

          {/* Crop Registration */}
          {crop_registration && (
            <View style={styles.section}>
              <View style={styles.sectionHeader}>
                <Ionicons name="leaf" size={20} color="#16A34A" />
                <Text style={styles.sectionTitle}>Регистрация на культуру: {crop_registration.crop}</Text>
              </View>
              <View style={styles.cropRegistrationRow}>
                <View style={[styles.cropRegistrationCard, crop_registration.left.has_registration ? styles.cropRegistered : styles.cropNotRegistered]}>
                  <Text style={styles.cropProductName}>{left.product_name}</Text>
                  <Text style={styles.cropGeneralStatus}>Общий статус: {isActive(left.registration_status) ? 'Действует' : 'Не действует'}</Text>
                  <Text style={styles.cropRegistrationText}>{crop_registration.left.message}</Text>
                </View>
                <View style={[styles.cropRegistrationCard, crop_registration.right.has_registration ? styles.cropRegistered : styles.cropNotRegistered]}>
                  <Text style={styles.cropProductName}>{right.product_name}</Text>
                  <Text style={styles.cropGeneralStatus}>Общий статус: {isActive(right.registration_status) ? 'Действует' : 'Не действует'}</Text>
                  <Text style={styles.cropRegistrationText}>{crop_registration.right.message}</Text>
                </View>
              </View>
            </View>
          )}

          {/* Identical Substances */}
          {analysis.identical_substances.length > 0 && (
            <View style={styles.section}>
              <View style={styles.sectionHeader}>
                <Ionicons name="checkmark-circle" size={20} color="#10B981" />
                <Text style={styles.sectionTitle}>Одинаковые ДВ ({analysis.identical_substances.length})</Text>
              </View>
              {analysis.identical_substances.map((sub, idx) => (
                <View key={idx} style={styles.substanceCard}>
                  <Text style={styles.substanceName}>{sub.name}</Text>
                  <View style={styles.substanceComparison}>
                    <View style={[styles.substanceValue, styles.leftBg, sub.winner === 'left' && styles.winnerBg]}>
                      <Text style={styles.substanceConc}>{sub.left_concentration} {sub.left_unit}</Text>
                      {sub.left_per_ha && (
                        <Text style={styles.substancePerHa}>{sub.left_per_ha} г/га</Text>
                      )}
                    </View>
                    <View style={[styles.substanceValue, styles.rightBg, sub.winner === 'right' && styles.winnerBg]}>
                      <Text style={styles.substanceConc}>{sub.right_concentration} {sub.right_unit}</Text>
                      {sub.right_per_ha && (
                        <Text style={styles.substancePerHa}>{sub.right_per_ha} г/га</Text>
                      )}
                    </View>
                  </View>
                </View>
              ))}
            </View>
          )}

          {/* Similar by Category */}
          {analysis.similar_by_category.length > 0 && (
            <View style={styles.section}>
              <View style={styles.sectionHeader}>
                <Ionicons name="git-compare" size={20} color="#F59E0B" />
                <Text style={styles.sectionTitle}>Сходные по механизму</Text>
              </View>
              {analysis.similar_by_category.map((cat, idx) => (
                <View key={idx} style={styles.categoryCard}>
                  <View style={styles.categoryHeader}>
                    <Ionicons name="flask" size={16} color="#6B7280" />
                    <Text style={styles.categoryName}>{cat.category}</Text>
                  </View>
                  <View style={styles.categoryComparison}>
                    <View style={[styles.categoryColumn, styles.leftBg]}>
                      {cat.left_substances.map((s, i) => (
                        <Text key={i} style={styles.categorySubstance}>
                          {s.name} ({s.concentration} {s.unit})
                        </Text>
                      ))}
                    </View>
                    <View style={[styles.categoryColumn, styles.rightBg]}>
                      {cat.right_substances.map((s, i) => (
                        <Text key={i} style={styles.categorySubstance}>
                          {s.name} ({s.concentration} {s.unit})
                        </Text>
                      ))}
                    </View>
                  </View>
                </View>
              ))}
            </View>
          )}

          {/* Unique Substances */}
          {(analysis.left_unique_substances.length > 0 || analysis.right_unique_substances.length > 0) && (
            <View style={styles.section}>
              <View style={styles.sectionHeader}>
                <Ionicons name="add-circle" size={20} color="#6366F1" />
                <Text style={styles.sectionTitle}>Уникальные ДВ</Text>
              </View>
              
              {analysis.left_unique_substances.length > 0 && (
                <View style={styles.uniqueBlock}>
                  <Text style={styles.uniqueBlockTitle}>Только в {left.product_name}:</Text>
                  {analysis.left_unique_substances.map((sub, idx) => (
                    <View key={idx} style={[styles.uniqueSubstance, styles.leftBg]}>
                      <Text style={styles.uniqueSubstanceName}>{sub.name}</Text>
                      <Text style={styles.uniqueSubstanceInfo}>
                        {sub.concentration} {sub.unit} • {sub.category}
                        {sub.per_ha && ` • ${sub.per_ha} г/га`}
                      </Text>
                    </View>
                  ))}
                </View>
              )}
              
              {analysis.right_unique_substances.length > 0 && (
                <View style={styles.uniqueBlock}>
                  <Text style={styles.uniqueBlockTitle}>Только в {right.product_name}:</Text>
                  {analysis.right_unique_substances.map((sub, idx) => (
                    <View key={idx} style={[styles.uniqueSubstance, styles.rightBg]}>
                      <Text style={styles.uniqueSubstanceName}>{sub.name}</Text>
                      <Text style={styles.uniqueSubstanceInfo}>
                        {sub.concentration} {sub.unit} • {sub.category}
                        {sub.per_ha && ` • ${sub.per_ha} г/га`}
                      </Text>
                    </View>
                  ))}
                </View>
              )}
            </View>
          )}

          {/* Resistance Groups */}
          {group_analysis && (
            group_analysis.same_group_matches.length > 0 ||
            group_analysis.different_group_matches.length > 0 ||
            group_analysis.unknown_group_substances.length > 0 ||
            (group_analysis.reference_groups?.length ?? 0) > 0
          ) && (
            <View style={styles.section}>
              <View style={styles.sectionHeader}>
                <Ionicons name="shield-checkmark" size={20} color="#0F766E" />
                <Text style={styles.sectionTitle}>Группы устойчивости HRAC / FRAC / IRAC</Text>
              </View>

              {group_analysis.reference_groups && group_analysis.reference_groups.length > 0 && (
                <View style={[styles.groupCard, styles.groupUnknownCard]}>
                  <Text style={styles.groupTitle}>Действующие вещества совпадают</Text>
                  {group_analysis.reference_groups.map((item, idx) => (
                    <Text key={`reference-${idx}`} style={styles.groupText}>
                      {item.substance} — {item.system && item.group ? `${item.system} ${item.group}` : 'группа не определена'} / {item.group_name}
                    </Text>
                  ))}
                </View>
              )}

              {group_analysis.same_group_matches.map((match, idx) => (
                <View key={`same-${idx}`} style={[styles.groupCard, styles.groupWarningCard]}>
                  <Text style={styles.groupTitle}>{match.system} {match.group} • {match.group_name}</Text>
                  <Text style={styles.groupText}>
                    {match.left_substances.join(', ')} ↔ {match.right_substances.join(', ')}
                  </Text>
                  <Text style={styles.groupWarningText}>{match.warning}</Text>
                </View>
              ))}

              {group_analysis.different_group_matches.map((match, idx) => (
                <View key={`different-${idx}`} style={[styles.groupCard, styles.groupSuccessCard]}>
                  <Text style={styles.groupTitle}>
                    {match.left_substance} ({match.left_group}) ↔ {match.right_substance} ({match.right_group})
                  </Text>
                  <Text style={styles.groupText}>{match.message}</Text>
                </View>
              ))}

              {group_analysis.unknown_group_substances.length > 0 && (
                <View style={[styles.groupCard, styles.groupUnknownCard]}>
                  <Text style={styles.groupTitle}>Группа не определена</Text>
                  {group_analysis.unknown_group_substances.map((item, idx) => (
                    <Text key={`unknown-${idx}`} style={styles.groupText}>
                      {item.side === 'left' ? left.product_name : right.product_name}: {item.substance}
                    </Text>
                  ))}
                </View>
              )}

              <Text style={styles.groupExplanation}>{group_analysis.plain_explanation}</Text>
            </View>
          )}

          {/* Price Input Section */}
          <View style={styles.priceSection}>
            <View style={styles.sectionHeader}>
              <Ionicons name="calculator" size={20} color="#059669" />
              <Text style={styles.sectionTitle}>Расчёт стоимости</Text>
            </View>
            
            <Text style={styles.priceHint}>Введите цену за 1 л/кг и, если нужно, ручную норму. Если норма пустая, используется максимальная зарегистрированная.</Text>
            
            <View style={styles.priceInputRow}>
              <View style={styles.priceInputContainer}>
                <Text style={styles.priceInputLabel}>{left.product_name}</Text>
                <TextInput
                  style={styles.priceInput}
                  placeholder="Цена, ₽"
                  placeholderTextColor="#9CA3AF"
                  keyboardType="decimal-pad"
                  value={leftPrice}
                  onChangeText={setLeftPrice}
                />
              </View>
              <View style={styles.priceInputContainer}>
                <Text style={styles.priceInputLabel}>{right.product_name}</Text>
                <TextInput
                  style={styles.priceInput}
                  placeholder="Цена, ₽"
                  placeholderTextColor="#9CA3AF"
                  keyboardType="decimal-pad"
                  value={rightPrice}
                  onChangeText={setRightPrice}
                />
              </View>
            </View>

            <View style={styles.priceInputRow}>
              <View style={styles.priceInputContainer}>
                <Text style={styles.priceInputLabel}>Норма препарата А</Text>
                <TextInput
                  style={styles.priceInput}
                  placeholder={`Макс.: ${left.max_rate ?? '—'}`}
                  placeholderTextColor="#9CA3AF"
                  keyboardType="decimal-pad"
                  value={leftRate}
                  onChangeText={setLeftRate}
                />
                <Text style={styles.rateSourceText}>Используется: {left.rate_source === 'manual' ? 'ручная' : 'макс. зарегистрированная'} ({left.rate_used ?? '—'})</Text>
              </View>
              <View style={styles.priceInputContainer}>
                <Text style={styles.priceInputLabel}>Норма препарата Б</Text>
                <TextInput
                  style={styles.priceInput}
                  placeholder={`Макс.: ${right.max_rate ?? '—'}`}
                  placeholderTextColor="#9CA3AF"
                  keyboardType="decimal-pad"
                  value={rightRate}
                  onChangeText={setRightRate}
                />
                <Text style={styles.rateSourceText}>Используется: {right.rate_source === 'manual' ? 'ручная' : 'макс. зарегистрированная'} ({right.rate_used ?? '—'})</Text>
              </View>
            </View>

            <TextInput
              style={[styles.priceInput, styles.cropInput]}
              placeholder="Культура для проверки регистрации"
              placeholderTextColor="#9CA3AF"
              value={crop}
              onChangeText={setCrop}
            />
            
            <TouchableOpacity 
              style={styles.calculateButton}
              onPress={handlePriceCalculation}
              disabled={priceLoading}
            >
              {priceLoading ? (
                <ActivityIndicator size="small" color="#FFFFFF" />
              ) : (
                <>
                  <Ionicons name="calculator" size={18} color="#FFFFFF" />
                  <Text style={styles.calculateButtonText}>Рассчитать</Text>
                </>
              )}
            </TouchableOpacity>

            {/* Price Analysis Results */}
            {price_analysis && (price_analysis.left_price_per_unit || price_analysis.right_price_per_unit) && (
              <View style={styles.priceResults}>
                <View style={styles.priceResultRow}>
                  <Text style={styles.priceResultLabel}>Стоимость 1 га, ₽</Text>
                  <View style={styles.priceResultValues}>
                    <Text style={[
                      styles.priceResultValue, 
                      styles.leftValue,
                      price_analysis.left_cost_per_ha && price_analysis.right_cost_per_ha && 
                      price_analysis.left_cost_per_ha < price_analysis.right_cost_per_ha ? styles.winnerValue : null
                    ]}>
                      {price_analysis.left_cost_per_ha?.toFixed(0) ?? '—'}
                    </Text>
                    <Text style={[
                      styles.priceResultValue, 
                      styles.rightValue,
                      price_analysis.left_cost_per_ha && price_analysis.right_cost_per_ha && 
                      price_analysis.right_cost_per_ha < price_analysis.left_cost_per_ha ? styles.winnerValue : null
                    ]}>
                      {price_analysis.right_cost_per_ha?.toFixed(0) ?? '—'}
                    </Text>
                  </View>
                </View>
                
                {price_analysis.substances_cost.length > 0 && (
                  <View style={styles.substanceCostSection}>
                    <Text style={styles.substanceCostTitle}>Стоимость действующих веществ</Text>
                    {price_analysis.substances_cost.map((item, idx) => (
                      <View key={`cost-${idx}`} style={[styles.substanceCostCard, item.side === 'left' ? styles.leftBg : styles.rightBg]}>
                        <Text style={styles.substanceCostName}>{item.substance_name || item.name}</Text>
                        <Text style={styles.substanceCostText}>ДВ на 1 га: {item.grams_per_ha ?? '—'} г</Text>
                        <Text style={styles.substanceCostText}>Оценка стоимости на 1 га: {item.estimated_cost_share_per_ha?.toFixed(2) ?? '—'} ₽</Text>
                        <Text style={styles.substanceCostText}>Оценка за 1 г: {item.estimated_cost_per_gram?.toFixed(4) ?? '—'} ₽</Text>
                      </View>
                    ))}
                  </View>
                )}
              </View>
            )}
          </View>

          <View style={{ height: 40 }} />
        </ScrollView>
      </KeyboardAvoidingView>
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
  logoContainer: {
    alignItems: 'center',
  },
  logoText: {
    fontSize: 24,
    fontWeight: '800',
    letterSpacing: -0.5,
  },
  logoB: {
    color: '#374151',
  },
  logoAI: {
    color: '#3B82F6',
    fontWeight: '900',
  },
  logoKov: {
    color: '#374151',
  },
  productHeaders: {
    flexDirection: 'row',
    backgroundColor: '#FFFFFF',
    padding: 16,
    margin: 16,
    borderRadius: 16,
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
  summarySection: {
    backgroundColor: '#FFFFFF',
    marginHorizontal: 16,
    borderRadius: 16,
    padding: 16,
    marginBottom: 16,
  },
  summaryGrid: {
    gap: 12,
  },
  summaryRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  summaryLabel: {
    fontSize: 13,
    color: '#6B7280',
    flex: 1,
  },
  summaryValues: {
    flexDirection: 'row',
    gap: 8,
  },
  summaryValue: {
    width: 70,
    textAlign: 'center',
    fontSize: 14,
    fontWeight: '600',
    paddingVertical: 4,
    paddingHorizontal: 8,
    borderRadius: 6,
    overflow: 'hidden',
  },
  leftValue: {
    backgroundColor: '#DBEAFE',
    color: '#1E40AF',
  },
  rightValue: {
    backgroundColor: '#EDE9FE',
    color: '#5B21B6',
  },
  winnerValue: {
    backgroundColor: '#D1FAE5',
    color: '#059669',
  },
  section: {
    backgroundColor: '#FFFFFF',
    marginHorizontal: 16,
    borderRadius: 16,
    padding: 16,
    marginBottom: 16,
  },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 16,
    gap: 8,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#374151',
  },
  substanceCard: {
    marginBottom: 12,
    padding: 12,
    backgroundColor: '#F9FAFB',
    borderRadius: 12,
  },
  substanceName: {
    fontSize: 14,
    fontWeight: '600',
    color: '#111827',
    marginBottom: 8,
    textAlign: 'center',
  },
  substanceComparison: {
    flexDirection: 'row',
    gap: 8,
  },
  substanceValue: {
    flex: 1,
    padding: 10,
    borderRadius: 8,
    alignItems: 'center',
  },
  leftBg: {
    backgroundColor: '#DBEAFE',
  },
  rightBg: {
    backgroundColor: '#EDE9FE',
  },
  winnerBg: {
    backgroundColor: '#D1FAE5',
  },
  substanceConc: {
    fontSize: 15,
    fontWeight: '700',
    color: '#111827',
  },
  substancePerHa: {
    fontSize: 12,
    color: '#6B7280',
    marginTop: 4,
  },
  categoryCard: {
    marginBottom: 12,
    backgroundColor: '#F9FAFB',
    borderRadius: 12,
    overflow: 'hidden',
  },
  categoryHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 12,
    backgroundColor: '#FEF3C7',
    gap: 8,
  },
  categoryName: {
    fontSize: 13,
    fontWeight: '600',
    color: '#92400E',
  },
  categoryComparison: {
    flexDirection: 'row',
  },
  categoryColumn: {
    flex: 1,
    padding: 10,
  },
  categorySubstance: {
    fontSize: 13,
    color: '#374151',
    marginBottom: 4,
  },
  uniqueBlock: {
    marginBottom: 12,
  },
  uniqueBlockTitle: {
    fontSize: 13,
    fontWeight: '500',
    color: '#6B7280',
    marginBottom: 8,
  },
  uniqueSubstance: {
    padding: 10,
    borderRadius: 8,
    marginBottom: 6,
  },
  uniqueSubstanceName: {
    fontSize: 14,
    fontWeight: '600',
    color: '#111827',
  },
  uniqueSubstanceInfo: {
    fontSize: 12,
    color: '#6B7280',
    marginTop: 4,
  },
  groupCard: {
    padding: 12,
    borderRadius: 10,
    marginBottom: 10,
  },
  groupWarningCard: {
    backgroundColor: '#FEF3C7',
  },
  groupSuccessCard: {
    backgroundColor: '#D1FAE5',
  },
  groupUnknownCard: {
    backgroundColor: '#F3F4F6',
  },
  groupTitle: {
    fontSize: 13,
    fontWeight: '700',
    color: '#111827',
    marginBottom: 4,
  },
  groupText: {
    fontSize: 12,
    color: '#374151',
    marginTop: 2,
  },
  groupWarningText: {
    fontSize: 12,
    color: '#92400E',
    marginTop: 6,
  },
  groupExplanation: {
    fontSize: 12,
    lineHeight: 18,
    color: '#6B7280',
    marginTop: 2,
  },
  cropRegistrationRow: {
    flexDirection: 'row',
    gap: 10,
  },
  cropRegistrationCard: {
    flex: 1,
    padding: 10,
    borderRadius: 10,
  },
  cropRegistered: {
    backgroundColor: '#D1FAE5',
  },
  cropNotRegistered: {
    backgroundColor: '#FEE2E2',
  },
  cropProductName: {
    fontSize: 12,
    fontWeight: '700',
    color: '#111827',
    marginBottom: 4,
  },
  cropGeneralStatus: {
    fontSize: 11,
    color: '#6B7280',
    marginBottom: 4,
  },
  cropRegistrationText: {
    fontSize: 12,
    color: '#374151',
  },
  rateSourceText: {
    fontSize: 11,
    color: '#6B7280',
    marginTop: 4,
  },
  cropInput: {
    marginTop: 12,
  },
  substanceCostSection: {
    marginTop: 12,
    gap: 8,
  },
  substanceCostTitle: {
    fontSize: 13,
    fontWeight: '700',
    color: '#374151',
  },
  substanceCostCard: {
    padding: 10,
    borderRadius: 8,
  },
  substanceCostName: {
    fontSize: 13,
    fontWeight: '700',
    color: '#111827',
    marginBottom: 4,
  },
  substanceCostText: {
    fontSize: 12,
    color: '#374151',
    marginTop: 2,
  },
  priceSection: {
    backgroundColor: '#FFFFFF',
    marginHorizontal: 16,
    borderRadius: 16,
    padding: 16,
    marginBottom: 16,
  },
  priceHint: {
    fontSize: 13,
    color: '#6B7280',
    marginBottom: 12,
  },
  priceInputRow: {
    flexDirection: 'row',
    gap: 12,
  },
  priceInputContainer: {
    flex: 1,
  },
  priceInputLabel: {
    fontSize: 12,
    color: '#6B7280',
    marginBottom: 6,
  },
  priceInput: {
    backgroundColor: '#F3F4F6',
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 16,
    color: '#111827',
  },
  calculateButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#059669',
    paddingVertical: 12,
    borderRadius: 8,
    marginTop: 16,
    gap: 8,
  },
  calculateButtonText: {
    color: '#FFFFFF',
    fontSize: 14,
    fontWeight: '600',
  },
  priceResults: {
    marginTop: 16,
    paddingTop: 16,
    borderTopWidth: 1,
    borderTopColor: '#E5E7EB',
    gap: 12,
  },
  priceResultRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  priceResultLabel: {
    fontSize: 13,
    color: '#374151',
    flex: 1,
  },
  priceResultValues: {
    flexDirection: 'row',
    gap: 8,
  },
  priceResultValue: {
    width: 80,
    textAlign: 'center',
    fontSize: 15,
    fontWeight: '700',
    paddingVertical: 6,
    paddingHorizontal: 8,
    borderRadius: 6,
    overflow: 'hidden',
  },
});
