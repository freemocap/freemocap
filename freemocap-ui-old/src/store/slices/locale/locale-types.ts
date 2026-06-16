import type {SupportedLocale} from "@/i18n";

export interface LocaleState {
  locale: SupportedLocale;
  previousLocale: SupportedLocale | null;
  showTranslationIndicator: boolean;
}
