export {
  default as i18n,
  SUPPORTED_LOCALES,
  FALLBACK_LOCALE,
  LOCALE_STORAGE_KEYS,
  changeLocale,
  getLocaleDirection,
  getStoredLocale,
  getStoredPreviousLocale,
  getStoredTranslationIndicator,
  getTranslationSource,
  initializeI18n,
  isSupportedLocale,
  loadLocale,
} from "./i18n";
export type { SupportedLocale } from "./i18n";
