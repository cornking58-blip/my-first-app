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
  rate_used: number | null;
  rate_source: 'manual' | 'max_registered';
  substances: Substance[];
  antidotes: Substance[];
  total_concentration: number;
  total_per_ha: number | null;
  substance_count: number;
}

interface GroupAnalysis {
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

interface SubstanceCost {
  side: 'left' | 'right';
  substance_name: string;
  name?: string;
  concentration: number;
  unit: string;
  rate_used: number;
  grams_per_ha: number;
  estimated_cost_share_per_ha: number | null;
  estimated_cost_per_gram: number | null;
}

interface PriceAnalysis {
  left_price_per_unit: number | null;
  right_price_per_unit: number | null;
  left_cost_per_ha: number | null;
  right_cost_per_ha: number | null;
  left_cost_per_gram_ai: number | null;
  right_cost_per_gram_ai: number | null;
  left_substances_cost?: SubstanceCost[];
  right_substances_cost?: SubstanceCost[];
  substances_cost: SubstanceCost[];
}

interface CropRegistrationSide {
  has_registration: boolean;
  message: string;
}

interface CropRegistration {
  crop: string;
  left: CropRegistrationSide;
  right: CropRegistrationSide;
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
  price_analysis: PriceAnalysis | null;
  crop_registration?: CropRegistration;
}

export default function CompareScreen() {
  const router = useRouter();
  const { selectedForCompare, clearSelection } = useHerbicideStore();
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
    if (selectedForCompare.length === 2) {
      fetchCompareData();
    }
  }, [selectedForCompare]);

  const parseOptionalNumber = (value: string) => {
    const parsed = value ? parseFloat(value.replace(',', '.')) : undefined;
    return Number.isFinite(parsed) ? parsed : undefined;
  };

  const fetchCompareData = async (withInputs = false) => {
    if (withInputs) {
      setPriceLoading(true);
    } else {
      setLoading(true);
    }
    setError(null);
    
    try {
      const body: any = {
        left_key: selectedForCompare[0],
        right_key: selectedForCompare[1],
      };
      
      const lPrice = parseOptionalNumber(leftPrice);
      const rPrice = parseOptionalNumber(rightPrice);
      const lRate = parseOptionalNumber(leftRate);
      const rRate = parseOptionalNumber(rightRate);
      if (lPrice !== undefined) body.left_price = lPrice;
      if (rPrice !== undefined) body.right_price = rPrice;
      if (lRate !== undefined) body.left_rate = lRate;
      if (rRate !== undefined) body.right_rate = rRate;
      if (crop.trim()) body.crop = crop.trim();
      
      const response = await axios.post(`${API_URL}/api/herbicides/compare-advanced`, body);
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
    fetchCompareData(true);
  };

  const handleBack = () => {
    clearSelection();
    router.back();
  };

  const isActive = (status: string | null) => {
    return status?.toLowerCase().trim() === 'действует';
  };


  const formatNumber = (value: number | null | undefined, digits = 2) => {
    if (value === null || value === undefined || !Number.isFinite(value)) return '—';
    return Number(value.toFixed(digits)).toString();
  };

  const getValueTone = (leftValue: number | null | undefined, rightValue: number | null | undefined, side: 'left' | 'right') => {
    if (leftValue === null || leftValue === undefined || rightValue === null || rightValue === undefined) return null;
    if (leftValue === rightValue) return styles.equalValue;
    return (side === 'left' && leftValue > rightValue) || (side === 'right' && rightValue > leftValue)
      ? styles.higherValue
      : styles.lowerValue;
  };

  const getValueLabel = (leftValue: number | null | undefined, rightValue: number | null | undefined, side: 'left' | 'right') => {
    if (leftValue === null || leftValue === undefined || rightValue === null || rightValue === undefined) return null;
    if (leftValue === rightValue) return 'одинаково';
    return (side === 'left' && leftValue > rightValue) || (side === 'right' && rightValue > leftValue) ? 'выше' : 'ниже';
  };

  const getSubstanceDetails = (product: ProductInfo, substanceName: string) => {
    return product.substances.find(item => item.name.toLowerCase() === substanceName.toLowerCase());
  };

  const renderGroupLabel = (substance?: Substance | null) => {
    if (!substance?.resistance_group) return 'группа не определена';
    const system = substance.resistance_system ? `${substance.resistance_system} ` : '';
    const groupName = substance.resistance_group_name ? ` • ${substance.resistance_group_name}` : '';
    return `${system}${substance.resistance_group}${groupName}`;
  };

  const renderProductColumnLabel = (side: 'left' | 'right', productName: string) => (
    <View style={[styles.columnLabel, side === 'left' ? styles.columnLabelLeft : styles.columnLabelRight]}>
      <Text style={[styles.columnLabelText, side === 'left' ? styles.leftAccentText : styles.rightAccentText]}>
        {side === 'left' ? 'Препарат А' : 'Препарат Б'}
      </Text>
      <Text style={styles.columnLabelName} numberOfLines={1}>{productName}</Text>
    </View>
  );

  const renderRegistrationSide = (side: 'left' | 'right', product: ProductInfo, cropSide?: CropRegistrationSide) => (
    <View style={[styles.registrationColumn, side === 'left' ? styles.leftColumnCard : styles.rightColumnCard]}>
      <Text style={[styles.registrationProductLabel, side === 'left' ? styles.leftAccentText : styles.rightAccentText]}>
        {side === 'left' ? 'Препарат А' : 'Препарат Б'}
      </Text>
      <Text style={styles.registrationLine}>Регистрация: {isActive(product.registration_status) ? 'Действует' : 'Не действует'}</Text>
      {cropSide && <Text style={styles.registrationLine}>Культура: {cropSide.message}</Text>}
    </View>
  );

  const renderUniqueSubstance = (sub: Substance & { category: string; per_ha: number | null }, side: 'left' | 'right') => (
    <View style={[styles.uniqueSubstance, side === 'left' ? styles.leftColumnCard : styles.rightColumnCard]}>
      <Text style={styles.uniqueSubstanceName}>{sub.name}</Text>
      <Text style={styles.uniqueSubstanceInfo}>Концентрация: {formatNumber(sub.concentration)} {sub.unit}</Text>
      <Text style={styles.uniqueSubstanceInfo}>ДВ на 1 га: {formatNumber(sub.per_ha)} г/га</Text>
      <Text style={styles.uniqueSubstanceInfo}>Группа: {renderGroupLabel(sub)}</Text>
    </View>
  );

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

  const { left, right, analysis, group_analysis, price_analysis, crop_registration } = compareData;
  const identicalNames = new Set(analysis.identical_substances.map(item => item.name.toLowerCase()));
  const sameGroupMatches = (group_analysis?.same_group_matches ?? [])
    .map(match => ({
      ...match,
      left_substances: match.left_substances.filter(name => !identicalNames.has(name.toLowerCase())),
      right_substances: match.right_substances.filter(name => !identicalNames.has(name.toLowerCase())),
    }))
    .filter(match => match.left_substances.length > 0 && match.right_substances.length > 0);
  const differentGroupMatches = group_analysis?.different_group_matches ?? [];
  const unknownGroupSubstances = group_analysis?.unknown_group_substances ?? [];
  const hasDirectComparison = analysis.identical_substances.length > 0 || sameGroupMatches.length > 0;

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
            <View style={[styles.productHeaderLeft, styles.leftHeaderAccent]}>
              <Text style={styles.productSideLabel}>Препарат А</Text>
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
              {crop_registration && (
                <View style={[
                  styles.cropRegistrationBadge,
                  crop_registration.left.has_registration ? styles.statusActiveMini : styles.statusInactiveMini
                ]}>
                  <Text style={[
                    styles.cropRegistrationText,
                    crop_registration.left.has_registration ? styles.statusTextActiveMini : styles.statusTextInactiveMini
                  ]}>{crop_registration.left.message}</Text>
                </View>
              )}
            </View>
            
            <View style={styles.vsContainer}>
              <Text style={styles.vsText}>VS</Text>
            </View>
            
            <View style={[styles.productHeaderRight, styles.rightHeaderAccent]}>
              <Text style={styles.productSideLabel}>Препарат Б</Text>
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
              {crop_registration && (
                <View style={[
                  styles.cropRegistrationBadge,
                  crop_registration.right.has_registration ? styles.statusActiveMini : styles.statusInactiveMini
                ]}>
                  <Text style={[
                    styles.cropRegistrationText,
                    crop_registration.right.has_registration ? styles.statusTextActiveMini : styles.statusTextInactiveMini
                  ]}>{crop_registration.right.message}</Text>
                </View>
              )}
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
                <Text style={styles.summaryLabel}>Норма для расчёта, л/га</Text>
                <View style={styles.summaryValues}>
                  <Text style={[styles.summaryValue, styles.leftValue]}>{left.rate_used ?? '—'}</Text>
                  <Text style={[styles.summaryValue, styles.rightValue]}>{right.rate_used ?? '—'}</Text>
                </View>
              </View>
              <View style={styles.summaryRow}>
                <Text style={styles.summaryLabel}>ДВ на 1 га, г</Text>
                <View style={styles.summaryValues}>
                  <View style={[styles.summaryValueBox, styles.leftValue, getValueTone(left.total_per_ha, right.total_per_ha, 'left')]}>
                    <Text style={styles.summaryValueText}>{formatNumber(left.total_per_ha)}</Text>
                    {getValueLabel(left.total_per_ha, right.total_per_ha, 'left') && (
                      <Text style={styles.comparisonTag}>{getValueLabel(left.total_per_ha, right.total_per_ha, 'left')}</Text>
                    )}
                  </View>
                  <View style={[styles.summaryValueBox, styles.rightValue, getValueTone(left.total_per_ha, right.total_per_ha, 'right')]}>
                    <Text style={styles.summaryValueText}>{formatNumber(right.total_per_ha)}</Text>
                    {getValueLabel(left.total_per_ha, right.total_per_ha, 'right') && (
                      <Text style={styles.comparisonTag}>{getValueLabel(left.total_per_ha, right.total_per_ha, 'right')}</Text>
                    )}
                  </View>
                </View>
              </View>
            </View>
            <View style={styles.registrationComparison}>
              {renderRegistrationSide('left', left, crop_registration?.left)}
              {renderRegistrationSide('right', right, crop_registration?.right)}
            </View>
          </View>

          {/* Identical Substances */}
          {analysis.identical_substances.length > 0 && (
            <View style={styles.section}>
              <View style={styles.sectionHeader}>
                <Ionicons name="checkmark-circle" size={20} color="#10B981" />
                <Text style={styles.sectionTitle}>Одинаковые действующие вещества</Text>
              </View>
              {analysis.identical_substances.map((sub, idx) => {
                const leftDetails = getSubstanceDetails(left, sub.name);
                const rightDetails = getSubstanceDetails(right, sub.name);
                return (
                  <View key={idx} style={styles.substanceCard}>
                    <Text style={styles.substanceName}>{sub.name}</Text>
                    <View style={styles.sideBySideHeader}>
                      {renderProductColumnLabel('left', left.product_name)}
                      {renderProductColumnLabel('right', right.product_name)}
                    </View>
                    <View style={styles.substanceComparison}>
                      <View style={[styles.substanceValue, styles.leftColumnCard, getValueTone(sub.left_concentration, sub.right_concentration, 'left')]}>
                        <Text style={styles.valueLabel}>Концентрация</Text>
                        <Text style={styles.substanceConc}>{formatNumber(sub.left_concentration)} {sub.left_unit}</Text>
                        <Text style={styles.comparisonTag}>{getValueLabel(sub.left_concentration, sub.right_concentration, 'left')}</Text>
                        <Text style={styles.valueLabel}>ДВ на 1 га</Text>
                        <Text style={styles.substancePerHa}>{formatNumber(sub.left_per_ha)} г/га</Text>
                        <Text style={styles.valueLabel}>Группа</Text>
                        <Text style={styles.groupInlineText}>{renderGroupLabel(leftDetails)}</Text>
                      </View>
                      <View style={[styles.substanceValue, styles.rightColumnCard, getValueTone(sub.left_concentration, sub.right_concentration, 'right')]}>
                        <Text style={styles.valueLabel}>Концентрация</Text>
                        <Text style={styles.substanceConc}>{formatNumber(sub.right_concentration)} {sub.right_unit}</Text>
                        <Text style={styles.comparisonTag}>{getValueLabel(sub.left_concentration, sub.right_concentration, 'right')}</Text>
                        <Text style={styles.valueLabel}>ДВ на 1 га</Text>
                        <Text style={styles.substancePerHa}>{formatNumber(sub.right_per_ha)} г/га</Text>
                        <Text style={styles.valueLabel}>Группа</Text>
                        <Text style={styles.groupInlineText}>{renderGroupLabel(rightDetails)}</Text>
                      </View>
                    </View>
                  </View>
                );
              })}
            </View>
          )}

          {/* Same Resistance Groups */}
          {sameGroupMatches.length > 0 && (
            <View style={styles.section}>
              <View style={styles.sectionHeader}>
                <Ionicons name="shield-checkmark" size={20} color="#0F766E" />
                <Text style={styles.sectionTitle}>Одна группа действия</Text>
              </View>
              {sameGroupMatches.map((match, idx) => (
                <View key={`same-${idx}`} style={styles.groupCard}>
                  <Text style={styles.groupTitle}>{match.system} {match.group} • {match.group_name || 'название группы не указано'}</Text>
                  <View style={styles.categoryComparison}>
                    <View style={[styles.categoryColumn, styles.leftColumnCard]}>
                      <Text style={[styles.columnSmallTitle, styles.leftAccentText]}>Препарат А</Text>
                      {match.left_substances.map((name, itemIdx) => (
                        <Text key={`left-same-${itemIdx}`} style={styles.categorySubstance}>{name}</Text>
                      ))}
                    </View>
                    <View style={[styles.categoryColumn, styles.rightColumnCard]}>
                      <Text style={[styles.columnSmallTitle, styles.rightAccentText]}>Препарат Б</Text>
                      {match.right_substances.map((name, itemIdx) => (
                        <Text key={`right-same-${itemIdx}`} style={styles.categorySubstance}>{name}</Text>
                      ))}
                    </View>
                  </View>
                  <Text style={styles.groupNeutralText}>одна группа действия</Text>
                </View>
              ))}
            </View>
          )}

          {!hasDirectComparison && (
            <View style={styles.section}>
              <View style={styles.sectionHeader}>
                <Ionicons name="information-circle" size={20} color="#6B7280" />
                <Text style={styles.sectionTitle}>Прямое сопоставление</Text>
              </View>
              <Text style={styles.neutralMessage}>Действующие вещества и группы действия разные.</Text>
              <Text style={styles.neutralMessage}>Прямое сопоставление не найдено.</Text>
            </View>
          )}

          {/* Similar by Category */}
          {analysis.similar_by_category.length > 0 && (
            <View style={styles.section}>
              <View style={styles.sectionHeader}>
                <Ionicons name="git-compare" size={20} color="#F59E0B" />
                <Text style={styles.sectionTitle}>Сопоставление по механизму</Text>
              </View>
              {analysis.similar_by_category.map((cat, idx) => (
                <View key={idx} style={styles.categoryCard}>
                  <View style={styles.categoryHeader}>
                    <Ionicons name="flask" size={16} color="#6B7280" />
                    <Text style={styles.categoryName}>{cat.category}</Text>
                  </View>
                  <View style={styles.categoryComparison}>
                    <View style={[styles.categoryColumn, styles.leftColumnCard]}>
                      <Text style={[styles.columnSmallTitle, styles.leftAccentText]}>Препарат А</Text>
                      {cat.left_substances.map((s, i) => (
                        <Text key={i} style={styles.categorySubstance}>
                          {s.name} ({formatNumber(s.concentration)} {s.unit})
                        </Text>
                      ))}
                    </View>
                    <View style={[styles.categoryColumn, styles.rightColumnCard]}>
                      <Text style={[styles.columnSmallTitle, styles.rightAccentText]}>Препарат Б</Text>
                      {cat.right_substances.map((s, i) => (
                        <Text key={i} style={styles.categorySubstance}>
                          {s.name} ({formatNumber(s.concentration)} {s.unit})
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
                <Text style={styles.sectionTitle}>Дополнительные компоненты</Text>
              </View>
              <View style={styles.uniqueColumns}>
                <View style={styles.uniqueBlock}>
                  <Text style={[styles.uniqueBlockTitle, styles.leftAccentText]}>У препарата А дополнительно:</Text>
                  {analysis.left_unique_substances.length > 0 ? (
                    analysis.left_unique_substances.map((sub, idx) => (
                      <React.Fragment key={`left-unique-${idx}`}>{renderUniqueSubstance(sub, 'left')}</React.Fragment>
                    ))
                  ) : (
                    <Text style={styles.emptyColumnText}>Нет дополнительных компонентов</Text>
                  )}
                </View>
                <View style={styles.uniqueBlock}>
                  <Text style={[styles.uniqueBlockTitle, styles.rightAccentText]}>У препарата Б дополнительно:</Text>
                  {analysis.right_unique_substances.length > 0 ? (
                    analysis.right_unique_substances.map((sub, idx) => (
                      <React.Fragment key={`right-unique-${idx}`}>{renderUniqueSubstance(sub, 'right')}</React.Fragment>
                    ))
                  ) : (
                    <Text style={styles.emptyColumnText}>Нет дополнительных компонентов</Text>
                  )}
                </View>
              </View>
            </View>
          )}

          {/* Other Resistance Groups */}
          {(differentGroupMatches.length > 0 || unknownGroupSubstances.length > 0) && (
            <View style={styles.section}>
              <View style={styles.sectionHeader}>
                <Ionicons name="shield-outline" size={20} color="#6B7280" />
                <Text style={styles.sectionTitle}>Дополнительная информация о группах</Text>
              </View>

              {differentGroupMatches.map((match, idx) => (
                <View key={`different-${idx}`} style={styles.groupCard}>
                  <View style={styles.categoryComparison}>
                    <View style={[styles.categoryColumn, styles.leftColumnCard]}>
                      <Text style={[styles.columnSmallTitle, styles.leftAccentText]}>Препарат А</Text>
                      <Text style={styles.categorySubstance}>{match.left_substance}</Text>
                      <Text style={styles.groupInlineText}>Группа: {match.left_group || 'группа не определена'}</Text>
                    </View>
                    <View style={[styles.categoryColumn, styles.rightColumnCard]}>
                      <Text style={[styles.columnSmallTitle, styles.rightAccentText]}>Препарат Б</Text>
                      <Text style={styles.categorySubstance}>{match.right_substance}</Text>
                      <Text style={styles.groupInlineText}>Группа: {match.right_group || 'группа не определена'}</Text>
                    </View>
                  </View>
                  <Text style={styles.groupNeutralText}>разные группы действия</Text>
                </View>
              ))}

              {unknownGroupSubstances.length > 0 && (
                <View style={styles.groupCard}>
                  <Text style={styles.groupTitle}>Группа не определена</Text>
                  <View style={styles.categoryComparison}>
                    <View style={[styles.categoryColumn, styles.leftColumnCard]}>
                      <Text style={[styles.columnSmallTitle, styles.leftAccentText]}>Препарат А</Text>
                      {unknownGroupSubstances.filter(item => item.side === 'left').map((item, idx) => (
                        <Text key={`unknown-left-${idx}`} style={styles.categorySubstance}>{item.substance}</Text>
                      ))}
                    </View>
                    <View style={[styles.categoryColumn, styles.rightColumnCard]}>
                      <Text style={[styles.columnSmallTitle, styles.rightAccentText]}>Препарат Б</Text>
                      {unknownGroupSubstances.filter(item => item.side === 'right').map((item, idx) => (
                        <Text key={`unknown-right-${idx}`} style={styles.categorySubstance}>{item.substance}</Text>
                      ))}
                    </View>
                  </View>
                </View>
              )}
            </View>
          )}
          {/* Price Input Section */}
          <View style={styles.priceSection}>
            <View style={styles.sectionHeader}>
              <Ionicons name="calculator" size={20} color="#059669" />
              <Text style={styles.sectionTitle}>Расчёт стоимости</Text>
            </View>
            
            <Text style={styles.priceHint}>Введите цену за 1 л/кг препарата</Text>
            
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
                  placeholder="Напр. 0,8"
                  placeholderTextColor="#9CA3AF"
                  keyboardType="decimal-pad"
                  value={leftRate}
                  onChangeText={setLeftRate}
                />
              </View>
              <View style={styles.priceInputContainer}>
                <Text style={styles.priceInputLabel}>Норма препарата Б</Text>
                <TextInput
                  style={styles.priceInput}
                  placeholder="Напр. 1,0"
                  placeholderTextColor="#9CA3AF"
                  keyboardType="decimal-pad"
                  value={rightRate}
                  onChangeText={setRightRate}
                />
              </View>
            </View>

            <View style={styles.cropInputContainer}>
              <Text style={styles.priceInputLabel}>Культура для проверки регистрации</Text>
              <TextInput
                style={styles.priceInput}
                placeholder="Напр. подсолнечник"
                placeholderTextColor="#9CA3AF"
                value={crop}
                onChangeText={setCrop}
              />
            </View>
            
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
                  <Text style={styles.priceResultLabel}>Стоимость обработки 1 га, ₽</Text>
                  <View style={styles.priceResultValues}>
                    <View style={[styles.priceResultValueBox, styles.leftValue, getValueTone(price_analysis.left_cost_per_ha, price_analysis.right_cost_per_ha, 'left')]}>
                      <Text style={styles.summaryValueText}>{formatNumber(price_analysis.left_cost_per_ha, 0)}</Text>
                      {getValueLabel(price_analysis.left_cost_per_ha, price_analysis.right_cost_per_ha, 'left') && (
                        <Text style={styles.comparisonTag}>{getValueLabel(price_analysis.left_cost_per_ha, price_analysis.right_cost_per_ha, 'left')}</Text>
                      )}
                    </View>
                    <View style={[styles.priceResultValueBox, styles.rightValue, getValueTone(price_analysis.left_cost_per_ha, price_analysis.right_cost_per_ha, 'right')]}>
                      <Text style={styles.summaryValueText}>{formatNumber(price_analysis.right_cost_per_ha, 0)}</Text>
                      {getValueLabel(price_analysis.left_cost_per_ha, price_analysis.right_cost_per_ha, 'right') && (
                        <Text style={styles.comparisonTag}>{getValueLabel(price_analysis.left_cost_per_ha, price_analysis.right_cost_per_ha, 'right')}</Text>
                      )}
                    </View>
                  </View>
                </View>
                
                <View style={styles.substanceCostBlock}>
                  <Text style={styles.substanceCostTitle}>Стоимость действующих веществ</Text>
                  <View style={styles.substanceCostColumns}>
                    <View style={styles.substanceCostColumn}>
                      {(price_analysis.left_substances_cost ?? price_analysis.substances_cost.filter(item => item.side === 'left')).map((item, idx) => (
                        <View key={`left-cost-${idx}`} style={[styles.substanceCostItem, styles.leftColumnCard]}>
                          <Text style={[styles.substanceCostName, styles.leftValue]}>{item.substance_name || item.name}</Text>
                          <Text style={styles.substanceCostText}>{item.grams_per_ha?.toFixed(2) ?? '—'} г/га</Text>
                          <Text style={styles.substanceCostText}>{item.estimated_cost_share_per_ha?.toFixed(0) ?? '—'} ₽/га</Text>
                          <Text style={styles.substanceCostText}>{item.estimated_cost_per_gram?.toFixed(2) ?? '—'} ₽/г</Text>
                        </View>
                      ))}
                    </View>
                    <View style={styles.substanceCostColumn}>
                      {(price_analysis.right_substances_cost ?? price_analysis.substances_cost.filter(item => item.side === 'right')).map((item, idx) => (
                        <View key={`right-cost-${idx}`} style={[styles.substanceCostItem, styles.rightColumnCard]}>
                          <Text style={[styles.substanceCostName, styles.rightValue]}>{item.substance_name || item.name}</Text>
                          <Text style={styles.substanceCostText}>{item.grams_per_ha?.toFixed(2) ?? '—'} г/га</Text>
                          <Text style={styles.substanceCostText}>{item.estimated_cost_share_per_ha?.toFixed(0) ?? '—'} ₽/га</Text>
                          <Text style={styles.substanceCostText}>{item.estimated_cost_per_gram?.toFixed(2) ?? '—'} ₽/г</Text>
                        </View>
                      ))}
                    </View>
                  </View>
                </View>
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
    padding: 10,
    borderRadius: 14,
    borderWidth: 1,
  },
  productHeaderRight: {
    flex: 1,
    alignItems: 'center',
    padding: 10,
    borderRadius: 14,
    borderWidth: 1,
  },

  productSideLabel: {
    fontSize: 11,
    fontWeight: '800',
    textTransform: 'uppercase',
    letterSpacing: 0.4,
    marginBottom: 6,
    color: '#6B7280',
  },
  leftHeaderAccent: {
    backgroundColor: '#EFF6FF',
    borderColor: '#3B82F6',
  },
  rightHeaderAccent: {
    backgroundColor: '#F5F3FF',
    borderColor: '#8B5CF6',
  },
  leftColumnCard: {
    backgroundColor: '#EFF6FF',
    borderColor: '#93C5FD',
    borderWidth: 1,
  },
  rightColumnCard: {
    backgroundColor: '#F5F3FF',
    borderColor: '#C4B5FD',
    borderWidth: 1,
  },
  leftAccentText: {
    color: '#1D4ED8',
  },
  rightAccentText: {
    color: '#6D28D9',
  },
  summaryValueBox: {
    width: 76,
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 5,
    paddingHorizontal: 6,
    borderRadius: 8,
    overflow: 'hidden',
    borderWidth: 1,
    borderColor: 'transparent',
  },
  summaryValueText: {
    fontSize: 14,
    fontWeight: '800',
    color: '#111827',
  },
  comparisonTag: {
    marginTop: 2,
    fontSize: 10,
    fontWeight: '700',
    color: '#374151',
  },
  sideBySideHeader: {
    flexDirection: 'row',
    gap: 8,
    marginBottom: 8,
  },
  columnLabel: {
    flex: 1,
    borderRadius: 8,
    paddingVertical: 6,
    paddingHorizontal: 8,
  },
  columnLabelLeft: {
    backgroundColor: '#DBEAFE',
  },
  columnLabelRight: {
    backgroundColor: '#EDE9FE',
  },
  columnLabelText: {
    fontSize: 11,
    fontWeight: '800',
  },
  columnLabelName: {
    fontSize: 10,
    color: '#4B5563',
    marginTop: 2,
  },
  valueLabel: {
    fontSize: 10,
    fontWeight: '700',
    color: '#6B7280',
    marginTop: 6,
    marginBottom: 2,
  },
  groupInlineText: {
    fontSize: 11,
    lineHeight: 15,
    color: '#374151',
  },
  columnSmallTitle: {
    fontSize: 11,
    fontWeight: '800',
    marginBottom: 6,
  },
  groupNeutralText: {
    fontSize: 12,
    fontWeight: '700',
    color: '#0F766E',
    marginTop: 8,
  },
  neutralMessage: {
    fontSize: 13,
    color: '#4B5563',
    lineHeight: 19,
  },
  uniqueColumns: {
    flexDirection: 'row',
    gap: 8,
  },
  emptyColumnText: {
    fontSize: 12,
    color: '#9CA3AF',
    lineHeight: 17,
  },
  registrationComparison: {
    flexDirection: 'row',
    gap: 8,
    marginTop: 14,
  },
  registrationColumn: {
    flex: 1,
    borderRadius: 10,
    padding: 10,
  },
  registrationProductLabel: {
    fontSize: 11,
    fontWeight: '800',
    marginBottom: 4,
  },
  registrationLine: {
    fontSize: 12,
    color: '#374151',
    lineHeight: 17,
  },
  priceResultValueBox: {
    width: 82,
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 6,
    paddingHorizontal: 6,
    borderRadius: 8,
    overflow: 'hidden',
    borderWidth: 1,
    borderColor: 'transparent',
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
  cropRegistrationBadge: {
    marginTop: 8,
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 4,
  },
  cropRegistrationText: {
    fontSize: 10,
    fontWeight: '600',
    textAlign: 'center',
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
  higherValue: {
    backgroundColor: '#DCFCE7',
    borderColor: '#22C55E',
  },
  lowerValue: {
    opacity: 0.82,
  },
  equalValue: {
    backgroundColor: '#F3F4F6',
    borderColor: '#9CA3AF',
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
  cropInputContainer: {
    marginTop: 12,
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
  substanceCostBlock: {
    marginTop: 12,
  },
  substanceCostTitle: {
    fontSize: 13,
    fontWeight: '700',
    color: '#374151',
    marginBottom: 8,
  },
  substanceCostColumns: {
    flexDirection: 'row',
    gap: 8,
  },
  substanceCostColumn: {
    flex: 1,
    gap: 8,
  },
  substanceCostItem: {
    backgroundColor: '#F9FAFB',
    borderRadius: 8,
    padding: 8,
  },
  substanceCostName: {
    fontSize: 12,
    fontWeight: '700',
    marginBottom: 4,
  },
  substanceCostText: {
    fontSize: 11,
    color: '#6B7280',
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
