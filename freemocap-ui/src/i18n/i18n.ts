import i18n from "i18next";
import {initReactI18next} from "react-i18next";
import LanguageDetector from "i18next-browser-languagedetector";

// Only eagerly load the fallback locale — all others are lazy-loaded on demand
import en from "./locales/en-english.json";

export const SUPPORTED_LOCALES = {
  en: { label: "English", englishName: "English", dir: "ltr" as const, flag: "US" },
  es: { label: "Español", englishName: "Spanish", dir: "ltr" as const, flag: "ES" },
  fr: { label: "Français", englishName: "French", dir: "ltr" as const, flag: "FR" },
  de: { label: "Deutsch", englishName: "German", dir: "ltr" as const, flag: "DE" },
  it: { label: "Italiano", englishName: "Italian", dir: "ltr" as const, flag: "IT" },
  "pt-BR": { label: "Português (Brasil)", englishName: "Portuguese (Brazil)", dir: "ltr" as const, flag: "BR" },
  nl: { label: "Nederlands", englishName: "Dutch", dir: "ltr" as const, flag: "NL" },
  sv: { label: "Svenska", englishName: "Swedish", dir: "ltr" as const, flag: "SE" },
  pl: { label: "Polski", englishName: "Polish", dir: "ltr" as const, flag: "PL" },
  cs: { label: "Čeština", englishName: "Czech", dir: "ltr" as const, flag: "CZ" },
  uk: { label: "Українська", englishName: "Ukrainian", dir: "ltr" as const, flag: "UA" },
  ru: { label: "Русский", englishName: "Russian", dir: "ltr" as const, flag: "RU" },
  tr: { label: "Türkçe", englishName: "Turkish", dir: "ltr" as const, flag: "TR" },
  ar: { label: "العربية", englishName: "Arabic", dir: "rtl" as const, flag: "PS" },
  fa: { label: "فارسی", englishName: "Persian", dir: "rtl" as const, flag: "IR" },
  ur: { label: "اردو", englishName: "Urdu", dir: "rtl" as const, flag: "PK" },
  hi: { label: "हिन्दी", englishName: "Hindi", dir: "ltr" as const, flag: "IN" },
  bn: { label: "বাংলা", englishName: "Bengali", dir: "ltr" as const, flag: "BD" },
  ta: { label: "தமிழ்", englishName: "Tamil", dir: "ltr" as const, flag: "IN" },
  ne: { label: "नेपाली", englishName: "Nepali", dir: "ltr" as const, flag: "NP" },
  si: { label: "සිංහල", englishName: "Sinhala", dir: "ltr" as const, flag: "LK" },
  "zh-CN": { label: "简体中文", englishName: "Chinese (Simplified)", dir: "ltr" as const, flag: "CN" },
  ja: { label: "日本語", englishName: "Japanese", dir: "ltr" as const, flag: "JP" },
  ko: { label: "한국어", englishName: "Korean", dir: "ltr" as const, flag: "KR" },
  th: { label: "ไทย", englishName: "Thai", dir: "ltr" as const, flag: "TH" },
  vi: { label: "Tiếng Việt", englishName: "Vietnamese", dir: "ltr" as const, flag: "VN" },
  id: { label: "Bahasa Indonesia", englishName: "Indonesian", dir: "ltr" as const, flag: "ID" },
  ms: { label: "Bahasa Melayu", englishName: "Malay", dir: "ltr" as const, flag: "MY" },
  tl: { label: "Tagalog", englishName: "Tagalog", dir: "ltr" as const, flag: "PH" },
  my: { label: "မြန်မာ", englishName: "Burmese", dir: "ltr" as const, flag: "MM" },
  sw: { label: "Kiswahili", englishName: "Swahili", dir: "ltr" as const, flag: "KE" },
  am: { label: "አማርኛ", englishName: "Amharic", dir: "ltr" as const, flag: "ET" },
  ro: { label: "Română", englishName: "Romanian", dir: "ltr" as const, flag: "RO" },
  el: { label: "Ελληνικά", englishName: "Greek", dir: "ltr" as const, flag: "GR" },
  hu: { label: "Magyar", englishName: "Hungarian", dir: "ltr" as const, flag: "HU" },
  ka: { label: "ქართული", englishName: "Georgian", dir: "ltr" as const, flag: "GE" },
  sr: { label: "Српски", englishName: "Serbian", dir: "ltr" as const, flag: "RS" },
  hr: { label: "Hrvatski", englishName: "Croatian", dir: "ltr" as const, flag: "HR" },
  ca: { label: "Català", englishName: "Catalan", dir: "ltr" as const, flag: "ES" },
  chr: { label: "ᏣᎳᎩ", englishName: "Cherokee", dir: "ltr" as const, flag: "CHEROKEE" },
  yi: { label: "ייִדיש", englishName: "Yiddish", dir: "rtl" as const, flag: "YIDDISH" },
} as const;

export type SupportedLocale = keyof typeof SUPPORTED_LOCALES;

export const FALLBACK_LOCALE: SupportedLocale = "en";

/**
 * Returns the text direction for the given locale.
 * Defaults to "ltr" for unknown locales.
 */
export function getLocaleDirection(locale: string): "ltr" | "rtl" {
  if (locale in SUPPORTED_LOCALES) {
    return SUPPORTED_LOCALES[locale as SupportedLocale].dir;
  }
  return "ltr";
}

/**
 * Dynamic import loaders for each non-English locale.
 * Vite splits each into a separate chunk that's only fetched when needed.
 */
const LOCALE_LOADERS: Record<string, () => Promise<{ default: Record<string, any> }>> = {
  es: () => import("./locales/es-espanol.json"),
  fr: () => import("./locales/fr-francais.json"),
  de: () => import("./locales/de-deutsch.json"),
  it: () => import("./locales/it-italiano.json"),
  "pt-BR": () => import("./locales/pt-BR-portugues-brasil.json"),
  nl: () => import("./locales/nl-nederlands.json"),
  sv: () => import("./locales/sv-svenska.json"),
  pl: () => import("./locales/pl-polski.json"),
  cs: () => import("./locales/cs-cestina.json"),
  uk: () => import("./locales/uk-ukrainska.json"),
  ru: () => import("./locales/ru-russkiy.json"),
  tr: () => import("./locales/tr-turkce.json"),
  ar: () => import("./locales/ar-arabic.json"),
  fa: () => import("./locales/fa-farsi.json"),
  ur: () => import("./locales/ur-urdu.json"),
  hi: () => import("./locales/hi-hindi.json"),
  bn: () => import("./locales/bn-bangla.json"),
  ta: () => import("./locales/ta-tamil.json"),
  ne: () => import("./locales/ne-nepali.json"),
  si: () => import("./locales/si-sinhala.json"),
  "zh-CN": () => import("./locales/zh-CN-zhongwen.json"),
  ja: () => import("./locales/ja-nihongo.json"),
  ko: () => import("./locales/ko-hangugeo.json"),
  th: () => import("./locales/th-thai.json"),
  vi: () => import("./locales/vi-tieng-viet.json"),
  id: () => import("./locales/id-bahasa-indonesia.json"),
  ms: () => import("./locales/ms-melayu.json"),
  tl: () => import("./locales/tl-tagalog.json"),
  my: () => import("./locales/my-myanmar.json"),
  sw: () => import("./locales/sw-kiswahili.json"),
  am: () => import("./locales/am-amharic.json"),
  ro: () => import("./locales/ro-romana.json"),
  el: () => import("./locales/el-ellinika.json"),
  hu: () => import("./locales/hu-magyar.json"),
  ka: () => import("./locales/ka-kartuli.json"),
  sr: () => import("./locales/sr-srpski.json"),
  hr: () => import("./locales/hr-hrvatski.json"),
  ca: () => import("./locales/ca-catala.json"),
  chr: () => import("./locales/chr-tsalagi.json"),
  yi: () => import("./locales/yi-yidish.json"),
};

/** Tracks which locales have already been loaded to avoid duplicate fetches. */
const loadedLocales = new Set<string>(["en"]);

/**
 * Load a locale's translations on demand. If already loaded, resolves immediately.
 * Called automatically by the languageChanged event and can be called manually.
 */
export async function loadLocale(locale: string): Promise<void> {
  if (loadedLocales.has(locale)) return;

  const loader = LOCALE_LOADERS[locale];
  if (!loader) {
    throw new Error(`No locale loader registered for "${locale}". Supported: ${Object.keys(LOCALE_LOADERS).join(", ")}`);
  }

  const module = await loader();
  const translations = module.default;
  i18n.addResourceBundle(locale, "translation", translations, true, true);
  loadedLocales.add(locale);

  // Re-trigger changeLanguage after the bundle is loaded so react-i18next
  // detects the new resources and re-renders all translated components.
  if (i18n.language === locale) {
    await i18n.changeLanguage(locale);
  }
}

/**
 * Returns the _meta.translationSource value from a locale's translations.
 * Only works for locales that have already been loaded.
 */
export function getTranslationSource(
  locale: string
): "human-authored" | "ai-generated" | "human-validated" {
  const resources = i18n.getResourceBundle(locale, "translation");
  const meta = resources?._meta;
  if (
    meta?.translationSource === "human-authored" ||
    meta?.translationSource === "ai-generated" ||
    meta?.translationSource === "human-validated"
  ) {
    return meta.translationSource;
  }
  return "ai-generated";
}

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      en: { translation: en },
    },
    lng: FALLBACK_LOCALE,
    fallbackLng: FALLBACK_LOCALE,
    interpolation: {
      escapeValue: false,
    },
    detection: {
      order: ["localStorage"],
      lookupLocalStorage: "freemocap:locale",
      caches: ["localStorage"],
    },
  });

// When the language changes (via user selection or detection), load the locale on demand.
// The UI briefly shows English keys until the async load completes, then re-renders.
i18n.on("languageChanged", (lng: string) => {
  if (lng !== FALLBACK_LOCALE) {
    loadLocale(lng);
  }
});

// If the detected language on startup is not English, load it immediately
const detectedLng = i18n.language;
if (detectedLng && detectedLng !== FALLBACK_LOCALE && !loadedLocales.has(detectedLng)) {
  loadLocale(detectedLng);
}

export default i18n;
