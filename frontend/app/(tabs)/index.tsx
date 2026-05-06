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

const API_URL = process.env.EXPO_PUBLIC_BACKEND_URL || '';

interface SearchResult {
  product_key: string;
  product_name: string;
  formulation: string | null;
  active_substances_raw: string | null;
  manufacturer: string | null;
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

export default function HomeScreen() {
  const router = useRouter();
  const [searchQuery, setSearchQuery] = useState('');
  const [crop, setCrop] = useState('');
  const [harmfulObject, setHarmfulObject] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [onlyActive, setOnlyActive] = useState(false);
  const [stats, setStats] = useState<{ total_records: number; unique_products: number; active_registrations: number } | null>(null);
  const { selectedForCompare, toggleSelection, clearSelection } = useHerbicideStore();

  const fetchStats = async () => {
    try {
      const response = await axios.get(`${API_URL}/api/stats`);
      setStats(response.data);
    } catch (error) {
      console.error('Failed to fetch stats:', error);
    }
  };

  const search = async (query: string, active: boolean, cropValue: string, harmfulObjectValue: string) => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (query.trim()) params.append('q', query.trim());
      if (cropValue.trim()) params.append('crop', cropValue.trim());
      if (harmfulObjectValue.trim()) params.append('harmful_object', harmfulObjectValue.trim());
      if (active) params.append('only_active', 'true');
      params.append('limit', '50');

      const response = await axios.get(`${API_URL}/api/herbicides/search?${params.toString()}`);
      setResults(response.data);
    } catch (error) {
      console.error('Search failed:', error);
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
    const isSelected = selectedForCompare.includes(item.product_key);
    const canSelect = selectedForCompare.length < 2 || isSelected;
    
    return (
      <View style={[styles.card, isSelected && styles.cardSelected]}>
        <TouchableOpacity
          style={styles.cardContent}
          onPress={() => router.push(`/product/${encodeURIComponent(item.product_key)}`)}
          activeOpacity={0.7}
        >
          <View style={styles.cardHeader}>
            <View style={styles.cardTitleRow}>
              <Text style={styles.productName} numberOfLines={1}>{item.product_name}</Text>
              {item.formulation && (
                <View style={styles.formulationBadge}>
                  <Text style={styles.formulationText}>{item.formulation}</Text>
                </View>
              )}
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

          {item.active_substances_raw && (
            <Text style={styles.substances} numberOfLines={2}>
              {item.active_substances_raw}
            </Text>
          )}

          {item.manufacturer && (
            <View style={styles.manufacturerRow}>
              <Ionicons name="business-outline" size={14} color="#9CA3AF" />
              <Text style={styles.manufacturer} numberOfLines={1}>{item.manufacturer}</Text>
            </View>
          )}
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
            onPress={() => toggleSelection(item.product_key)}
            disabled={!canSelect && !isSelected}
          >
            <Ionicons 
              name={isSelected ? "checkmark-circle" : "add-circle-outline"} 
              size={18} 
              color={isSelected ? "#FFFFFF" : (!canSelect ? "#D1D5DB" : "#3B82F6")} 
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
              <Text style={styles.subtitle}>Справочник гербицидов РФ</Text>
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
              placeholder="Поиск по названию, культуре, ДВ..."
              placeholderTextColor="#9CA3AF"
              value={searchQuery}
              onChangeText={setSearchQuery}
              onSubmitEditing={handleSearch}
              returnKeyType="search"
            />
            {searchQuery.length > 0 && (
              <TouchableOpacity onPress={() => { setSearchQuery(''); setCrop(''); setHarmfulObject(''); search('', onlyActive, '', ''); }}>
                <Ionicons name="close-circle" size={20} color="#9CA3AF" />
              </TouchableOpacity>
            )}
          </View>

          <View style={styles.advancedFilters}>
            <TextInput
              style={styles.advancedInput}
              placeholder="Культура (например, пшеница)"
              placeholderTextColor="#9CA3AF"
              value={crop}
              onChangeText={setCrop}
            />
            <TextInput
              style={styles.advancedInput}
              placeholder="Вредный объект"
              placeholderTextColor="#9CA3AF"
              value={harmfulObject}
              onChangeText={setHarmfulObject}
            />
            <TouchableOpacity style={styles.searchButton} onPress={handleSearch}>
              <Text style={styles.searchButtonText}>Найти</Text>
            </TouchableOpacity>
          </View>

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
          </View>
        </View>

        {/* Compare Bar */}
        {selectedForCompare.length > 0 && (
          <View style={styles.compareBar}>
            <View style={styles.compareInfo}>
              <Text style={styles.compareText}>Выбрано: {selectedForCompare.length}</Text>
              <TouchableOpacity onPress={clearSelection}>
                <Text style={styles.clearText}>Очистить</Text>
              </TouchableOpacity>
            </View>
            {selectedForCompare.length === 2 && (
              <TouchableOpacity 
                style={styles.compareButton}
                onPress={() => router.push('/compare')}
              >
                <Ionicons name="git-compare-outline" size={18} color="#FFFFFF" />
                <Text style={styles.compareButtonText}>Сравнить</Text>
              </TouchableOpacity>
            )}
            {selectedForCompare.length === 1 && (
              <Text style={styles.compareHint}>Выберите ещё 1 препарат</Text>
            )}
          </View>
        )}

        {/* Results */}
        <View style={styles.resultsContainer}>
          {loading ? (
            <View style={styles.loadingContainer}>
              <ActivityIndicator size="large" color="#3B82F6" />
              <Text style={styles.loadingText}>Загрузка...</Text>
            </View>
          ) : (
            <FlashList
              data={results}
              renderItem={renderItem}
              keyExtractor={(item) => item.product_key}
              estimatedItemSize={140}
              contentContainerStyle={styles.listContent}
              refreshControl={
                <RefreshControl
                  refreshing={refreshing}
                  onRefresh={handleRefresh}
                  tintColor="#3B82F6"
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
    backgroundColor: '#F9FAFB',
  },
  flex: {
    flex: 1,
  },
  header: {
    backgroundColor: '#FFFFFF',
    paddingHorizontal: 20,
    paddingTop: 16,
    paddingBottom: 20,
    borderBottomWidth: 1,
    borderBottomColor: '#E5E7EB',
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
    color: '#374151',
  },
  logoAI: {
    color: '#3B82F6',
    fontWeight: '900',
  },
  logoKov: {
    color: '#374151',
  },
  subtitle: {
    fontSize: 14,
    color: '#6B7280',
    marginTop: 2,
  },
  statsRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 16,
    backgroundColor: '#F3F4F6',
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
    color: '#111827',
  },
  statLabel: {
    fontSize: 12,
    color: '#6B7280',
    marginTop: 2,
  },
  statDivider: {
    width: 1,
    height: 30,
    backgroundColor: '#D1D5DB',
  },
  searchContainer: {
    backgroundColor: '#FFFFFF',
    paddingHorizontal: 20,
    paddingVertical: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#E5E7EB',
  },
  searchInputContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#F3F4F6',
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
    color: '#111827',
  },
  advancedFilters: {
    marginTop: 10,
    gap: 8,
  },
  advancedInput: {
    backgroundColor: '#F3F4F6',
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 14,
    color: '#111827',
  },
  searchButton: {
    backgroundColor: '#2563EB',
    borderRadius: 10,
    paddingVertical: 10,
    alignItems: 'center',
  },
  searchButtonText: {
    color: '#FFFFFF',
    fontWeight: '600',
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
    backgroundColor: '#F3F4F6',
  },
  filterButtonActive: {
    backgroundColor: '#D1FAE5',
  },
  filterText: {
    marginLeft: 6,
    fontSize: 14,
    color: '#6B7280',
  },
  filterTextActive: {
    color: '#059669',
  },
  searchButton: {
    backgroundColor: '#3B82F6',
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
    backgroundColor: '#EFF6FF',
    paddingHorizontal: 20,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#BFDBFE',
  },
  compareInfo: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  compareText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#1E40AF',
  },
  clearText: {
    marginLeft: 12,
    fontSize: 14,
    color: '#6B7280',
    textDecorationLine: 'underline',
  },
  compareButton: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#3B82F6',
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
    color: '#6B7280',
    fontStyle: 'italic',
  },
  resultsContainer: {
    flex: 1,
  },
  listContent: {
    padding: 16,
  },
  card: {
    backgroundColor: '#FFFFFF',
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: '#E5E7EB',
  },
  cardSelected: {
    borderColor: '#3B82F6',
    borderWidth: 2,
    backgroundColor: '#EFF6FF',
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
    color: '#111827',
    flexShrink: 1,
  },
  formulationBadge: {
    backgroundColor: '#F3F4F6',
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 4,
    marginLeft: 8,
  },
  formulationText: {
    fontSize: 12,
    color: '#6B7280',
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
    backgroundColor: '#D1FAE5',
  },
  statusInactive: {
    backgroundColor: '#FEE2E2',
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
    color: '#059669',
  },
  statusTextInactive: {
    color: '#DC2626',
  },
  substances: {
    fontSize: 14,
    color: '#4B5563',
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
    color: '#6B7280',
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
    borderTopColor: '#F3F4F6',
  },
  applicationsCount: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  applicationsText: {
    fontSize: 13,
    color: '#6B7280',
    marginLeft: 6,
  },
  selectedBadge: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  selectedText: {
    fontSize: 13,
    color: '#10B981',
    fontWeight: '500',
    marginLeft: 4,
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
    backgroundColor: '#EFF6FF',
    borderWidth: 1,
    borderColor: '#3B82F6',
  },
  compareSelectButtonActive: {
    backgroundColor: '#3B82F6',
    borderColor: '#3B82F6',
  },
  compareSelectButtonDisabled: {
    backgroundColor: '#F3F4F6',
    borderColor: '#D1D5DB',
  },
  compareSelectText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#3B82F6',
    marginLeft: 4,
  },
  compareSelectTextActive: {
    color: '#FFFFFF',
  },
  compareSelectTextDisabled: {
    color: '#D1D5DB',
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
    color: '#6B7280',
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
    color: '#374151',
    marginTop: 16,
  },
  emptyText: {
    fontSize: 14,
    color: '#9CA3AF',
    marginTop: 4,
  },
});
