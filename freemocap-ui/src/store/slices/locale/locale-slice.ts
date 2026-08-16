import {createSlice, PayloadAction} from "@reduxjs/toolkit";
import type {LocaleState} from "./locale-types";
import type {SupportedLocale} from "@/i18n";
import {
  changeLocale,
  getStoredLocale,
  getStoredPreviousLocale,
  getStoredTranslationIndicator,
  LOCALE_STORAGE_KEYS,
} from "@/i18n";

function loadLocale(): SupportedLocale {
  return getStoredLocale();
}

function loadPreviousLocale(): SupportedLocale | null {
  return getStoredPreviousLocale();
}

function loadShowTranslationIndicator(): boolean {
  return getStoredTranslationIndicator();
}

/** Applies locale side-effects: syncs i18next, document dir, and localStorage. */
function applyLocale(locale: SupportedLocale): void {
  void changeLocale(locale).catch((error) => {
    console.error("Failed to change locale:", error);
  });
}

const initialState: LocaleState = {
  locale: loadLocale(),
  previousLocale: loadPreviousLocale(),
  showTranslationIndicator: loadShowTranslationIndicator(),
};

export const localeSlice = createSlice({
  name: "settings",
  initialState,
  reducers: {
    localeChanged: (state, action: PayloadAction<SupportedLocale>) => {
      const next = action.payload;
      if (next === state.locale) return;

      // Remember the outgoing locale so we can toggle back to it
      state.previousLocale = state.locale;
      localStorage.setItem(LOCALE_STORAGE_KEYS.PREVIOUS_LOCALE, state.locale);

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
      localStorage.setItem(LOCALE_STORAGE_KEYS.PREVIOUS_LOCALE, outgoing);
      applyLocale(target);
    },

    showTranslationIndicatorToggled: (state) => {
      state.showTranslationIndicator = !state.showTranslationIndicator;
      localStorage.setItem(
        LOCALE_STORAGE_KEYS.SHOW_TRANSLATION_INDICATOR,
        JSON.stringify(state.showTranslationIndicator)
      );
    },
  },
});

export const { localeChanged, localeToggled, showTranslationIndicatorToggled } =
  localeSlice.actions;
