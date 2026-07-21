import axios from 'axios';

type CompareSubstance = {
  name?: string | null;
  concentration?: number | null;
  unit?: string | null;
};

type CompareSide = {
  active_substances_raw?: string | null;
  substances?: CompareSubstance[] | null;
  [key: string]: unknown;
};

type CompareResponse = {
  left?: CompareSide | null;
  right?: CompareSide | null;
  [key: string]: unknown;
};

const INSTALL_FLAG = '__bAIkovSeedTreatmentCompareSanitizerInstalled__';

const formatConcentration = (value: number) => (
  Number.isInteger(value) ? String(value) : String(value).replace('.', ',')
);

const buildCompositionFromSubstances = (substances?: CompareSubstance[] | null) => {
  if (!Array.isArray(substances) || substances.length === 0) return '';

  return substances
    .map((substance) => {
      const name = substance?.name?.trim();
      if (!name) return '';

      const concentration = substance.concentration;
      const unit = substance.unit?.trim();

      if (typeof concentration !== 'number' || !Number.isFinite(concentration)) {
        return name;
      }

      const value = formatConcentration(concentration);
      return unit ? `${value} ${unit} ${name}` : `${value} ${name}`;
    })
    .filter(Boolean)
    .join(' + ');
};

const sanitizeSide = (side?: CompareSide | null): CompareSide | null | undefined => {
  if (!side) return side;

  const composition = buildCompositionFromSubstances(side.substances);
  if (!composition) return side;

  return {
    ...side,
    active_substances_raw: `(${composition})`,
  };
};

const installSanitizer = () => {
  const globalState = globalThis as typeof globalThis & Record<string, boolean | undefined>;
  if (globalState[INSTALL_FLAG]) return;

  axios.interceptors.response.use((response) => {
    const requestUrl = String(response.config?.url ?? '');
    if (!requestUrl.includes('/api/seed-treatments/compare-advanced')) {
      return response;
    }

    const data = response.data as CompareResponse | null | undefined;
    if (!data || typeof data !== 'object') return response;

    response.data = {
      ...data,
      left: sanitizeSide(data.left),
      right: sanitizeSide(data.right),
    };

    return response;
  });

  globalState[INSTALL_FLAG] = true;
};

installSanitizer();
