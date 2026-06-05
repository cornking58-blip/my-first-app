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
import { RetryErrorCard } from '../src/components/RetryErrorCard';

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
  effect_summary?: string | null;
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
  max_rate_unit?: string | null;
  rate_used: number | null;
  rate_unit?: string | null;
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
    effect_summary?: string | null;
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
  rate_unit?: string | null;
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

export default function FungicideCompareScreen() {
  const router = useRouter();
  const { selectedFungicidesForCompare, clearFungicideSelection } = useHerbicideStore();
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
    if (selectedFungicidesForCompare.length === 2) {
      fetchCompareData();
    }
  }, [selectedFungicidesForCompare]);

  const parseOptionalNumber = (value: string) => {
    const parsed = value ? parseFloat(value.replace(',', '.')) : undefined;
    return Number.isFinite(parsed) ? parsed : undefined;
  };

  const formatRate = (rate?: number | null, unit?: string | null) => {
    if (rate === null || rate === undefined) return '—';
    return unit ? `${formatNumber(rate)} ${unit}` : formatNumber(rate);
  };

  const getManualRatePlaceholder = (fallback: string, unit?: string | null) => (
    unit ? `${fallback} ${unit}` : fallback
  );

  const calculateActiveAmount = (substance?: Substance, product?: ProductInfo) => {
    if (!substance || !product?.rate_used) return null;
    if (!product.rate_unit) return substance.concentration * product.rate_used;
    if (substance.unit === 'г/кг' && product.rate_unit.startsWith('кг/')) {
      return substance.concentration * product.rate_used;
    }
    if (substance.unit === 'г/л' && product.rate_unit.startsWith('л/')) {
      return substance.concentration * product.rate_used;
    }
    return null;
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
        left_key: selectedFungicidesForCompare[0],
        right_key: selectedFungicidesForCompare[1],
      };

      const lPrice = parseOptionalNumber(leftPrice);
      const rPrice = parseOptionalNumber(rightPrice);
      const lRate = parseOptionalNumber(leftRate);
      const rRate = parseOptionalNumber(rightRate);
      if (lPrice !== undefined) body.left_price = lPrice;
      if (rPrice !== undefined) body.right_price = rPrice;
      if (lRate !== undefined) body.left_rate = lRate;
      if (rRate !== undefined) body.right_rate = rRate;
      if (crop.trim().length > 0) body.crop = crop.trim();

      const response = await axios.post(`${API_URL}/api/fungicides/compare-advanced`, body);
      setCompareData(response.data);
    } catch (err) {
      console.error('Compare failed:', err);
      setError('Не удалось загрузить данные');
    } finally {
      setLoading(false);
      setPriceLoading(false);
    }
  };

  const handlePriceCalculation = () => {
    fetchCompareData(true);
  };

  const hasLeftPrice = parseOptionalNumber(leftPrice) !== undefined;
  const hasRightPrice = parseOptionalNumber(rightPrice) !== undefined;
  const hasAnyPrice = hasLeftPrice || hasRightPrice;

  const handleBack = () => {
    clearFungicideSelection();
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

  const getSubstanceKey = (name: string) => name.trim().toLowerCase();

  const namesMatch = (leftName?: string | null, rightName?: string | null) => {
    const leftKey = getSubstanceKey(leftName ?? '');
    const rightKey = getSubstanceKey(rightName ?? '');
    return Boolean(leftKey && rightKey && (leftKey === rightKey || leftKey.includes(rightKey) || rightKey.includes(leftKey)));
  };

  const getSubstanceDetails = (product: ProductInfo, substanceName: string) => {
    return product.substances.find(item => namesMatch(item.name, substanceName));
  };

  const getSubstanceCost = (side: 'left' | 'right', substanceName: string) => {
    const costs = side === 'left'
      ? compareData?.price_analysis?.left_substances_cost ?? compareData?.price_analysis?.substances_cost.filter(item => item.side === 'left')
      : compareData?.price_analysis?.right_substances_cost ?? compareData?.price_analysis?.substances_cost.filter(item => item.side === 'right');
    return costs?.find(item => namesMatch(item.substance_name || item.name, substanceName));
  };

  const shouldShowSubstanceCost = (cost: SubstanceCost | undefined, hasPrice: boolean) => {
    return hasPrice
      && cost?.grams_per_ha !== null
      && cost?.grams_per_ha !== undefined
      && cost.grams_per_ha > 0
      && cost.estimated_cost_per_gram !== null
      && cost.estimated_cost_per_gram !== undefined;
  };

  const renderGroupLabel = (substance?: Substance | null) => {
    if (!substance?.resistance_group) return 'группа не определена';
    const system = substance.resistance_system ? `${substance.resistance_system} ` : '';
    const groupName = substance.resistance_group_name ? ` • ${substance.resistance_group_name}` : '';
    return `${system}${substance.resistance_group}${groupName}`;
  };

  const renderEffectSummary = (effectSummary?: string | null) => {
    if (!effectSummary) return null;
    return <Text style={styles.groupEffectText}>{effectSummary}</Text>;
  };

  const renderProductColumnLabel = (side: 'left' | 'right', productName: string) => (
    <View style={[styles.columnLabel, side === 'left' ? styles.columnLabelLeft : styles.columnLabelRight]}>
      <Text style={[styles.columnLabelText, side === 'left' ? styles.leftAccentText : styles.rightAccentText]}>
        {side === 'left' ? 'A' : 'B'}
      </Text>
      <Text style={styles.columnLabelName}>{productName}</Text>
    </View>
  );

  const renderSubstanceMetrics = (substance: Substance | undefined, side: 'left' | 'right', perHa?: number | null) => {
    if (!substance) return null;
    const cost = getSubstanceCost(side, substance.name);
    const product = side === 'left' ? compareData?.left : compareData?.right;
    const showCost = shouldShowSubstanceCost(cost, side === 'left' ? hasLeftPrice : hasRightPrice);
    const calculatedPerHa = perHa ?? substance.per_ha ?? calculateActiveAmount(substance, product);

    return (
      <View style={[styles.metricSubstanceCard, side === 'left' ? styles.leftColumnCard : styles.rightColumnCard]}>
        <Text style={styles.uniqueSubstanceName}>{substance.name}</Text>
        <Text style={styles.uniqueSubstanceInfo}>Концентрация: {formatNumber(substance.concentration)} {substance.unit}</Text>
        <Text style={styles.uniqueSubstanceInfo}>Норма: {formatRate(product?.rate_used, product?.rate_unit)}</Text>
        <Text style={styles.uniqueSubstanceInfo}>ДВ на 1 га: {formatNumber(calculatedPerHa)} г/га</Text>
        {showCost && (
          <Text style={styles.uniqueSubstanceInfo}>Стоимость 1 г ДВ: {formatNumber(cost?.estimated_cost_per_gram)} ₽/г</Text>
        )}
        <Text style={styles.uniqueSubstanceInfo}>Группа: {renderGroupLabel(substance)}</Text>
        {renderEffectSummary(substance.effect_summary)}
      </View>
    );
  };

  const renderUniqueSubstance = (sub: Substance & { category: string; per_ha: number | null }, side: 'left' | 'right') => {
    const cost = getSubstanceCost(side, sub.name);
    const product = side === 'left' ? compareData?.left : compareData?.right;
    const showCost = shouldShowSubstanceCost(cost, side === 'left' ? hasLeftPrice : hasRightPrice);
    const calculatedPerHa = sub.per_ha ?? calculateActiveAmount(sub, product);

    return (
      <View style={[styles.uniqueSubstance, side === 'left' ? styles.leftColumnCard : styles.rightColumnCard]}>
        <Text style={styles.uniqueSubstanceName}>{sub.name}</Text>
        <Text style={styles.uniqueSubstanceInfo}>Концентрация: {formatNumber(sub.concentration)} {sub.unit}</Text>
        <Text style={styles.uniqueSubstanceInfo}>ДВ на 1 га: {formatNumber(calculatedPerHa)} г/га</Text>
        {showCost && (
          <Text style={styles.uniqueSubstanceInfo}>Стоимость 1 г ДВ: {formatNumber(cost?.estimated_cost_per_gram)} ₽/г</Text>
        )}
        <Text style={styles.uniqueSubstanceInfo}>Группа: {renderGroupLabel(sub)}</Text>
        {renderEffectSummary(sub.effect_summary)}
        <Text style={styles.uniqueSubstanceInfo}>Прямое сопоставление не найдено.</Text>
      </View>
    );
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
          <RetryErrorCard onRetry={() => fetchCompareData()} />
        </View>
      </SafeAreaView>
    );
  }

  const { left, right, analysis, group_analysis, price_analysis, crop_registration } = compareData;
  const hasCropInput = crop.trim().length > 0;
  const hasLeftComposition = (left.active_substances_raw?.trim().length ?? 0) > 0;
  const hasRightComposition = (right.active_substances_raw?.trim().length ?? 0) > 0;
  const hasLeftFormulation = (left.formulation?.trim().length ?? 0) > 0;
  const hasRightFormulation = (right.formulation?.trim().length ?? 0) > 0;
  const hasPriceResultValues = price_analysis !== null
    && (price_analysis.left_price_per_unit !== null || price_analysis.right_price_per_unit !== null);
  const usedLeftSubstances = new Set(analysis.identical_substances.map(item => getSubstanceKey(item.name)));
  const usedRightSubstances = new Set(analysis.identical_substances.map(item => getSubstanceKey(item.name)));
  const sameGroupMatches = (group_analysis?.same_group_matches ?? [])
    .map(match => {
      const leftSubstances = match.left_substances.filter(name => !usedLeftSubstances.has(getSubstanceKey(name)));
      const rightSubstances = match.right_substances.filter(name => !usedRightSubstances.has(getSubstanceKey(name)));

      if (leftSubstances.length > 0 && rightSubstances.length > 0) {
        leftSubstances.forEach(name => usedLeftSubstances.add(getSubstanceKey(name)));
        rightSubstances.forEach(name => usedRightSubstances.add(getSubstanceKey(name)));
      }

      return {
        ...match,
        left_substances: leftSubstances,
        right_substances: rightSubstances,
      };
    })
    .filter(match => match.left_substances.length > 0 && match.right_substances.length > 0);
  const leftAdditionalSubstances = analysis.left_unique_substances.filter(sub => !usedLeftSubstances.has(getSubstanceKey(sub.name)));
  const rightAdditionalSubstances = analysis.right_unique_substances.filter(sub => !usedRightSubstances.has(getSubstanceKey(sub.name)));
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
              {hasLeftComposition ? (
                <Text style={styles.productComposition} numberOfLines={4}>д.в.: {left.active_substances_raw}</Text>
              ) : null}
              {hasLeftFormulation ? (
                <View style={styles.formulationBadge}>
                  <Text style={styles.formulationText}>{left.formulation}</Text>
                </View>
              ) : null}
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
              {hasCropInput && crop_registration ? (
                <View style={[
                  styles.cropRegistrationBadge,
                  crop_registration.left.has_registration ? styles.statusActiveMini : styles.statusInactiveMini
                ]}>
                  <Text style={[
                    styles.cropRegistrationText,
                    crop_registration.left.has_registration ? styles.statusTextActiveMini : styles.statusTextInactiveMini
                  ]}>{crop_registration.left.message}</Text>
                </View>
              ) : null}
            </View>

            <View style={styles.vsContainer}>
              <Text style={styles.vsText}>VS</Text>
            </View>

            <View style={[styles.productHeaderRight, styles.rightHeaderAccent]}>
              <Text style={styles.productSideLabel}>Препарат Б</Text>
              <Text style={styles.productHeaderName} numberOfLines={2}>{right.product_name}</Text>
              {hasRightComposition ? (
                <Text style={styles.productComposition} numberOfLines={4}>д.в.: {right.active_substances_raw}</Text>
              ) : null}
              {hasRightFormulation ? (
                <View style={styles.formulationBadge}>
                  <Text style={styles.formulationText}>{right.formulation}</Text>
                </View>
              ) : null}
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
              {hasCropInput && crop_registration ? (
                <View style={[
                  styles.cropRegistrationBadge,
                  crop_registration.right.has_registration ? styles.statusActiveMini : styles.statusInactiveMini
                ]}>
                  <Text style={[
                    styles.cropRegistrationText,
                    crop_registration.right.has_registration ? styles.statusTextActiveMini : styles.statusTextInactiveMini
                  ]}>{crop_registration.right.message}</Text>
                </View>
              ) : null}
            </View>
          </View>

          {/* Top Calculation Controls */}
          <View style={styles.priceSection}>
            <View style={styles.sectionHeader}>
              <Ionicons name="calculator" size={20} color="#059669" />
              <Text style={styles.sectionTitle}>Параметры расчёта</Text>
            </View>
            <Text style={styles.priceHint}>Если норму не заполнить, берётся максимальная зарегистрированная норма. Цена нужна только для экономики.</Text>

            <View style={styles.priceInputRow}>
              <View style={[styles.priceInputContainer, styles.leftControlCard]}>
                <Text style={[styles.priceInputLabel, styles.leftAccentText]}>Норма: {left.product_name}</Text>
                <TextInput
                  style={styles.priceInput}
                  placeholder={getManualRatePlaceholder('Напр. 0,8', left.rate_unit)}
                  placeholderTextColor="#9CA3AF"
                  keyboardType="decimal-pad"
                  value={leftRate}
                  onChangeText={setLeftRate}
                />
                <Text style={styles.inputHint}>По умолчанию: максимальная зарегистрированная норма</Text>
                <Text style={styles.inputHint}>Источник нормы: {leftRate.trim().length > 0 ? 'введена вручную' : 'максимальная зарегистрированная'}</Text>
                <Text style={[styles.priceInputLabel, styles.leftAccentText]}>Цена: {left.product_name}</Text>
                <TextInput
                  style={styles.priceInput}
                  placeholder="Цена, ₽"
                  placeholderTextColor="#9CA3AF"
                  keyboardType="decimal-pad"
                  value={leftPrice}
                  onChangeText={setLeftPrice}
                />
              </View>
              <View style={[styles.priceInputContainer, styles.rightControlCard]}>
                <Text style={[styles.priceInputLabel, styles.rightAccentText]}>Норма: {right.product_name}</Text>
                <TextInput
                  style={styles.priceInput}
                  placeholder={getManualRatePlaceholder('Напр. 1,0', right.rate_unit)}
                  placeholderTextColor="#9CA3AF"
                  keyboardType="decimal-pad"
                  value={rightRate}
                  onChangeText={setRightRate}
                />
                <Text style={styles.inputHint}>По умолчанию: максимальная зарегистрированная норма</Text>
                <Text style={styles.inputHint}>Источник нормы: {rightRate.trim().length > 0 ? 'введена вручную' : 'максимальная зарегистрированная'}</Text>
                <Text style={[styles.priceInputLabel, styles.rightAccentText]}>Цена: {right.product_name}</Text>
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
            {hasCropInput && crop_registration ? (
              <View style={styles.cropResultRow}>
                <View style={[styles.cropResultCard, styles.leftColumnCard]}>
                  <Text style={[styles.columnSmallTitle, styles.leftAccentText]}>{left.product_name}</Text>
                  <Text style={styles.registrationLine}>{crop_registration.left.message}</Text>
                </View>
                <View style={[styles.cropResultCard, styles.rightColumnCard]}>
                  <Text style={[styles.columnSmallTitle, styles.rightAccentText]}>{right.product_name}</Text>
                  <Text style={styles.registrationLine}>{crop_registration.right.message}</Text>
                </View>
              </View>
            ) : null}

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

            {!hasAnyPrice && (
              <Text style={styles.neutralEconomyText}>Цена не указана, экономика не рассчитана.</Text>
            )}

            {hasAnyPrice && hasPriceResultValues && price_analysis ? (
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
              </View>
            ) : null}
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
                <Text style={styles.summaryLabel}>Максимальная норма</Text>
                <View style={styles.summaryValues}>
                  <Text style={[styles.summaryValue, styles.leftValue]}>{formatRate(left.max_rate, left.max_rate_unit)}</Text>
                  <Text style={[styles.summaryValue, styles.rightValue]}>{formatRate(right.max_rate, right.max_rate_unit)}</Text>
                </View>
              </View>
              <View style={styles.summaryRow}>
                <Text style={styles.summaryLabel}>Норма для расчёта</Text>
                <View style={styles.summaryValues}>
                  <Text style={[styles.summaryValue, styles.leftValue]}>{formatRate(left.rate_used, left.rate_unit)}</Text>
                  <Text style={[styles.summaryValue, styles.rightValue]}>{formatRate(right.rate_used, right.rate_unit)}</Text>
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
                const leftCost = getSubstanceCost('left', leftDetails?.name ?? sub.name);
                const rightCost = getSubstanceCost('right', rightDetails?.name ?? sub.name);
                const showLeftCost = shouldShowSubstanceCost(leftCost, hasLeftPrice);
                const showRightCost = shouldShowSubstanceCost(rightCost, hasRightPrice);
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
                        {showLeftCost && (
                          <>
                            <Text style={styles.valueLabel}>Стоимость 1 г ДВ</Text>
                            <Text style={styles.substancePerHa}>{formatNumber(leftCost?.estimated_cost_per_gram)} ₽/г</Text>
                          </>
                        )}
                        <Text style={styles.valueLabel}>Группа</Text>
                        <Text style={styles.groupInlineText}>{renderGroupLabel(leftDetails)}</Text>
                        {renderEffectSummary(leftDetails?.effect_summary)}
                      </View>
                      <View style={[styles.substanceValue, styles.rightColumnCard, getValueTone(sub.left_concentration, sub.right_concentration, 'right')]}>
                        <Text style={styles.valueLabel}>Концентрация</Text>
                        <Text style={styles.substanceConc}>{formatNumber(sub.right_concentration)} {sub.right_unit}</Text>
                        <Text style={styles.comparisonTag}>{getValueLabel(sub.left_concentration, sub.right_concentration, 'right')}</Text>
                        <Text style={styles.valueLabel}>ДВ на 1 га</Text>
                        <Text style={styles.substancePerHa}>{formatNumber(sub.right_per_ha)} г/га</Text>
                        {showRightCost && (
                          <>
                            <Text style={styles.valueLabel}>Стоимость 1 г ДВ</Text>
                            <Text style={styles.substancePerHa}>{formatNumber(rightCost?.estimated_cost_per_gram)} ₽/г</Text>
                          </>
                        )}
                        <Text style={styles.valueLabel}>Группа</Text>
                        <Text style={styles.groupInlineText}>{renderGroupLabel(rightDetails)}</Text>
                        {renderEffectSummary(rightDetails?.effect_summary)}
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
                  <Text style={styles.groupTitle}>{match.system} {match.group}{match.group_name ? ` • ${match.group_name}` : ''}</Text>
                  {renderEffectSummary(match.effect_summary)}
                  <Text style={styles.groupNeutralText}>Разные действующие вещества, но одна группа действия.</Text>
                  <View style={styles.categoryComparison}>
                    <View style={styles.categoryColumn}>
                      <Text style={[styles.columnSmallTitle, styles.leftAccentText]}>{left.product_name}</Text>
                      {match.left_substances.map((name, itemIdx) => (
                        <React.Fragment key={`left-same-${itemIdx}`}>
                          {renderSubstanceMetrics(getSubstanceDetails(left, name), 'left')}
                        </React.Fragment>
                      ))}
                    </View>
                    <View style={styles.categoryColumn}>
                      <Text style={[styles.columnSmallTitle, styles.rightAccentText]}>{right.product_name}</Text>
                      {match.right_substances.map((name, itemIdx) => (
                        <React.Fragment key={`right-same-${itemIdx}`}>
                          {renderSubstanceMetrics(getSubstanceDetails(right, name), 'right')}
                        </React.Fragment>
                      ))}
                    </View>
                  </View>
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


          {/* Unique Substances */}
          {(leftAdditionalSubstances.length > 0 || rightAdditionalSubstances.length > 0) && (
            <View style={styles.section}>
              <View style={styles.sectionHeader}>
                <Ionicons name="add-circle" size={20} color="#6366F1" />
                <Text style={styles.sectionTitle}>Дополнительные компоненты</Text>
              </View>
              <View style={styles.uniqueColumns}>
                <View style={styles.uniqueBlock}>
                  <Text style={[styles.uniqueBlockTitle, styles.leftAccentText]}>У {left.product_name} дополнительно:</Text>
                  {leftAdditionalSubstances.length > 0 ? (
                    leftAdditionalSubstances.map((sub, idx) => (
                      <React.Fragment key={`left-unique-${idx}`}>{renderUniqueSubstance(sub, 'left')}</React.Fragment>
                    ))
                  ) : (
                    <Text style={styles.emptyColumnText}>Нет дополнительных компонентов</Text>
                  )}
                </View>
                <View style={styles.uniqueBlock}>
                  <Text style={[styles.uniqueBlockTitle, styles.rightAccentText]}>У {right.product_name} дополнительно:</Text>
                  {rightAdditionalSubstances.length > 0 ? (
                    rightAdditionalSubstances.map((sub, idx) => (
                      <React.Fragment key={`right-unique-${idx}`}>{renderUniqueSubstance(sub, 'right')}</React.Fragment>
                    ))
                  ) : (
                    <Text style={styles.emptyColumnText}>Нет дополнительных компонентов</Text>
                  )}
                </View>
              </View>
            </View>
          )}


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
  groupEffectText: {
    alignSelf: 'stretch',
    flexShrink: 1,
    flexWrap: 'wrap',
    fontSize: 10,
    lineHeight: 14,
    color: '#6B7280',
    marginTop: 3,
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
    flexWrap: 'wrap',
    gap: 8,
  },
  emptyColumnText: {
    fontSize: 12,
    color: '#9CA3AF',
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
    marginBottom: 4,
  },
  productComposition: {
    fontSize: 9,
    lineHeight: 12,
    color: '#4B5563',
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
    flexShrink: 1,
    flexWrap: 'wrap',
    fontSize: 13,
    fontWeight: '600',
    color: '#92400E',
  },
  categoryComparison: {
    flexDirection: 'row',
  },
  categoryColumn: {
    flex: 1,
    minWidth: 0,
    padding: 10,
  },
  categorySubstance: {
    flexShrink: 1,
    flexWrap: 'wrap',
    fontSize: 13,
    color: '#374151',
    marginBottom: 4,
  },
  uniqueBlock: {
    flex: 1,
    minWidth: 0,
    marginBottom: 12,
  },
  uniqueBlockTitle: {
    flexShrink: 1,
    flexWrap: 'wrap',
    fontSize: 13,
    fontWeight: '500',
    color: '#6B7280',
    marginBottom: 8,
  },
  uniqueSubstance: {
    minWidth: 0,
    padding: 10,
    borderRadius: 8,
    marginBottom: 6,
  },
  metricSubstanceCard: {
    minWidth: 0,
    padding: 8,
    borderRadius: 8,
    marginBottom: 6,
  },
  uniqueSubstanceName: {
    flexShrink: 1,
    flexWrap: 'wrap',
    fontSize: 14,
    fontWeight: '600',
    color: '#111827',
  },
  uniqueSubstanceInfo: {
    flexShrink: 1,
    flexWrap: 'wrap',
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
    flexShrink: 1,
    flexWrap: 'wrap',
    fontSize: 13,
    fontWeight: '700',
    color: '#111827',
    marginBottom: 4,
  },
  groupText: {
    flexShrink: 1,
    flexWrap: 'wrap',
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
    minWidth: 0,
  },
  leftControlCard: {
    backgroundColor: '#EFF6FF',
    borderColor: '#93C5FD',
    borderWidth: 1,
    borderRadius: 10,
    padding: 8,
  },
  rightControlCard: {
    backgroundColor: '#F5F3FF',
    borderColor: '#C4B5FD',
    borderWidth: 1,
    borderRadius: 10,
    padding: 8,
  },
  cropInputContainer: {
    marginTop: 12,
  },
  cropResultRow: {
    flexDirection: 'row',
    gap: 8,
    marginTop: 10,
  },
  cropResultCard: {
    flex: 1,
    minWidth: 0,
    borderRadius: 10,
    padding: 8,
  },
  priceInputLabel: {
    flexShrink: 1,
    flexWrap: 'wrap',
    fontSize: 12,
    color: '#6B7280',
    marginBottom: 6,
    marginTop: 4,
  },
  inputHint: {
    fontSize: 10,
    lineHeight: 14,
    color: '#6B7280',
    marginTop: 4,
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
  neutralEconomyText: {
    fontSize: 12,
    color: '#6B7280',
    marginTop: 10,
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
