import { createSlice, PayloadAction } from "@reduxjs/toolkit";
import type { SettingsState } from "./settings-types";
import type { SupportedLocale } from "@/i18n";
import { FALLBACK_LOCALE, getLocaleDirection } from "@/i18n";
import i18n from "@/i18n/i18n";

const STORAGE_KEYS = {
  LOCALE: "freemocap:locale",
  PREVIOUS_LOCALE: "freemocap:previousLocale",
  SHOW_TRANSLATION_INDICATOR: "freemocap:showTranslationIndicator",
} as const;

function loadLocale(): SupportedLocale {
  if (typeof window === "undefined") return FALLBACK_LOCALE;
  const saved = localStorage.getItem(STORAGE_KEYS.LOCALE);
  if (saved) return saved as SupportedLocale;
  return (i18n.language as SupportedLocale) || FALLBACK_LOCALE;
}

function loadPreviousLocale(): SupportedLocale | null {
  if (typeof window === "undefined") return null;
  const saved = localStorage.getItem(STORAGE_KEYS.PREVIOUS_LOCALE);
  return saved as SupportedLocale | null;
}

function loadShowTranslationIndicator(): boolean {
  if (typeof window === "undefined") return true;
  const saved = localStorage.getItem(STORAGE_KEYS.SHOW_TRANSLATION_INDICATOR);
  if (saved !== null) return JSON.parse(saved) as boolean;
  return true;
}

/** Applies locale side-effects: syncs i18next, document dir, and localStorage. */
function applyLocale(locale: SupportedLocale): void {
  localStorage.setItem(STORAGE_KEYS.LOCALE, locale);
  i18n.changeLanguage(locale);
  const dir = getLocaleDirection(locale);
  document.documentElement.dir = dir;
  document.documentElement.lang = locale;
}

const initialState: SettingsState = {
  locale: loadLocale(),
  previousLocale: loadPreviousLocale(),
  showTranslationIndicator: loadShowTranslationIndicator(),
};

export const settingsSlice = createSlice({
  name: "settings",
  initialState,
  reducers: {
    localeChanged: (state, action: PayloadAction<SupportedLocale>) => {
      const next = action.payload;
      if (next === state.locale) return;

      // Remember the outgoing locale so we can toggle back to it
      state.previousLocale = state.locale;
      localStorage.setItem(STORAGE_KEYS.PREVIOUS_LOCALE, state.locale);

      state.locale = next;
      applyLocale(next);
    },

    /** Toggle between the current locale and the previous one (Ctrl+Shift+L). */
    localeToggled: (state) => {
      const target = state.previousLocale;
      if (!target || target === state.locale) return;

      const outgoing = state.locale;
      state.locale = target;
      state.previousLocale = outgoing;
      localStorage.setItem(STORAGE_KEYS.PREVIOUS_LOCALE, outgoing);
      applyLocale(target);
    },

    showTranslationIndicatorToggled: (state) => {
      state.showTranslationIndicator = !state.showTranslationIndicator;
      localStorage.setItem(
        STORAGE_KEYS.SHOW_TRANSLATION_INDICATOR,
        JSON.stringify(state.showTranslationIndicator)
      );
    },
  },
});

export const { localeChanged, localeToggled, showTranslationIndicatorToggled } =
  settingsSlice.actions;
