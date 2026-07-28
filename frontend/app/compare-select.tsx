import React, { useMemo, useState } from 'react';
import {
  ActivityIndicator,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import axios from 'axios';
import { AmbientBackground } from '../src/components/AmbientBackground';
import { BrandLogo } from '../src/components/BrandLogo';
import { RetryErrorCard } from '../src/components/RetryErrorCard';
import { colors } from '../src/theme/colors';

const API_URL = process.env.EXPO_PUBLIC_BACKEND_URL || '';

type ProductGroup = 'herbicide' | 'fungicide' | 'insecticide' | 'seed_treatment';

type SearchResult = {
  product_key: string;
  product_name: string;
  formulation: string | null;
  active_substances_raw: string | null;
  display_manufacturer: string | null;
  registration_status: string | null;
  applications_count: number;
  product_group: ProductGroup;
};

const GROUPS: Array<{
  key: ProductGroup;
  title: string;
  icon: keyof typeof Ionicons.glyphMap;
  route: '/compare' | '/fungicide-compare' | '/insecticide-compare' | '/seed-treatment-compare';
}> = [
  { key: 'herbicide', title: 'Гербициды', icon: 'leaf-outline', route: '/compare' },
  { key: 'fungicide', title: 'Фунгициды', icon: 'shield-checkmark-outline', route: '/fungicide-compare' },
  { key: 'insecticide', title: 'Инсектициды', icon: 'bug-outline', route: '/insecticide-compare' },
  { key: 'seed_treatment', title: 'Протравители', icon: 'ellipse-outline', route: '/seed-treatment-compare' },
];

export default function CompareSelectScreen() {
  const router = useRouter();
  const [group, setGroup] = useState<ProductGroup | null>(null);
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [selected, setSelected] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);

  const currentGroup = useMemo(
    () => GROUPS.find(item => item.key === group) || null,
    [group],
  );

  const selectGroup = (nextGroup: ProductGroup) => {
    setGroup(nextGroup);
    setQuery('');
    setResults([]);
    setSelected([]);
    setError(false);
    setHasSearched(false);
  };

  const search = async () => {
    if (!group || loading) return;
    setLoading(true);
    setError(false);
    setHasSearched(true);
    try {
      const params = new URLSearchParams();
      params.append('group', group);
      params.append('limit', '100');
      if (query.trim()) params.append('q', query.trim());
      const response = await axios.get(`${API_URL}/api/products/search?${params.toString()}`);
      setResults(response.data);
    } catch (requestError) {
      console.error('Comparison search failed:', requestError);
      setResults([]);
      setError(true);
    } finally {
      setLoading(false);
    }
  };

  const toggleSelection = (item: SearchResult) => {
    if (item.product_group !== group) return;
    setSelected(current => {
      if (current.some(product => product.product_key === item.product_key)) {
        return current.filter(product => product.product_key !== item.product_key);
      }
      if (current.length >= 2) return current;
      return [...current, item];
    });
  };

  const openComparison = () => {
    if (!currentGroup || selected.length !== 2) return;
    router.push({
      pathname: currentGroup.route,
      params: {
        left_key: selected[0].product_key,
        right_key: selected[1].product_key,
      },
    } as never);
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <AmbientBackground />
      <View style={styles.header}>
        <TouchableOpacity style={styles.backButton} onPress={() => router.back()}>
          <Ionicons name="arrow-back" size={22} color={colors.text} />
        </TouchableOpacity>
        <BrandLogo compact />
        <View style={styles.headerSpacer} />
      </View>

      <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
        <Text style={styles.title}>Сравнение препаратов</Text>
        <Text style={styles.subtitle}>
          Сначала выберите категорию. Сравнивать можно только препараты одной группы.
        </Text>

        <View style={styles.groupGrid}>
          {GROUPS.map(item => {
            const active = item.key === group;
            return (
              <TouchableOpacity
                key={item.key}
                style={[styles.groupCard, active && styles.groupCardActive]}
                onPress={() => selectGroup(item.key)}
                activeOpacity={0.78}
              >
                <Ionicons
                  name={item.icon}
                  size={22}
                  color={active ? colors.primaryBright : colors.textSecondary}
                />
                <Text style={[styles.groupTitle, active && styles.groupTitleActive]}>
                  {item.title}
                </Text>
              </TouchableOpacity>
            );
          })}
        </View>

        {currentGroup ? (
          <>
            <View style={styles.notice}>
              <Ionicons name="lock-closed-outline" size={17} color={colors.primaryBright} />
              <Text style={styles.noticeText}>
                Выбрана категория «{currentGroup.title}». Второй препарат будет только из этой же категории.
              </Text>
            </View>

            <View style={styles.searchRow}>
              <View style={styles.searchBox}>
                <Ionicons name="search-outline" size={19} color={colors.primaryBright} />
                <TextInput
                  style={styles.searchInput}
                  placeholder={`Найти: ${currentGroup.title.toLowerCase()}`}
                  placeholderTextColor={colors.textMuted}
                  value={query}
                  onChangeText={setQuery}
                  onSubmitEditing={search}
                  returnKeyType="search"
                />
              </View>
              <TouchableOpacity style={styles.searchButton} onPress={search}>
                <Ionicons name="arrow-forward" size={19} color={colors.white} />
              </TouchableOpacity>
            </View>

            <View style={styles.selectionLine}>
              <Text style={styles.selectionText}>Выбрано: {selected.length} из 2</Text>
              {selected.length > 0 ? (
                <TouchableOpacity onPress={() => setSelected([])}>
                  <Text style={styles.clearText}>Очистить</Text>
                </TouchableOpacity>
              ) : null}
            </View>

            {loading ? (
              <View style={styles.centerState}>
                <ActivityIndicator color={colors.primaryBright} />
                <Text style={styles.stateText}>Ищем препараты...</Text>
              </View>
            ) : error ? (
              <RetryErrorCard onRetry={search} compact />
            ) : hasSearched ? (
              results.length > 0 ? (
                <View style={styles.results}>
                  {results.map(item => {
                    const isSelected = selected.some(product => product.product_key === item.product_key);
                    const disabled = selected.length >= 2 && !isSelected;
                    return (
                      <TouchableOpacity
                        key={item.product_key}
                        style={[
                          styles.productCard,
                          isSelected && styles.productCardSelected,
                          disabled && styles.productCardDisabled,
                        ]}
                        onPress={() => toggleSelection(item)}
                        disabled={disabled}
                        activeOpacity={0.78}
                      >
                        <View style={styles.productMain}>
                          <Text style={styles.productName}>{item.product_name}</Text>
                          {item.active_substances_raw ? (
                            <Text style={styles.productComposition} numberOfLines={2}>
                              {item.active_substances_raw}
                            </Text>
                          ) : null}
                          {item.display_manufacturer ? (
                            <Text style={styles.productManufacturer} numberOfLines={1}>
                              {item.display_manufacturer}
                            </Text>
                          ) : null}
                        </View>
                        <Ionicons
                          name={isSelected ? 'checkmark-circle' : 'add-circle-outline'}
                          size={23}
                          color={isSelected ? colors.primaryBright : colors.textMuted}
                        />
                      </TouchableOpacity>
                    );
                  })}
                </View>
              ) : (
                <View style={styles.centerState}>
                  <Ionicons name="search-outline" size={36} color={colors.borderStrong} />
                  <Text style={styles.stateTitle}>Ничего не найдено</Text>
                  <Text style={styles.stateText}>Измените название препарата</Text>
                </View>
              )
            ) : (
              <View style={styles.centerState}>
                <Ionicons name="git-compare-outline" size={36} color={colors.borderStrong} />
                <Text style={styles.stateTitle}>Найдите первый препарат</Text>
                <Text style={styles.stateText}>Затем выберите второй из этой же категории</Text>
              </View>
            )}
          </>
        ) : (
          <View style={styles.centerState}>
            <Ionicons name="layers-outline" size={38} color={colors.borderStrong} />
            <Text style={styles.stateTitle}>Выберите категорию</Text>
          </View>
        )}
      </ScrollView>

      {selected.length === 2 && currentGroup ? (
        <View style={styles.bottomBar}>
          <View style={styles.bottomTextBlock}>
            <Text style={styles.bottomTitle}>{currentGroup.title}</Text>
            <Text style={styles.bottomText} numberOfLines={1}>
              {selected[0].product_name} ↔ {selected[1].product_name}
            </Text>
          </View>
          <TouchableOpacity style={styles.openButton} onPress={openComparison}>
            <Text style={styles.openButtonText}>Сравнить</Text>
            <Ionicons name="arrow-forward" size={17} color={colors.white} />
          </TouchableOpacity>
        </View>
      ) : null}
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
  },
  backButton: {
    width: 40,
    height: 40,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 13,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
  },
  headerSpacer: { width: 40 },
  content: { paddingHorizontal: 18, paddingTop: 18, paddingBottom: 130 },
  title: { color: colors.text, fontSize: 25, fontWeight: '800', letterSpacing: -0.5 },
  subtitle: { color: colors.textMuted, fontSize: 13, lineHeight: 19, marginTop: 7 },
  groupGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10, marginTop: 20 },
  groupCard: {
    width: '48%',
    minHeight: 86,
    borderRadius: 16,
    paddingHorizontal: 14,
    paddingVertical: 14,
    justifyContent: 'space-between',
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
  },
  groupCardActive: { borderColor: colors.primaryBright },
  groupTitle: { color: colors.textSecondary, fontSize: 13, fontWeight: '700', marginTop: 10 },
  groupTitleActive: { color: colors.text },
  notice: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 16,
    padding: 12,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.primaryBorder,
    backgroundColor: colors.surface,
  },
  noticeText: { flex: 1, color: colors.textSecondary, fontSize: 11, lineHeight: 16, marginLeft: 9 },
  searchRow: { flexDirection: 'row', gap: 9, marginTop: 14 },
  searchBox: {
    flex: 1,
    height: 52,
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 14,
    borderRadius: 15,
    borderWidth: 1,
    borderColor: colors.primaryBorder,
    backgroundColor: colors.surface,
  },
  searchInput: { flex: 1, color: colors.text, fontSize: 14, marginLeft: 9 },
  searchButton: {
    width: 52,
    height: 52,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 15,
    backgroundColor: colors.primary,
  },
  selectionLine: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginTop: 13,
    marginBottom: 8,
  },
  selectionText: { color: colors.textSecondary, fontSize: 12, fontWeight: '700' },
  clearText: { color: colors.primaryBright, fontSize: 11, fontWeight: '700' },
  results: { gap: 9 },
  productCard: {
    flexDirection: 'row',
    alignItems: 'center',
    minHeight: 92,
    padding: 13,
    borderRadius: 15,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
  },
  productCardSelected: { borderColor: colors.primaryBright },
  productCardDisabled: { opacity: 0.42 },
  productMain: { flex: 1, marginRight: 12 },
  productName: { color: colors.text, fontSize: 15, fontWeight: '700' },
  productComposition: { color: colors.textSecondary, fontSize: 12, lineHeight: 17, marginTop: 5 },
  productManufacturer: { color: colors.textMuted, fontSize: 11, marginTop: 5 },
  centerState: { alignItems: 'center', paddingVertical: 44 },
  stateTitle: { color: colors.text, fontSize: 16, fontWeight: '700', marginTop: 12 },
  stateText: { color: colors.textMuted, fontSize: 12, textAlign: 'center', marginTop: 5 },
  bottomBar: {
    position: 'absolute',
    left: 12,
    right: 12,
    bottom: 10,
    minHeight: 68,
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: 17,
    borderWidth: 1,
    borderColor: colors.primaryBorder,
    backgroundColor: colors.backgroundDeep,
  },
  bottomTextBlock: { flex: 1, marginRight: 10 },
  bottomTitle: { color: colors.primaryBright, fontSize: 11, fontWeight: '700' },
  bottomText: { color: colors.text, fontSize: 12, fontWeight: '700', marginTop: 3 },
  openButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 14,
    paddingVertical: 11,
    borderRadius: 12,
    backgroundColor: colors.primary,
  },
  openButtonText: { color: colors.white, fontSize: 12, fontWeight: '800' },
});
