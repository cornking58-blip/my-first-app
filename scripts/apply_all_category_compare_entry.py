from pathlib import Path

path = Path("frontend/app/(tabs)/index.tsx")
text = path.read_text(encoding="utf-8")
old = '''  const openComparison = () => {
    if (selectedForCompare.length === 2) {
      router.push({
        pathname: '/compare',
        params: {
          left_key: selectedForCompare[0],
          right_key: selectedForCompare[1],
        },
      });
      return;
    }

    setCompareMode(true);
    setHasSearched(true);
    setShowFilters(false);
    setResults([]);
    setRequestError(null);
    setTimeout(() => searchInputRef.current?.focus(), 120);
  };'''
new = '''  const openComparison = () => {
    router.push('/compare-select');
  };'''
if text.count(old) != 1:
    raise RuntimeError(f"Expected one old comparison handler, found {text.count(old)}")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
