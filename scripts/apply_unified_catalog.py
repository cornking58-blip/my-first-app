from pathlib import Path
import re

SERVER = Path("backend/server.py")
INDEX = Path("frontend/app/(tabs)/index.tsx")
AI_SCREEN = Path("frontend/app/ai.tsx")
REQUIREMENTS = Path("backend/requirements.txt")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, got {count}")
    return text.replace(old, new, 1)


server = SERVER.read_text(encoding="utf-8")
server = replace_once(
    server,
    "from collections import Counter, defaultdict\n",
    "from collections import Counter, defaultdict\nfrom product_catalog import build_catalog_ai_context, create_products_router\n",
    "catalog import",
)

pattern = re.compile(
    r"async def build_general_ai_context\(message: str\) -> Dict\[str, Any\]:\n.*?\n\nasync def build_ai_chat_context",
    flags=re.DOTALL,
)
replacement = '''async def build_general_ai_context(message: str) -> Dict[str, Any]:
    return await build_catalog_ai_context(db, message)


async def build_ai_chat_context'''
server, count = pattern.subn(replacement, server, count=1)
if count != 1:
    raise RuntimeError(f"AI context replacement failed: {count}")

server = replace_once(
    server,
    "# Include the router in the main app\napp.include_router(api_router)",
    "# Include the routers in the main app\napp.include_router(create_products_router(db))\napp.include_router(api_router)",
    "products router",
)
server = server.replace("Справочник гербицидов РФ", "Единый справочник пестицидов РФ")
SERVER.write_text(server, encoding="utf-8")

index = INDEX.read_text(encoding="utf-8")
index = replace_once(
    index,
    "  applications_count: number;\n}",
    "  applications_count: number;\n  product_group: 'herbicide' | 'fungicide' | 'insecticide' | 'seed_treatment';\n  product_group_title?: string;\n}",
    "search result group",
)
index = replace_once(
    index,
    "      params.append('limit', '50');\n\n      const response = await axios.get(`${API_URL}/api/herbicides/search?${params.toString()}`);",
    "      params.append('limit', '100');\n\n      const response = await axios.get(`${API_URL}/api/products/search?${params.toString()}`);",
    "universal search endpoint",
)
index = replace_once(
    index,
    "  const isActive = (status: string | null) => status?.toLowerCase().trim() === 'действует';\n\n  const renderItem",
    '''  const isActive = (status: string | null) => status?.toLowerCase().trim() === 'действует';

  const openProduct = (item: SearchResult) => {
    const routes = {
      herbicide: '/product/',
      fungicide: '/fungicide-product/',
      insecticide: '/insecticide-product/',
      seed_treatment: '/seed-treatment-product/',
    } as const;
    router.push(`${routes[item.product_group]}${encodeURIComponent(item.product_key)}` as never);
  };

  const renderItem''',
    "product route helper",
)
index = index.replace(
    "onPress={() => router.push(`/product/${encodeURIComponent(item.product_key)}`)}",
    "onPress={() => openProduct(item)}",
)
index = replace_once(
    index,
    "              <Text style={styles.productName} numberOfLines={1}>{item.product_name}</Text>",
    '''              <View style={styles.productTitleBlock}>
                <Text style={styles.productName} numberOfLines={1}>{item.product_name}</Text>
                <Text style={styles.productGroupLabel}>{item.product_group_title || item.product_group}</Text>
              </View>''',
    "product group label",
)
index = replace_once(
    index,
    '''          <TouchableOpacity
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
          </TouchableOpacity>''',
    '''          {item.product_group === 'herbicide' ? (
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
          ) : null}''',
    "safe compare button",
)
index = index.replace("Справочник гербицидов РФ", "Справочник пестицидов РФ")
index = index.replace("Название, действующее вещество...", "Название, ДВ, производитель...")
index = index.replace("Сорное растение / вредный объект", "Вредный объект")
index = replace_once(
    index,
    "  productName: { color: colors.text, fontSize: 16, fontWeight: '700', flexShrink: 1 },",
    "  productTitleBlock: { flex: 1 },\n  productName: { color: colors.text, fontSize: 16, fontWeight: '700' },\n  productGroupLabel: { color: colors.primaryBright, fontSize: 10, marginTop: 3 },",
    "group styles",
)
INDEX.write_text(index, encoding="utf-8")

ai = AI_SCREEN.read_text(encoding="utf-8")
ai = ai.replace("справочника гербицидов РФ", "единого справочника пестицидов РФ")
AI_SCREEN.write_text(ai, encoding="utf-8")

requirements = REQUIREMENTS.read_text(encoding="utf-8")
requirements = re.sub(
    r"\n# Install the AI runtime loader.*?\ngit\+https://github\.com/cornking58-blip/my-first-app\.git@[^\n]+",
    "",
    requirements,
    flags=re.DOTALL,
)
REQUIREMENTS.write_text(requirements.rstrip() + "\n", encoding="utf-8")
