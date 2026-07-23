import React, { useState, useEffect, useMemo } from 'react';
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
import { useLocalSearchParams, useRouter } from 'expo-router';
import axios from 'axios';
import { AmbientBackground } from '../src/components/AmbientBackground';
import { BrandLogo } from '../src/components/BrandLogo';
import { useHerbicideStore } from '../src/store/herbicideStore';
import { RetryErrorCard } from '../src/components/RetryErrorCard';
import { colors, shadows } from '../src/theme/colors';

const API_URL = process.env.EXPO_PUBLIC_BACKEND_URL || '';

interface Substance {
  name: string;
  comparison_key?: string;
  concentration: number | null;
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
  left_name?: string;
  right_name?: string;
  comparison_key?: string;
  left_concentration: number | null;
  left_unit: string;
  right_concentration: number | null;
  right_unit: string;
  left_per_ha: number | null;
  right_per_ha: number | null;
}

interface SimilarCategory {
  category: string;
  left_substances: { name: string; concentration: number | null; unit: string }[];
  right_substances: { name: string; concentration: number | null; unit: string }[];
}

interface ProductInfo {
  product_key: string;
  product_name: string;
  formulation: string | null;
  active_substances_raw: string | null;
  display_manufacturer: string | null;
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
  comparison_key?: string;
  concentration: number | null;
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

interface ComparisonSummaryItem {
  status: 'winner' | 'tie' | 'none' | 'unavailable' | 'different_composition' | 'mixed';
  winner_side: 'left' | 'right' | null;
  winner_name: string | null;
  message: string;
  note?: string;
}

interface ComparisonSummary {
  cost: ComparisonSummaryItem;
  active_substances: ComparisonSummaryItem & { same_active_substance_set?: boolean };
  absolute: ComparisonSummaryItem;
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
  comparison_summary?: ComparisonSummary;
  crop_registration?: CropRegistration;
}

export default function CompareScreen() {
  const router = useRouter();
  const routeParams = useLocalSearchParams<{
    left_key?: string | string[];
    right_key?: string | string[];
  }>();
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

  const getRouteParamValue = (value?: string | string[]) => (
    Array.isArray(value) ? value[0] : value
  );

  const selectedProductKeys = useMemo(() => {
    const routeProductKeys = [
      getRouteParamValue(routeParams.left_key),
      getRouteParamValue(routeParams.right_key),
    ];

    return routeProductKeys.every(Boolean)
      ? routeProductKeys as string[]
      : selectedForCompare;
  }, [routeParams.left_key, routeParams.right_key, selectedForCompare]);

  const hasComparableProducts = selectedProductKeys.length === 2;
  const leftSelectedProductKey = selectedProductKeys[0];
  const rightSelectedProductKey = selectedProductKeys[1];

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
    if (!substance || !product?.rate_used || substance.concentration === null || substance.concentration === undefined) return null;
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
    if (!hasComparableProducts) {
      setLoading(false);
      setPriceLoading(false);
      setError('Выберите два препарата для сравнения');
      return;
    }

    if (withInputs) {
      setPriceLoading(true);
    } else {
      setLoading(true);
    }
    setError(null);

    try {
      const body: any = {
        left_key: leftSelectedProductKey,
        right_key: rightSelectedProductKey,
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

      const response = await axios.post(`${API_URL}/api/herbicides/compare-advanced`, body);
      setCompareData(response.data);
    } catch (err) {
      console.error('Compare failed:', err);
      setError('Не удалось загрузить данные');
    } finally {
      setLoading(false);
      setPriceLoading(false);
    }
  };

  useEffect(() => {
    fetchCompareData();
  }, [leftSelectedProductKey, rightSelectedProductKey, hasComparableProducts]);

  const handlePriceCalculation = () => {
    fetchCompareData(true);
  };

  const hasLeftPrice = parseOptionalNumber(leftPrice) !== undefined;
  const hasRightPrice = parseOptionalNumber(rightPrice) !== undefined;
  const hasAnyPrice = hasLeftPrice || hasRightPrice;

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

  const formatConcentration = (value: number | null | undefined, unit?: string | null) => {
    const formattedValue = formatNumber(value);
    return formattedValue === '—' ? formattedValue : unit ? `${formattedValue} ${unit}` : formattedValue;
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

  const getSubstanceKey = (name: string, comparisonKey?: string | null) => (
    comparisonKey?.trim() || name.trim().toLowerCase()
  );

  const namesMatch = (
    leftName?: string | null,
    rightName?: string | null,
    leftComparisonKey?: string | null,
    rightComparisonKey?: string | null,
  ) => {
    const leftKey = getSubstanceKey(leftName ?? '', leftComparisonKey);
    const rightKey = getSubstanceKey(rightName ?? '', rightComparisonKey);
    return Boolean(leftKey && rightKey && (leftKey === rightKey || leftKey.includes(rightKey) || rightKey.includes(leftKey)));
  };

  const getSubstanceDetails = (product: ProductInfo, substanceName: string, comparisonKey?: string) => {
    return product.substances.find(item => namesMatch(item.name, substanceName, item.comparison_key, comparisonKey));
  };

  const getSubstanceCost = (side: 'left' | 'right', substanceName: string, comparisonKey?: string) => {
    const costs = side === 'left'
      ? compareData?.price_analysis?.left_substances_cost ?? compareData?.price_analysis?.substances_cost.filter(item => item.side === 'left')
      : compareData?.price_analysis?.right_substances_cost ?? compareData?.price_analysis?.substances_cost.filter(item => item.side === 'right');
    return costs?.find(item => namesMatch(
      item.substance_name || item.name,
      substanceName,
      item.comparison_key,
      comparisonKey,
    ));
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
    const cost = getSubstanceCost(side, substance.name, substance.comparison_key);
    const product = side === 'left' ? compareData?.left : compareData?.right;
    const showCost = shouldShowSubstanceCost(cost, side === 'left' ? hasLeftPrice : hasRightPrice);
    const calculatedPerHa = perHa ?? substance.per_ha ?? calculateActiveAmount(substance, product);

    return (
      <View style={[styles.metricSubstanceCard, side === 'left' ? styles.leftColumnCard : styles.rightColumnCard]}>
        <Text style={styles.uniqueSubstanceName}>{substance.name}</Text>
        <Text style={styles.uniqueSubstanceInfo}>Концентрация: {formatConcentration(substance.concentration, substance.unit)}</Text>
        <Text style={styles.uniqueSubstanceInfo}>Норма: {formatRate(product?.rate_used, product?.rate_unit)}</Text>
        <Text style={styles.uniqueSubstanceInfo}>ДВ на гектар: {formatNumber(calculatedPerHa)} г/га</Text>
        {showCost && (
          <Text style={styles.uniqueSubstanceInfo}>Затраты на 1 г ДВ: {formatNumber(cost?.estimated_cost_per_gram)} ₽/г</Text>
        )}
        <Text style={styles.uniqueSubstanceInfo}>Группа устойчивости: {renderGroupLabel(substance)}</Text>
        {renderEffectSummary(substance.effect_summary)}
      </View>
    );
  };

  const renderUniqueSubstance = (sub: Substance & { category: string; per_ha: number | null }, side: 'left' | 'right') => {
    const cost = getSubstanceCost(side, sub.name, sub.comparison_key);
    const product = side === 'left' ? compareData?.left : compareData?.right;
    const showCost = shouldShowSubstanceCost(cost, side === 'left' ? hasLeftPrice : hasRightPrice);
    const calculatedPerHa = sub.per_ha ?? calculateActiveAmount(sub, product);

    return (
      <View style={[styles.uniqueSubstance, side === 'left' ? styles.leftColumnCard : styles.rightColumnCard]}>
        <Text style={styles.uniqueSubstanceName}>{sub.name}</Text>
        <Text style={styles.uniqueSubstanceInfo}>Концентрация: {formatConcentration(sub.concentration, sub.unit)}</Text>
        <Text style={styles.uniqueSubstanceInfo}>ДВ на гектар: {formatNumber(calculatedPerHa)} г/га</Text>
        {showCost && (
          <Text style={styles.uniqueSubstanceInfo}>Затраты на 1 г ДВ: {formatNumber(cost?.estimated_cost_per_gram)} ₽/г</Text>
        )}
        <Text style={styles.uniqueSubstanceInfo}>Группа устойчивости: {renderGroupLabel(sub)}</Text>
        {renderEffectSummary(sub.effect_summary)}
        <Text style={styles.uniqueSubstanceInfo}>Прямое сопоставление не найдено.</Text>
      </View>
    );
  };

  if (loading) {
    return (
      <SafeAreaView style={styles.container} edges={['top']}>
        <AmbientBackground />
        <View style={styles.header}>
          <TouchableOpacity style={styles.backButton} onPress={handleBack}>
            <Ionicons name="arrow-back" size={22} color={colors.text} />
          </TouchableOpacity>
          <BrandLogo compact />
          <View style={{ width: 40 }} />
        </View>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={colors.primaryBright} />
          <Text style={styles.loadingText}>Анализ действующих веществ...</Text>
        </View>
      </SafeAreaView>
    );
  }

  if (error || !compareData) {
    return (
      <SafeAreaView style={styles.container} edges={['top']}>
        <AmbientBackground />
        <View style={styles.header}>
          <TouchableOpacity style={styles.backButton} onPress={handleBack}>
            <Ionicons name="arrow-back" size={22} color={colors.text} />
          </TouchableOpacity>
          <BrandLogo compact />
          <View style={{ width: 40 }} />
        </View>
        <View style={styles.errorContainer}>
          <RetryErrorCard onRetry={() => fetchCompareData()} />
        </View>
      </SafeAreaView>
    );
  }

  const { left, right, analysis, group_analysis, price_analysis, comparison_summary, crop_registration } = compareData;
  const hasCropInput = crop.trim().length > 0;
  const hasLeftComposition = (left.active_substances_raw?.trim().length ?? 0) > 0;
  const leftDisplayManufacturer = left.display_manufacturer?.trim() || 'Производитель не указан';
  const rightDisplayManufacturer = right.display_manufacturer?.trim() || 'Производитель не указан';
  const hasRightComposition = (right.active_substances_raw?.trim().length ?? 0) > 0;
  const hasLeftFormulation = (left.formulation?.trim().length ?? 0) > 0;
  const hasRightFormulation = (right.formulation?.trim().length ?? 0) > 0;
  const hasPriceResultValues = price_analysis !== null
    && (price_analysis.left_price_per_unit !== null || price_analysis.right_price_per_unit !== null);
  const usedLeftSubstances = new Set(analysis.identical_substances.map(item => getSubstanceKey(item.left_name ?? item.name, item.comparison_key)));
  const usedRightSubstances = new Set(analysis.identical_substances.map(item => getSubstanceKey(item.right_name ?? item.name, item.comparison_key)));
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
      <AmbientBackground />
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={{ flex: 1 }}
      >
        <View style={styles.header}>
          <TouchableOpacity style={styles.backButton} onPress={handleBack}>
            <Ionicons name="arrow-back" size={22} color={colors.text} />
          </TouchableOpacity>
          <View style={styles.headerCenter}>
            <BrandLogo compact />
            <Text style={styles.headerSubtitle}>Сравнение препаратов</Text>
          </View>
          <View style={{ width: 40 }} />
        </View>

        <ScrollView style={styles.content} showsVerticalScrollIndicator={false}>
          {/* Product Headers */}
          <View style={styles.productHeaders}>
            <View style={[styles.productHeaderLeft, styles.leftHeaderAccent]}>
              <Text style={styles.productSideLabel}>Препарат А</Text>
              <Text style={styles.productHeaderName} numberOfLines={2}>{left.product_name}</Text>
              <Text style={styles.productComposition} numberOfLines={2}>Производитель: {leftDisplayManufacturer}</Text>
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
              <Text style={styles.productComposition} numberOfLines={2}>Производитель: {rightDisplayManufacturer}</Text>
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
              <Ionicons name="calculator" size={20} color={colors.primaryBright} />
              <Text style={styles.sectionTitle}>Параметры расчёта</Text>
            </View>
            <Text style={styles.priceHint}>Если норму не заполнить, берётся максимальная зарегистрированная норма. Цена нужна только для экономики.</Text>

            <View style={styles.priceInputRow}>
              <View style={[styles.priceInputContainer, styles.leftControlCard]}>
                <Text style={[styles.priceInputLabel, styles.leftAccentText]}>Норма: {left.product_name}</Text>
                <TextInput
                  style={styles.priceInput}
                  placeholder={getManualRatePlaceholder('Напр. 0,8', left.rate_unit)}
                  placeholderTextColor={colors.textMuted}
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
                  placeholderTextColor={colors.textMuted}
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
                  placeholderTextColor={colors.textMuted}
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
                  placeholderTextColor={colors.textMuted}
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
                placeholderTextColor={colors.textMuted}
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
                <ActivityIndicator size="small" color={colors.white} />
              ) : (
                <>
                  <Ionicons name="calculator" size={18} color={colors.white} />
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
                  <Text style={styles.priceResultLabel}>Стоимость обработки</Text>
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
                <Text style={styles.summaryLabel}>ДВ на гектар, г</Text>
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
                <Ionicons name="checkmark-circle" size={20} color={colors.success} />
                <Text style={styles.sectionTitle}>Одинаковые действующие вещества</Text>
              </View>
              <Text style={styles.costMetricNote}>Полная стоимость обработки делится на количество этого ДВ на гектар. Дополнительные компоненты входят в стоимость препарата.</Text>
              {analysis.identical_substances.map((sub, idx) => {
                const leftName = sub.left_name ?? sub.name;
                const rightName = sub.right_name ?? sub.name;
                const leftDetails = getSubstanceDetails(left, leftName, sub.comparison_key);
                const rightDetails = getSubstanceDetails(right, rightName, sub.comparison_key);
                const leftCost = getSubstanceCost('left', leftName, sub.comparison_key);
                const rightCost = getSubstanceCost('right', rightName, sub.comparison_key);
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
                        <Text style={styles.substanceConc}>{formatConcentration(sub.left_concentration, sub.left_unit)}</Text>
                        <Text style={styles.comparisonTag}>{getValueLabel(sub.left_concentration, sub.right_concentration, 'left')}</Text>
                        <Text style={styles.valueLabel}>ДВ на гектар</Text>
                        <Text style={styles.substancePerHa}>{formatNumber(sub.left_per_ha)} г/га</Text>
                        {showLeftCost && (
                          <>
                            <Text style={styles.valueLabel}>Затраты на 1 г ДВ</Text>
                            <Text style={styles.substancePerHa}>{formatNumber(leftCost?.estimated_cost_per_gram)} ₽/г</Text>
                          </>
                        )}
                        <Text style={styles.valueLabel}>Группа устойчивости</Text>
                        <Text style={styles.groupInlineText}>{renderGroupLabel(leftDetails)}</Text>
                        {renderEffectSummary(leftDetails?.effect_summary)}
                      </View>
                      <View style={[styles.substanceValue, styles.rightColumnCard, getValueTone(sub.left_concentration, sub.right_concentration, 'right')]}>
                        <Text style={styles.valueLabel}>Концентрация</Text>
                        <Text style={styles.substanceConc}>{formatConcentration(sub.right_concentration, sub.right_unit)}</Text>
                        <Text style={styles.comparisonTag}>{getValueLabel(sub.left_concentration, sub.right_concentration, 'right')}</Text>
                        <Text style={styles.valueLabel}>ДВ на гектар</Text>
                        <Text style={styles.substancePerHa}>{formatNumber(sub.right_per_ha)} г/га</Text>
                        {showRightCost && (
                          <>
                            <Text style={styles.valueLabel}>Затраты на 1 г ДВ</Text>
                            <Text style={styles.substancePerHa}>{formatNumber(rightCost?.estimated_cost_per_gram)} ₽/г</Text>
                          </>
                        )}
                        <Text style={styles.valueLabel}>Группа устойчивости</Text>
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
                <Ionicons name="shield-checkmark" size={20} color={colors.success} />
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
                <Ionicons name="information-circle" size={20} color={colors.textSecondary} />
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
                <Ionicons name="add-circle" size={20} color={colors.primaryBright} />
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

          {comparison_summary && (
            <View style={styles.section}>
              <View style={styles.sectionHeader}>
                <Ionicons name="trophy-outline" size={20} color={colors.primaryBright} />
                <Text style={styles.sectionTitle}>Итог сравнения</Text>
              </View>

              <View style={styles.conclusionCard}>
                <Text style={styles.conclusionLabel}>По стоимости обработки</Text>
                <Text style={styles.conclusionText}>{comparison_summary.cost.message}</Text>
              </View>

              <View style={styles.conclusionCard}>
                <Text style={styles.conclusionLabel}>По действующим веществам</Text>
                <Text style={styles.conclusionText}>{comparison_summary.active_substances.message}</Text>
                {comparison_summary.active_substances.note ? (
                  <Text style={styles.conclusionNote}>{comparison_summary.active_substances.note}</Text>
                ) : null}
              </View>

              <View style={[
                styles.absoluteConclusionCard,
                comparison_summary.absolute.status === 'winner' && styles.absoluteConclusionWinner,
              ]}>
                <Ionicons
                  name={comparison_summary.absolute.status === 'winner' ? 'trophy' : 'information-circle-outline'}
                  size={22}
                  color={comparison_summary.absolute.status === 'winner' ? colors.success : colors.textSecondary}
                />
                <View style={styles.absoluteConclusionContent}>
                  <Text style={styles.absoluteConclusionLabel}>Общий итог</Text>
                  <Text style={styles.absoluteConclusionText}>{comparison_summary.absolute.message}</Text>
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
    backgroundColor: colors.background,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: 'rgba(7,10,28,0.9)',
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
  headerCenter: { alignItems: 'center' },
  headerSubtitle: { color: colors.textMuted, fontSize: 9, marginTop: -1 },
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
    color: colors.white,
    fontSize: 14,
    fontWeight: '600',
  },
  productHeaders: {
    flexDirection: 'row',
    backgroundColor: colors.surface,
    padding: 16,
    margin: 16,
    borderRadius: 18,
    borderWidth: 1,
    borderColor: colors.border,
    ...shadows.card,
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
    color: colors.textSecondary,
  },
  leftHeaderAccent: {
    backgroundColor: '#182140',
    borderColor: colors.cyan,
  },
  rightHeaderAccent: {
    backgroundColor: colors.primarySoft,
    borderColor: colors.primaryBright,
  },
  leftColumnCard: {
    backgroundColor: '#182140',
    borderColor: '#37638A',
    borderWidth: 1,
  },
  rightColumnCard: {
    backgroundColor: colors.primarySoft,
    borderColor: '#51468E',
    borderWidth: 1,
  },
  leftAccentText: {
    color: colors.cyan,
  },
  rightAccentText: {
    color: colors.primaryBright,
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
    color: colors.text,
  },
  comparisonTag: {
    marginTop: 2,
    fontSize: 10,
    fontWeight: '700',
    color: colors.textSecondary,
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
    backgroundColor: '#1C2B4D',
  },
  columnLabelRight: {
    backgroundColor: colors.primarySoft,
  },
  columnLabelText: {
    fontSize: 11,
    fontWeight: '800',
  },
  columnLabelName: {
    fontSize: 10,
    color: colors.textSecondary,
    marginTop: 2,
  },
  valueLabel: {
    fontSize: 10,
    fontWeight: '700',
    color: colors.textMuted,
    marginTop: 6,
    marginBottom: 2,
  },
  groupInlineText: {
    fontSize: 11,
    lineHeight: 15,
    color: colors.textSecondary,
  },
  groupEffectText: {
    alignSelf: 'stretch',
    flexShrink: 1,
    flexWrap: 'wrap',
    fontSize: 10,
    lineHeight: 14,
    color: colors.textMuted,
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
    color: colors.success,
    marginTop: 8,
  },
  neutralMessage: {
    fontSize: 13,
    color: colors.textSecondary,
    lineHeight: 19,
  },
  uniqueColumns: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  emptyColumnText: {
    fontSize: 12,
    color: colors.textMuted,
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
    color: colors.text,
    textAlign: 'center',
    marginBottom: 4,
  },
  productComposition: {
    fontSize: 9,
    lineHeight: 12,
    color: colors.textSecondary,
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
    color: colors.textMuted,
  },
  formulationBadge: {
    backgroundColor: colors.surfaceSoft,
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 4,
    marginBottom: 8,
  },
  formulationText: {
    fontSize: 12,
    color: colors.textSecondary,
    fontWeight: '500',
  },
  statusBadgeMini: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 4,
  },
  statusActiveMini: {
    backgroundColor: colors.successSoft,
  },
  statusInactiveMini: {
    backgroundColor: colors.dangerSoft,
  },
  statusTextMini: {
    fontSize: 11,
    fontWeight: '600',
  },
  statusTextActiveMini: {
    color: colors.success,
  },
  statusTextInactiveMini: {
    color: colors.danger,
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
  registrationLine: {
    color: colors.textSecondary,
    fontSize: 11,
    lineHeight: 16,
  },
  summarySection: {
    backgroundColor: colors.surface,
    marginHorizontal: 16,
    borderRadius: 16,
    padding: 16,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: colors.border,
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
    color: colors.textSecondary,
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
    backgroundColor: '#1C2B4D',
    color: colors.cyan,
  },
  rightValue: {
    backgroundColor: colors.primarySoft,
    color: colors.primaryBright,
  },
  higherValue: {
    backgroundColor: colors.successSoft,
    borderColor: colors.success,
  },
  lowerValue: {
    opacity: 1,
  },
  equalValue: {
    backgroundColor: colors.surfaceSoft,
    borderColor: colors.textMuted,
  },
  section: {
    backgroundColor: colors.surface,
    marginHorizontal: 16,
    borderRadius: 16,
    padding: 16,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: colors.border,
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
    color: colors.text,
  },
  costMetricNote: {
    marginBottom: 12,
    fontSize: 12,
    lineHeight: 17,
    color: colors.textSecondary,
  },
  conclusionCard: {
    padding: 12,
    marginBottom: 10,
    borderRadius: 12,
    backgroundColor: colors.backgroundRaised,
    borderWidth: 1,
    borderColor: colors.border,
  },
  conclusionLabel: {
    marginBottom: 5,
    fontSize: 11,
    fontWeight: '700',
    color: colors.primaryBright,
  },
  conclusionText: {
    fontSize: 13,
    lineHeight: 18,
    color: colors.text,
  },
  conclusionNote: {
    marginTop: 6,
    fontSize: 10,
    lineHeight: 14,
    color: colors.textMuted,
  },
  absoluteConclusionCard: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 10,
    padding: 13,
    borderRadius: 13,
    backgroundColor: colors.surfaceSoft,
    borderWidth: 1,
    borderColor: colors.borderStrong,
  },
  absoluteConclusionWinner: {
    backgroundColor: colors.successSoft,
    borderColor: colors.success,
  },
  absoluteConclusionContent: {
    flex: 1,
  },
  absoluteConclusionLabel: {
    marginBottom: 4,
    fontSize: 11,
    fontWeight: '800',
    color: colors.textSecondary,
  },
  absoluteConclusionText: {
    fontSize: 13,
    lineHeight: 18,
    fontWeight: '600',
    color: colors.text,
  },
  substanceCard: {
    marginBottom: 12,
    padding: 12,
    backgroundColor: colors.backgroundRaised,
    borderRadius: 12,
  },
  substanceName: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.text,
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
    backgroundColor: '#1C2B4D',
  },
  rightBg: {
    backgroundColor: colors.primarySoft,
  },
  substanceConc: {
    fontSize: 15,
    fontWeight: '700',
    color: colors.text,
  },
  substancePerHa: {
    fontSize: 12,
    color: colors.textSecondary,
    marginTop: 4,
  },
  categoryCard: {
    marginBottom: 12,
    backgroundColor: colors.backgroundRaised,
    borderRadius: 12,
    overflow: 'hidden',
  },
  categoryHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 12,
    backgroundColor: colors.warningSoft,
    gap: 8,
  },
  categoryName: {
    flexShrink: 1,
    flexWrap: 'wrap',
    fontSize: 13,
    fontWeight: '600',
    color: colors.warning,
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
    color: colors.textSecondary,
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
    color: colors.textSecondary,
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
    color: colors.text,
  },
  uniqueSubstanceInfo: {
    flexShrink: 1,
    flexWrap: 'wrap',
    fontSize: 12,
    color: colors.textSecondary,
    marginTop: 4,
  },
  groupCard: {
    padding: 12,
    borderRadius: 10,
    marginBottom: 10,
  },
  groupWarningCard: {
    backgroundColor: colors.warningSoft,
  },
  groupSuccessCard: {
    backgroundColor: colors.successSoft,
  },
  groupUnknownCard: {
    backgroundColor: colors.surfaceSoft,
  },
  groupTitle: {
    flexShrink: 1,
    flexWrap: 'wrap',
    fontSize: 13,
    fontWeight: '700',
    color: colors.text,
    marginBottom: 4,
  },
  groupText: {
    flexShrink: 1,
    flexWrap: 'wrap',
    fontSize: 12,
    color: colors.textSecondary,
    marginTop: 2,
  },
  groupWarningText: {
    fontSize: 12,
    color: colors.warning,
    marginTop: 6,
  },
  groupExplanation: {
    fontSize: 12,
    lineHeight: 18,
    color: colors.textSecondary,
    marginTop: 2,
  },
  priceSection: {
    backgroundColor: colors.surface,
    marginHorizontal: 16,
    borderRadius: 16,
    padding: 16,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: colors.border,
  },
  priceHint: {
    fontSize: 13,
    color: colors.textSecondary,
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
    backgroundColor: '#182140',
    borderColor: '#37638A',
    borderWidth: 1,
    borderRadius: 10,
    padding: 8,
  },
  rightControlCard: {
    backgroundColor: colors.primarySoft,
    borderColor: '#51468E',
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
    color: colors.textSecondary,
    marginBottom: 6,
    marginTop: 4,
  },
  inputHint: {
    fontSize: 10,
    lineHeight: 14,
    color: colors.textMuted,
    marginTop: 4,
  },
  priceInput: {
    backgroundColor: colors.backgroundRaised,
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 16,
    color: colors.text,
    borderWidth: 1,
    borderColor: colors.border,
  },
  calculateButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.primary,
    paddingVertical: 12,
    borderRadius: 8,
    marginTop: 16,
    gap: 8,
  },
  calculateButtonText: {
    color: colors.white,
    fontSize: 14,
    fontWeight: '600',
  },
  neutralEconomyText: {
    fontSize: 12,
    color: colors.textSecondary,
    marginTop: 10,
  },
  priceResults: {
    marginTop: 16,
    paddingTop: 16,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    gap: 12,
  },
  substanceCostBlock: {
    marginTop: 12,
  },
  substanceCostTitle: {
    fontSize: 13,
    fontWeight: '700',
    color: colors.text,
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
    backgroundColor: colors.backgroundRaised,
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
    color: colors.textSecondary,
  },
  priceResultRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  priceResultLabel: {
    fontSize: 13,
    color: colors.textSecondary,
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
