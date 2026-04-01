import { RootState } from "../../types";

export const selectLocale = (state: RootState) => state.settings.locale;
export const selectPreviousLocale = (state: RootState) =>
  state.settings.previousLocale;
export const selectShowTranslationIndicator = (state: RootState) =>
  state.settings.showTranslationIndicator;
