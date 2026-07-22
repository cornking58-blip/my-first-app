import React, { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Keyboard,
  KeyboardAvoidingView,
  Platform,
  RefreshControl,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { FlashList } from '@shopify/flash-list';
import { useRouter } from 'expo-router';
import axios from 'axios';
import { AmbientBackground } from '../../src/components/AmbientBackground';
import { BrandLogo } from '../../src/components/BrandLogo';
import { RetryErrorCard } from '../../src/components/RetryErrorCard';
import { useHerbicideStore } from '../../src/store/herbicideStore';
import { colors, shadows } from '../../src/theme/colors';

const API_URL = process.env.EXPO_PUBLIC_BACKEND_URL || '';

interface SearchResult {
  product_key: string;
  product_name: string;
  formulation: string | null;
  active_substances_raw: string | null;
  manufacturer: string | null;
  display_manufacturer: string | null;
  registration_status: string | null;
  applications_count: number;
}

export default function HomeScreen() {
  const router = useRouter();
  const [searchQuery, setSearchQuery] = useState('');
  const [crop, setCrop] = useState('');
  const [harmfulObject, setHarmfulObject] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [requestError, setRequestError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [onlyActive, setOnlyActive] = useState(false);
  const [showFilters, setShowFilters] = useState(false);
  const [stats, setStats] = useState<{
    total_records: number;
    unique_products: number;
    active_registrations: number;
  } | null>(null);
  const { selectedForCompare, toggleSelection, clearSelection } = useHerbicideStore();

  const fetchStats = async () => {
    try {
      const response = await axios.get(`${API_URL}/api/stats`);
      setStats(response.data);
    } catch (error) {
      console.error('Failed to fetch stats:', error);
      setRequestError('Не удалось загрузить данные');
    }
  };

  const search = async (
    query: string,
    active: boolean,
    cropValue: string,
    harmfulObjectValue: string,
  ) => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (query.trim()) params.append('q', query.trim());
      if (cropValue.trim()) params.append('culture', cropValue.trim());
      if (harmfulObjectValue.trim()) params.append('harmful_object', harmfulObjectValue.trim());
      if (active) params.append('only_active', 'true');
      params.append('limit', '50');

      const response = await axios.get(`${API_URL}/api/herbicides/search?${params.toString()}`);
      setResults(response.data);
      setRequestError(null);
    } catch (error) {
      console.error('Search failed:', error);
      setRequestError('Не удалось загрузить данные');
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStats();
    search('', false, '', '');
  }, []);

  const handleSearch = useCallback(() => {
    Keyboard.dismiss();
    search(searchQuery, onlyActive, crop, harmfulObject);
  }, [searchQuery, onlyActive, crop, harmfulObject]);

  const handleRefresh = async () => {
    setRefreshing(true);
    await Promise.all([fetchStats(), search(searchQuery, onlyActive, crop, harmfulObject)]);
    setRefreshing(false);
  };

  const handleRetry = () => {
    fetchStats();
    search(searchQuery, onlyActive, crop, harmfulObject);
  };

  const toggleActiveFilter = () => {
    const newValue = !onlyActive;
    setOnlyActive(newValue);
    search(searchQuery, newValue, crop, harmfulObject);
  };

  const clearFilters = () => {
    setSearchQuery('');
    setCrop('');
    setHarmfulObject('');
    search('', onlyActive, '', '');
  };

  const openComparison = () => {
    if (selectedForCompare.length !== 2) return;
    router.push({
      pathname: '/compare',
      params: {
        left_key: selectedForCompare[0],
        right_key: selectedForCompare[1],
      },
    });
  };

  const isActive = (status: string | null) => status?.toLowerCase().trim() === 'действует';

  const renderItem = ({ item }: { item: SearchResult }) => {
    const active = isActive(item.registration_status);
    const displayManufacturer = item.display_manufacturer?.trim() || '';
    const shouldShowManufacturer = Boolean(
      displayManufacturer && displayManufacturer !== 'Производитель не указан',
    );
    const isSelected = selectedForCompare.includes(item.product_key);
    const canSelect = selectedForCompare.length < 2 || isSelected;

    return (
      <View style={[styles.card, isSelected && styles.cardSelected]}>
        <TouchableOpacity
          style={styles.cardContent}
          onPress={() => router.push(`/product/${encodeURIComponent(item.product_key)}`)}
          activeOpacity={0.76}
        >
          <View style={styles.cardHeader}>
            <View style={styles.cardTitleRow}>
              <Text style={styles.productName} numberOfLines={1}>{item.product_name}</Text>
              {(item.formulation?.trim().length ?? 0) > 0 ? (
                <View style={styles.formulationBadge}>
                  <Text style={styles.formulationText}>{item.formulation}</Text>
                </View>
              ) : null}
            </View>
            <View style={[styles.statusBadge, active ? styles.statusActive : styles.statusInactive]}>
              <View style={[styles.statusDot, active ? styles.statusDotActive : styles.statusDotInactive]} />
              <Text style={[styles.statusText, active ? styles.statusTextActive : styles.statusTextInactive]}>
                {active ? 'Действует' : 'Не действует'}
              </Text>
            </View>
          </View>

          {(item.active_substances_raw?.trim().length ?? 0) > 0 ? (
            <Text style={styles.substances} numberOfLines={2}>{item.active_substances_raw}</Text>
          ) : null}

          {shouldShowManufacturer ? (
            <View style={styles.manufacturerRow}>
              <Ionicons name="business-outline" size={14} color={colors.textMuted} />
              <Text style={styles.manufacturer} numberOfLines={1}>{displayManufacturer}</Text>
            </View>
          ) : null}
        </TouchableOpacity>

        <View style={styles.cardFooter}>
          <View style={styles.applicationsCount}>
            <Ionicons name="layers-outline" size={14} color={colors.textMuted} />
            <Text style={styles.applicationsText}>{item.applications_count} применений</Text>
          </View>
          <TouchableOpacity
            style={[
              styles.compareSelectButton,
              isSelected && styles.compareSelectButtonActive,
              !canSelect && !isSelected && styles.compareSelectButtonDisabled,
            ]}
            onPress={() => toggleSelection(item.product_key)}
            disabled={!canSelect && !isSelected}
          >
            <Ionicons
              name={isSelected ? 'checkmark-circle' : 'add-circle-outline'}
              size={18}
              color={isSelected ? colors.white : (!canSelect ? colors.textMuted : colors.primaryBright)}
            />
            <Text style={[
              styles.compareSelectText,
              isSelected && styles.compareSelectTextActive,
              !canSelect && !isSelected && styles.compareSelectTextDisabled,
            ]}>
              {isSelected ? 'Выбрано' : 'Сравнить'}
            </Text>
          </TouchableOpacity>
        </View>
      </View>
    );
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <AmbientBackground />
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={styles.flex}
      >
        <View style={styles.hero}>
          <View style={styles.topBar}>
            <View>
              <BrandLogo />
              <Text style={styles.subtitle}>Справочник гербицидов РФ</Text>
            </View>
            <TouchableOpacity style={styles.profileButton} activeOpacity={0.8}>
              <Ionicons name="person-outline" size={21} color={colors.text} />
            </TouchableOpacity>
          </View>

          <View style={styles.welcomeRow}>
            <View>
              <Text style={styles.eyebrow}>УМНЫЙ СПРАВОЧНИК</Text>
              <Text style={styles.welcomeTitle}>Как я могу помочь?</Text>
            </View>
            {stats ? (
              <View style={styles.catalogBadge}>
                <Text style={styles.catalogBadgeValue}>{stats.unique_products}</Text>
                <Text style={styles.catalogBadgeLabel}>препаратов</Text>
              </View>
            ) : null}
          </View>

          <View style={styles.searchInputContainer}>
            <Ionicons name="search-outline" size={21} color={colors.primaryBright} />
            <TextInput
              style={styles.searchInput}
              placeholder="Название, действующее вещество..."
              placeholderTextColor={colors.textMuted}
              value={searchQuery}
              onChangeText={setSearchQuery}
              onSubmitEditing={handleSearch}
              returnKeyType="search"
            />
            {(searchQuery.length > 0 || crop.length > 0 || harmfulObject.length > 0) ? (
              <TouchableOpacity onPress={clearFilters} style={styles.clearSearchButton}>
                <Ionicons name="close" size={18} color={colors.textSecondary} />
              </TouchableOpacity>
            ) : (
              <TouchableOpacity onPress={handleSearch} style={styles.searchSubmitButton}>
                <Ionicons name="arrow-forward" size={19} color={colors.white} />
              </TouchableOpacity>
            )}
          </View>

          <View style={styles.searchToolsRow}>
            <TouchableOpacity style={styles.filtersToggle} onPress={() => setShowFilters(!showFilters)}>
              <Ionicons name="options-outline" size={17} color={colors.textSecondary} />
              <Text style={styles.filtersToggleText}>Расширенный поиск</Text>
              <Ionicons
                name={showFilters ? 'chevron-up' : 'chevron-down'}
                size={16}
                color={colors.textMuted}
              />
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.activeOnlyChip, onlyActive && styles.activeOnlyChipSelected]}
              onPress={toggleActiveFilter}
            >
              <View style={[styles.activeOnlyDot, onlyActive && styles.activeOnlyDotSelected]} />
              <Text style={[styles.activeOnlyText, onlyActive && styles.activeOnlyTextSelected]}>
                Действующие
              </Text>
            </TouchableOpacity>
          </View>

          {showFilters ? (
            <View style={styles.expandedFilters}>
              <TextInput
                style={styles.filterInput}
                placeholder="Культура"
                placeholderTextColor={colors.textMuted}
                value={crop}
                onChangeText={setCrop}
                onSubmitEditing={handleSearch}
              />
              <TextInput
                style={styles.filterInput}
                placeholder="Сорное растение / вредный объект"
                placeholderTextColor={colors.textMuted}
                value={harmfulObject}
                onChangeText={setHarmfulObject}
                onSubmitEditing={handleSearch}
              />
              <TouchableOpacity style={styles.filterSearchButton} onPress={handleSearch}>
                <Text style={styles.filterSearchButtonText}>Показать результаты</Text>
              </TouchableOpacity>
            </View>
          ) : null}

          <View style={styles.quickHeader}>
            <Text style={styles.quickTitle}>Быстрый доступ</Text>
            <Text style={styles.quickCaption}>Основные возможности</Text>
          </View>
          <View style={styles.quickActions}>
            <TouchableOpacity
              style={[styles.quickAction, selectedForCompare.length === 2 && styles.quickActionReady]}
              onPress={openComparison}
              activeOpacity={0.8}
            >
              <View style={styles.quickIcon}>
                <Ionicons name="git-compare-outline" size={22} color={colors.primaryBright} />
              </View>
              <Text style={styles.quickActionTitle}>Сравнить</Text>
              <Text style={styles.quickActionText}>
                {selectedForCompare.length > 0 ? `Выбрано ${selectedForCompare.length} из 2` : 'Два препарата'}
              </Text>
            </TouchableOpacity>

            <TouchableOpacity style={styles.quickAction} activeOpacity={0.8}>
              <View style={styles.quickIcon}>
                <Ionicons name="sparkles-outline" size={22} color={colors.primaryBright} />
              </View>
              <Text style={styles.quickActionTitle}>Спросить AI</Text>
              <Text style={styles.quickActionText}>Умный ответ</Text>
            </TouchableOpacity>

            <TouchableOpacity style={styles.quickAction} activeOpacity={0.8}>
              <View style={styles.quickIcon}>
                <Ionicons name="camera-outline" size={22} color={colors.primaryBright} />
              </View>
              <Text style={styles.quickActionTitle}>Определить</Text>
              <Text style={styles.quickActionText}>Сорняк по фото</Text>
            </TouchableOpacity>
          </View>
        </View>

        {selectedForCompare.length > 0 ? (
          <View style={styles.compareBar}>
            <View style={styles.compareInfo}>
              <View style={styles.compareIconSmall}>
                <Ionicons name="git-compare-outline" size={17} color={colors.primaryBright} />
              </View>
              <View>
                <Text style={styles.compareText}>Сравнение · {selectedForCompare.length}/2</Text>
                <TouchableOpacity onPress={clearSelection}>
                  <Text style={styles.clearText}>Очистить выбор</Text>
                </TouchableOpacity>
              </View>
            </View>
            {selectedForCompare.length === 2 ? (
              <TouchableOpacity style={styles.compareButton} onPress={openComparison}>
                <Text style={styles.compareButtonText}>Открыть</Text>
                <Ionicons name="arrow-forward" size={17} color={colors.white} />
              </TouchableOpacity>
            ) : (
              <Text style={styles.compareHint}>Выберите ещё один</Text>
            )}
          </View>
        ) : null}

        <View style={styles.resultsContainer}>
          <View style={styles.resultsHeader}>
            <Text style={styles.resultsTitle}>Каталог препаратов</Text>
            <Text style={styles.resultsCount}>{results.length} найдено</Text>
          </View>
          {loading ? (
            <View style={styles.loadingContainer}>
              <ActivityIndicator size="large" color={colors.primaryBright} />
              <Text style={styles.loadingText}>Загружаем препараты...</Text>
            </View>
          ) : requestError ? (
            <RetryErrorCard onRetry={handleRetry} compact />
          ) : (
            <FlashList
              data={results}
              renderItem={renderItem}
              keyExtractor={(item) => item.product_key}
              contentContainerStyle={styles.listContent}
              refreshControl={(
                <RefreshControl
                  refreshing={refreshing}
                  onRefresh={handleRefresh}
                  tintColor={colors.primaryBright}
                />
              )}
              ListEmptyComponent={(
                <View style={styles.emptyContainer}>
                  <Ionicons name="leaf-outline" size={52} color={colors.borderStrong} />
                  <Text style={styles.emptyTitle}>Ничего не найдено</Text>
                  <Text style={styles.emptyText}>Попробуйте изменить запрос</Text>
                </View>
              )}
            />
          )}
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  flex: { flex: 1 },
  hero: {
    paddingHorizontal: 18,
    paddingTop: 10,
    paddingBottom: 14,
    backgroundColor: 'rgba(7,10,28,0.74)',
  },
  topBar: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  subtitle: { color: colors.textSecondary, fontSize: 12, marginTop: -2 },
  profileButton: {
    width: 43,
    height: 43,
    borderRadius: 15,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.surfaceElevated,
    borderWidth: 1,
    borderColor: colors.border,
  },
  welcomeRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-end',
    marginTop: 18,
    marginBottom: 13,
  },
  eyebrow: { color: colors.primaryBright, fontSize: 10, fontWeight: '800', letterSpacing: 1.3 },
  welcomeTitle: { color: colors.text, fontSize: 24, fontWeight: '700', marginTop: 4, letterSpacing: -0.5 },
  catalogBadge: { alignItems: 'flex-end', paddingBottom: 1 },
  catalogBadgeValue: { color: colors.text, fontSize: 18, fontWeight: '800' },
  catalogBadgeLabel: { color: colors.textMuted, fontSize: 10, marginTop: 1 },
  searchInputContainer: {
    height: 54,
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surfaceElevated,
    borderRadius: 17,
    paddingLeft: 15,
    paddingRight: 8,
    borderWidth: 1,
    borderColor: colors.borderStrong,
    ...shadows.card,
  },
  searchInput: { flex: 1, color: colors.text, fontSize: 15, marginLeft: 10, paddingVertical: 0 },
  searchSubmitButton: {
    width: 38,
    height: 38,
    borderRadius: 13,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.primary,
    ...shadows.glow,
  },
  clearSearchButton: {
    width: 36,
    height: 36,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.surfaceSoft,
  },
  searchToolsRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginTop: 9,
  },
  filtersToggle: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingVertical: 5 },
  filtersToggleText: { color: colors.textSecondary, fontSize: 12, fontWeight: '600' },
  activeOnlyChip: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 10,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
  },
  activeOnlyChipSelected: { backgroundColor: colors.successSoft, borderColor: colors.success },
  activeOnlyDot: { width: 6, height: 6, borderRadius: 3, backgroundColor: colors.textMuted, marginRight: 6 },
  activeOnlyDotSelected: { backgroundColor: colors.success },
  activeOnlyText: { color: colors.textSecondary, fontSize: 11, fontWeight: '600' },
  activeOnlyTextSelected: { color: colors.success },
  expandedFilters: {
    marginTop: 10,
    padding: 11,
    borderRadius: 15,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    gap: 8,
  },
  filterInput: {
    height: 42,
    borderRadius: 11,
    paddingHorizontal: 12,
    fontSize: 13,
    color: colors.text,
    backgroundColor: colors.backgroundRaised,
    borderWidth: 1,
    borderColor: colors.border,
  },
  filterSearchButton: { height: 40, borderRadius: 11, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.primary },
  filterSearchButtonText: { color: colors.white, fontSize: 13, fontWeight: '700' },
  quickHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: 13, marginBottom: 9 },
  quickTitle: { color: colors.text, fontSize: 14, fontWeight: '700' },
  quickCaption: { color: colors.textMuted, fontSize: 10 },
  quickActions: { flexDirection: 'row', gap: 9 },
  quickAction: {
    flex: 1,
    minWidth: 0,
    minHeight: 104,
    borderRadius: 16,
    padding: 10,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
  },
  quickActionReady: { borderColor: colors.primaryBright, backgroundColor: colors.primarySoft },
  quickIcon: {
    width: 37,
    height: 37,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.primarySoft,
    borderWidth: 1,
    borderColor: '#493D87',
    marginBottom: 8,
  },
  quickActionTitle: { color: colors.text, fontSize: 12, fontWeight: '700' },
  quickActionText: { color: colors.textMuted, fontSize: 10, lineHeight: 13, marginTop: 3 },
  compareBar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginHorizontal: 18,
    marginBottom: 6,
    padding: 10,
    borderRadius: 14,
    backgroundColor: colors.primarySoft,
    borderWidth: 1,
    borderColor: '#4C408C',
  },
  compareInfo: { flexDirection: 'row', alignItems: 'center' },
  compareIconSmall: { width: 34, height: 34, borderRadius: 11, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.surfaceElevated, marginRight: 9 },
  compareText: { color: colors.text, fontSize: 12, fontWeight: '700' },
  clearText: { color: colors.textSecondary, fontSize: 10, marginTop: 2 },
  compareButton: { flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: colors.primary, borderRadius: 11, paddingHorizontal: 13, paddingVertical: 9 },
  compareButtonText: { color: colors.white, fontSize: 12, fontWeight: '700' },
  compareHint: { color: colors.textSecondary, fontSize: 11 },
  resultsContainer: { flex: 1, minHeight: 0 },
  resultsHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingHorizontal: 18, paddingTop: 9, paddingBottom: 7 },
  resultsTitle: { color: colors.text, fontSize: 15, fontWeight: '700' },
  resultsCount: { color: colors.textMuted, fontSize: 11 },
  listContent: { paddingHorizontal: 18, paddingBottom: 20 },
  card: {
    backgroundColor: colors.surface,
    borderRadius: 16,
    padding: 14,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: colors.border,
  },
  cardSelected: { borderColor: colors.primaryBright, backgroundColor: colors.primarySoft },
  cardContent: { flex: 1 },
  cardHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 },
  cardTitleRow: { flex: 1, flexDirection: 'row', alignItems: 'center', marginRight: 8 },
  productName: { color: colors.text, fontSize: 16, fontWeight: '700', flexShrink: 1 },
  formulationBadge: { backgroundColor: colors.surfaceSoft, paddingHorizontal: 7, paddingVertical: 3, borderRadius: 6, marginLeft: 7 },
  formulationText: { color: colors.textSecondary, fontSize: 10, fontWeight: '600' },
  statusBadge: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 8, paddingVertical: 5, borderRadius: 8 },
  statusActive: { backgroundColor: colors.successSoft },
  statusInactive: { backgroundColor: colors.dangerSoft },
  statusDot: { width: 6, height: 6, borderRadius: 3, marginRight: 5 },
  statusDotActive: { backgroundColor: colors.success },
  statusDotInactive: { backgroundColor: colors.danger },
  statusText: { fontSize: 10, fontWeight: '700' },
  statusTextActive: { color: colors.success },
  statusTextInactive: { color: colors.danger },
  substances: { color: colors.textSecondary, fontSize: 13, lineHeight: 19, marginBottom: 8 },
  manufacturerRow: { flexDirection: 'row', alignItems: 'center', marginBottom: 7 },
  manufacturer: { color: colors.textMuted, fontSize: 12, marginLeft: 6, flex: 1 },
  cardFooter: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingTop: 9, borderTopWidth: 1, borderTopColor: colors.border },
  applicationsCount: { flexDirection: 'row', alignItems: 'center' },
  applicationsText: { color: colors.textMuted, fontSize: 11, marginLeft: 6 },
  compareSelectButton: { flexDirection: 'row', alignItems: 'center', paddingVertical: 6, paddingHorizontal: 10, borderRadius: 9, backgroundColor: colors.primarySoft, borderWidth: 1, borderColor: '#4A3E89' },
  compareSelectButtonActive: { backgroundColor: colors.primary, borderColor: colors.primary },
  compareSelectButtonDisabled: { backgroundColor: colors.surfaceSoft, borderColor: colors.border },
  compareSelectText: { color: colors.primaryBright, fontSize: 11, fontWeight: '700', marginLeft: 4 },
  compareSelectTextActive: { color: colors.white },
  compareSelectTextDisabled: { color: colors.textMuted },
  loadingContainer: { flex: 1, justifyContent: 'center', alignItems: 'center', paddingVertical: 42 },
  loadingText: { color: colors.textSecondary, fontSize: 13, marginTop: 12 },
  emptyContainer: { flex: 1, justifyContent: 'center', alignItems: 'center', paddingVertical: 45 },
  emptyTitle: { color: colors.text, fontSize: 17, fontWeight: '700', marginTop: 14 },
  emptyText: { color: colors.textMuted, fontSize: 13, marginTop: 4 },
});
