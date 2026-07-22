import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  TextInput,
  StyleSheet,
  TouchableOpacity,
  ActivityIndicator,
  RefreshControl,
  KeyboardAvoidingView,
  Platform,
  Keyboard,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { FlashList } from '@shopify/flash-list';
import { useRouter } from 'expo-router';
import axios from 'axios';
import { useHerbicideStore } from '../../src/store/herbicideStore';
import { RetryErrorCard } from '../../src/components/RetryErrorCard';

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

export default function FungicidesScreen() {
  const router = useRouter();
  const [searchQuery, setSearchQuery] = useState('');
  const [crop, setCrop] = useState('');
  const [harmfulObject, setHarmfulObject] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [requestError, setRequestError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [onlyActive, setOnlyActive] = useState(false);
  const [stats, setStats] = useState<{ total_records: number; unique_products: number; active_registrations: number } | null>(null);
  const { selectedFungicidesForCompare, toggleFungicideSelection, clearFungicideSelection } = useHerbicideStore();

  const fetchStats = async () => {
    try {
      const response = await axios.get(`${API_URL}/api/stats`);
      if (response.data.fungicides) {
        setStats(response.data.fungicides);
      }
    } catch (error) {
      console.error('Failed to fetch stats:', error);
      setRequestError('Не удалось загрузить данные');
    }
  };

  const search = async (query: string, active: boolean, cropValue: string, harmfulObjectValue: string) => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (query.trim()) params.append('q', query.trim());
      if (cropValue.trim()) params.append('culture', cropValue.trim());
      if (harmfulObjectValue.trim()) params.append('harmful_object', harmfulObjectValue.trim());
      if (active) params.append('only_active', 'true');
      params.append('limit', '50');

      const response = await axios.get(`${API_URL}/api/fungicides/search?${params.toString()}`);
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

  const isActive = (status: string | null) => {
    return status?.toLowerCase().trim() === 'действует';
  };

  const renderItem = ({ item }: { item: SearchResult }) => {
    const active = isActive(item.registration_status);
    const displayManufacturer = item.display_manufacturer?.trim() || '';
    const shouldShowManufacturer = Boolean(displayManufacturer && displayManufacturer !== 'Производитель не указан');
    const isSelected = selectedFungicidesForCompare.includes(item.product_key);
    const canSelect = selectedFungicidesForCompare.length < 2 || isSelected;
    
    return (
      <View style={[styles.card, isSelected && styles.cardSelected]}>
        <TouchableOpacity
          style={styles.cardContent}
          onPress={() => router.push(`/fungicide-product/${encodeURIComponent(item.product_key)}`)}
          activeOpacity={0.7}
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
                {active ? 'Действует' : 'Не действует'}
              </Text>
            </View>
          </View>

          {(item.active_substances_raw?.trim().length ?? 0) > 0 ? (
            <Text style={styles.substances} numberOfLines={2}>
              {item.active_substances_raw}
            </Text>
          ) : null}

          {shouldShowManufacturer ? (
            <View style={styles.manufacturerRow}>
              <Ionicons name="business-outline" size={14} color="#9CA3AF" />
              <Text style={styles.manufacturer} numberOfLines={1}>{displayManufacturer}</Text>
            </View>
          ) : null}
        </TouchableOpacity>

        <View style={styles.cardFooter}>
          <View style={styles.applicationsCount}>
            <Ionicons name="layers-outline" size={14} color="#6B7280" />
            <Text style={styles.applicationsText}>{item.applications_count} применений</Text>
          </View>
          <TouchableOpacity 
            style={[
              styles.compareSelectButton,
              isSelected && styles.compareSelectButtonActive,
              !canSelect && !isSelected && styles.compareSelectButtonDisabled
            ]}
            onPress={() => toggleFungicideSelection(item.product_key)}
            disabled={!canSelect && !isSelected}
          >
            <Ionicons 
              name={isSelected ? "checkmark-circle" : "add-circle-outline"} 
              size={18} 
              color={isSelected ? "#FFFFFF" : (!canSelect ? "#D1D5DB" : "#F59E0B")} 
            />
            <Text style={[
              styles.compareSelectText,
              isSelected && styles.compareSelectTextActive,
              !canSelect && !isSelected && styles.compareSelectTextDisabled
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
      <KeyboardAvoidingView 
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={styles.flex}
      >
        {/* Header with Logo */}
        <View style={styles.header}>
          <View style={styles.titleRow}>
            <View>
              <Logo />
              <Text style={styles.subtitle}>Справочник фунгицидов РФ</Text>
            </View>
          </View>

          {stats && (
            <View style={styles.statsRow}>
              <View style={styles.statItem}>
                <Text style={styles.statValue}>{stats.unique_products}</Text>
                <Text style={styles.statLabel}>препаратов</Text>
              </View>
              <View style={styles.statDivider} />
              <View style={styles.statItem}>
                <Text style={styles.statValue}>{stats.active_registrations}</Text>
                <Text style={styles.statLabel}>действующих</Text>
              </View>
              <View style={styles.statDivider} />
              <View style={styles.statItem}>
                <Text style={styles.statValue}>{stats.total_records}</Text>
                <Text style={styles.statLabel}>применений</Text>
              </View>
            </View>
          )}
        </View>

        {/* Search */}
        <View style={styles.searchContainer}>
          <View style={styles.searchInputContainer}>
            <Ionicons name="search-outline" size={20} color="#9CA3AF" style={styles.searchIcon} />
            <TextInput
              style={styles.searchInput}
              placeholder="Поиск по названию или ДВ..."
              placeholderTextColor="#9CA3AF"
              value={searchQuery}
              onChangeText={setSearchQuery}
              onSubmitEditing={handleSearch}
              returnKeyType="search"
            />
            {(searchQuery.length > 0 || crop.length > 0 || harmfulObject.length > 0) && (
              <TouchableOpacity onPress={() => { setSearchQuery(''); setCrop(''); setHarmfulObject(''); search('', onlyActive, '', ''); }}>
                <Ionicons name="close-circle" size={20} color="#9CA3AF" />
              </TouchableOpacity>
            )}
          </View>


          <TextInput
            style={styles.filterInput}
            placeholder="Культура (опционально)"
            placeholderTextColor="#9CA3AF"
            value={crop}
            onChangeText={setCrop}
            onSubmitEditing={handleSearch}
            returnKeyType="search"
          />

          <TextInput
            style={styles.filterInput}
            placeholder="Болезнь (опционально)"
            placeholderTextColor="#9CA3AF"
            value={harmfulObject}
            onChangeText={setHarmfulObject}
            onSubmitEditing={handleSearch}
            returnKeyType="search"
          />

          <View style={styles.filterRow}>
            <TouchableOpacity
              style={[
                styles.filterButton,
                onlyActive && styles.filterButtonActive
              ]}
              onPress={toggleActiveFilter}
            >
              <Ionicons 
                name={onlyActive ? "checkmark-circle" : "ellipse-outline"} 
                size={18} 
                color={onlyActive ? "#10B981" : "#6B7280"} 
              />
              <Text style={[
                styles.filterText,
                onlyActive && styles.filterTextActive
              ]}>Только действующие</Text>
            </TouchableOpacity>

            <TouchableOpacity style={styles.searchButton} onPress={handleSearch}>
              <Text style={styles.searchButtonText}>Найти</Text>
            </TouchableOpacity>
          </View>
        </View>

        {/* Compare Bar */}
        {selectedFungicidesForCompare.length > 0 && (
          <View style={styles.compareBar}>
            <View style={styles.compareInfo}>
              <Text style={styles.compareText}>Выбрано: {selectedFungicidesForCompare.length}</Text>
              <TouchableOpacity onPress={clearFungicideSelection}>
                <Text style={styles.clearText}>Очистить</Text>
              </TouchableOpacity>
            </View>
            {selectedFungicidesForCompare.length === 2 && (
              <TouchableOpacity 
                style={styles.compareButton}
                onPress={() => router.push({
                  pathname: '/fungicide-compare',
                  params: {
                    left_key: selectedFungicidesForCompare[0],
                    right_key: selectedFungicidesForCompare[1],
                  },
                })}
              >
                <Ionicons name="git-compare-outline" size={18} color="#FFFFFF" />
                <Text style={styles.compareButtonText}>Сравнить</Text>
              </TouchableOpacity>
            )}
            {selectedFungicidesForCompare.length === 1 && (
              <Text style={styles.compareHint}>Выберите ещё 1 препарат</Text>
            )}
          </View>
        )}

        {/* Results */}
        <View style={styles.resultsContainer}>
          {loading ? (
            <View style={styles.loadingContainer}>
              <ActivityIndicator size="large" color="#F59E0B" />
              <Text style={styles.loadingText}>Загрузка...</Text>
            </View>
          ) : requestError ? (
            <RetryErrorCard onRetry={handleRetry} compact />
          ) : (
            <FlashList
              data={results}
              renderItem={renderItem}
              keyExtractor={(item) => item.product_key}
              contentContainerStyle={styles.listContent}
              refreshControl={
                <RefreshControl
                  refreshing={refreshing}
                  onRefresh={handleRefresh}
                  tintColor="#F59E0B"
                />
              }
              ListEmptyComponent={
                <View style={styles.emptyContainer}>
                  <Ionicons name="leaf-outline" size={64} color="#D1D5DB" />
                  <Text style={styles.emptyTitle}>Ничего не найдено</Text>
                  <Text style={styles.emptyText}>Попробуйте изменить запрос</Text>
                </View>
              }
            />
          )}
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#070A1C',
  },
  flex: {
    flex: 1,
  },
  header: {
    backgroundColor: '#0B0F26',
    paddingHorizontal: 20,
    paddingTop: 16,
    paddingBottom: 20,
    borderBottomWidth: 1,
    borderBottomColor: '#2A335A',
  },
  titleRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  logoContainer: {
    marginBottom: 2,
  },
  logoText: {
    fontSize: 32,
    fontWeight: '800',
    letterSpacing: -1,
  },
  logoB: {
    color: '#F8F8FF',
  },
  logoAI: {
    color: '#9B7BFF',
    fontWeight: '900',
  },
  logoKov: {
    color: '#F8F8FF',
  },
  subtitle: {
    fontSize: 14,
    color: '#C8CBE0',
    marginTop: 2,
  },
  statsRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 16,
    backgroundColor: '#FFF7ED',
    borderRadius: 12,
    padding: 12,
  },
  statItem: {
    flex: 1,
    alignItems: 'center',
  },
  statValue: {
    fontSize: 20,
    fontWeight: '700',
    color: '#F8F8FF',
  },
  statLabel: {
    fontSize: 12,
    color: '#C8CBE0',
    marginTop: 2,
  },
  statDivider: {
    width: 1,
    height: 30,
    backgroundColor: '#2A335A',
  },
  searchContainer: {
    backgroundColor: '#070A1C',
    paddingHorizontal: 20,
    paddingVertical: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#2A335A',
  },
  searchInputContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#171D3B',
    borderRadius: 12,
    paddingHorizontal: 12,
    height: 48,
  },
  searchIcon: {
    marginRight: 8,
  },
  searchInput: {
    flex: 1,
    fontSize: 16,
    color: '#F8F8FF',
  },
  filterInput: {
    backgroundColor: '#11162E',
    borderWidth: 1,
    borderColor: '#2A335A',
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 10,
    fontSize: 15,
    color: '#F8F8FF',
    marginTop: 8,
  },
  filterRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginTop: 12,
  },
  filterButton: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 8,
    paddingHorizontal: 12,
    borderRadius: 8,
    backgroundColor: '#171D3B',
  },
  filterButtonActive: {
    backgroundColor: '#123C38',
  },
  filterText: {
    marginLeft: 6,
    fontSize: 14,
    color: '#C8CBE0',
  },
  filterTextActive: {
    color: '#48D6A5',
  },
  searchButton: {
    backgroundColor: '#F59E0B',
    paddingVertical: 10,
    paddingHorizontal: 20,
    borderRadius: 8,
  },
  searchButtonText: {
    color: '#FFFFFF',
    fontSize: 14,
    fontWeight: '600',
  },
  compareBar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: '#FFFBEB',
    paddingHorizontal: 20,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#FDE68A',
  },
  compareInfo: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  compareText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#92400E',
  },
  clearText: {
    marginLeft: 12,
    fontSize: 14,
    color: '#C8CBE0',
    textDecorationLine: 'underline',
  },
  compareButton: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#F59E0B',
    paddingVertical: 8,
    paddingHorizontal: 16,
    borderRadius: 8,
  },
  compareButtonText: {
    color: '#FFFFFF',
    fontSize: 14,
    fontWeight: '600',
    marginLeft: 6,
  },
  compareHint: {
    fontSize: 13,
    color: '#C8CBE0',
    fontStyle: 'italic',
  },
  resultsContainer: {
    flex: 1,
  },
  listContent: {
    padding: 16,
  },
  card: {
    backgroundColor: '#11162E',
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: '#2A335A',
  },
  cardSelected: {
    borderColor: '#F59E0B',
    borderWidth: 2,
    backgroundColor: '#FFFBEB',
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 8,
  },
  cardTitleRow: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    marginRight: 8,
  },
  productName: {
    fontSize: 17,
    fontWeight: '600',
    color: '#F8F8FF',
    flexShrink: 1,
  },
  formulationBadge: {
    backgroundColor: '#1D2446',
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 4,
    marginLeft: 8,
  },
  formulationText: {
    fontSize: 12,
    color: '#C8CBE0',
    fontWeight: '500',
  },
  statusBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
  },
  statusActive: {
    backgroundColor: '#123C38',
  },
  statusInactive: {
    backgroundColor: '#421F35',
  },
  statusDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    marginRight: 6,
  },
  statusDotActive: {
    backgroundColor: '#10B981',
  },
  statusDotInactive: {
    backgroundColor: '#EF4444',
  },
  statusText: {
    fontSize: 11,
    fontWeight: '600',
  },
  statusTextActive: {
    color: '#48D6A5',
  },
  statusTextInactive: {
    color: '#FF718E',
  },
  substances: {
    fontSize: 14,
    color: '#C8CBE0',
    lineHeight: 20,
    marginBottom: 8,
  },
  manufacturerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 8,
  },
  manufacturer: {
    fontSize: 13,
    color: '#969DBB',
    marginLeft: 6,
    flex: 1,
  },
  cardFooter: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginTop: 4,
    paddingTop: 8,
    borderTopWidth: 1,
    borderTopColor: '#2A335A',
  },
  applicationsCount: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  applicationsText: {
    fontSize: 13,
    color: '#969DBB',
    marginLeft: 6,
  },
  cardContent: {
    flex: 1,
  },
  compareSelectButton: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 6,
    paddingHorizontal: 12,
    borderRadius: 6,
    backgroundColor: '#FFFBEB',
    borderWidth: 1,
    borderColor: '#F59E0B',
  },
  compareSelectButtonActive: {
    backgroundColor: '#F59E0B',
    borderColor: '#F59E0B',
  },
  compareSelectButtonDisabled: {
    backgroundColor: '#1D2446',
    borderColor: '#2A335A',
  },
  compareSelectText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#F59E0B',
    marginLeft: 4,
  },
  compareSelectTextActive: {
    color: '#FFFFFF',
  },
  compareSelectTextDisabled: {
    color: '#969DBB',
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingVertical: 60,
  },
  loadingText: {
    marginTop: 12,
    fontSize: 14,
    color: '#C8CBE0',
  },
  emptyContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingVertical: 60,
  },
  emptyTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: '#F8F8FF',
    marginTop: 16,
  },
  emptyText: {
    fontSize: 14,
    color: '#969DBB',
    marginTop: 4,
  },
});
