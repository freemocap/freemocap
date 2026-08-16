import {RootState} from "../../root-state-types";

export const selectLocale = (state: RootState) => state.locale.locale;
export const selectPreviousLocale = (state: RootState) =>
  state.locale.previousLocale;
export const selectShowTranslationIndicator = (state: RootState) =>
  state.locale.showTranslationIndicator;
