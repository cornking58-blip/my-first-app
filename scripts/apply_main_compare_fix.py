from pathlib import Path

path = Path("frontend/app/(tabs)/index.tsx")
text = path.read_text(encoding="utf-8")

replacements = [
    (
        "import React, { useCallback, useState } from 'react';",
        "import React, { useCallback, useRef, useState } from 'react';",
    ),
    (
        "  const router = useRouter();\n  const [searchQuery, setSearchQuery] = useState('');",
        "  const router = useRouter();\n  const searchInputRef = useRef<TextInput>(null);\n  const [searchQuery, setSearchQuery] = useState('');",
    ),
    (
        "  const [showFilters, setShowFilters] = useState(false);\n  const { selectedForCompare, toggleSelection, clearSelection } = useHerbicideStore();",
        "  const [showFilters, setShowFilters] = useState(false);\n  const [compareMode, setCompareMode] = useState(false);\n  const { selectedForCompare, toggleSelection, clearSelection } = useHerbicideStore();",
    ),
    (
        "      if (harmfulObjectValue.trim()) params.append('harmful_object', harmfulObjectValue.trim());\n      if (active) params.append('only_active', 'true');",
        "      if (harmfulObjectValue.trim()) params.append('harmful_object', harmfulObjectValue.trim());\n      if (compareMode) params.append('group', 'herbicide');\n      if (active) params.append('only_active', 'true');",
    ),
    (
        "  }, [searchQuery, onlyActive, crop, harmfulObject]);",
        "  }, [searchQuery, onlyActive, crop, harmfulObject, compareMode]);",
    ),
    (
        "    setRequestError(null);\n    setHasSearched(false);\n  };",
        "    setRequestError(null);\n    setHasSearched(false);\n    setCompareMode(false);\n  };",
    ),
    (
        "  const openComparison = () => {\n    if (selectedForCompare.length !== 2) return;\n    router.push({\n      pathname: '/compare',\n      params: {\n        left_key: selectedForCompare[0],\n        right_key: selectedForCompare[1],\n      },\n    });\n  };",
        "  const openComparison = () => {\n    if (selectedForCompare.length === 2) {\n      router.push({\n        pathname: '/compare',\n        params: {\n          left_key: selectedForCompare[0],\n          right_key: selectedForCompare[1],\n        },\n      });\n      return;\n    }\n\n    setCompareMode(true);\n    setHasSearched(true);\n    setShowFilters(false);\n    setResults([]);\n    setRequestError(null);\n    setTimeout(() => searchInputRef.current?.focus(), 120);\n  };",
    ),
    (
        "            <TextInput\n              testID=\"main-search-input\"",
        "            <TextInput\n              ref={searchInputRef}\n              testID=\"main-search-input\"",
    ),
    (
        "          </View>\n\n          {showFilters ? (",
        "          </View>\n\n          {compareMode ? (\n            <View style={styles.compareModeNotice}>\n              <Ionicons name=\"git-compare-outline\" size={17} color={colors.primaryBright} />\n              <View style={styles.compareModeTextBlock}>\n                <Text style={styles.compareModeTitle}>Выберите два гербицида</Text>\n                <Text style={styles.compareModeText}>Найдите первый препарат, нажмите «Сравнить», затем выберите второй.</Text>\n              </View>\n            </View>\n          ) : null}\n\n          {showFilters ? (",
    ),
    (
        "              <Text style={styles.resultsTitle}>Каталог препаратов</Text>",
        "              <Text style={styles.resultsTitle}>{compareMode ? 'Выбор для сравнения' : 'Каталог препаратов'}</Text>",
    ),
    (
        "                    <Text style={styles.emptyTitle}>Ничего не найдено</Text>\n                    <Text style={styles.emptyText}>Попробуйте изменить запрос</Text>",
        "                    <Text style={styles.emptyTitle}>{compareMode ? 'Найдите первый гербицид' : 'Ничего не найдено'}</Text>\n                    <Text style={styles.emptyText}>{compareMode ? 'Введите название препарата в строке поиска' : 'Попробуйте изменить запрос'}</Text>",
    ),
    (
        "  searchToolsRow: {\n    flexDirection: 'row',\n    alignItems: 'center',\n    justifyContent: 'space-between',\n    marginTop: 12,\n  },",
        "  searchToolsRow: {\n    flexDirection: 'row',\n    alignItems: 'center',\n    justifyContent: 'space-between',\n    marginTop: 12,\n  },\n  compareModeNotice: {\n    flexDirection: 'row',\n    alignItems: 'center',\n    marginTop: 12,\n    paddingHorizontal: 12,\n    paddingVertical: 10,\n    borderRadius: 13,\n    backgroundColor: colors.surface,\n    borderWidth: 1,\n    borderColor: colors.primaryBorder,\n  },\n  compareModeTextBlock: { flex: 1, marginLeft: 9 },\n  compareModeTitle: { color: colors.text, fontSize: 12, fontWeight: '700' },\n  compareModeText: { color: colors.textMuted, fontSize: 10, lineHeight: 14, marginTop: 2 },",
    ),
]

for old, new in replacements:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"Expected one match, found {count}: {old[:80]!r}")
    text = text.replace(old, new, 1)

path.write_text(text, encoding="utf-8")
