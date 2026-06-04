import type { SupportedLocale } from "@/i18n";

export interface SettingsState {
  locale: SupportedLocale;
  previousLocale: SupportedLocale | null;
  showTranslationIndicator: boolean;
}
