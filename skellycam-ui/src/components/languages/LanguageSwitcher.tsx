import React, { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import clsx from "clsx";
import { EXTERNAL_URLS } from "@/constants/external-urls";
import { useAppDispatch, useAppSelector } from "@/store";
import { localeChanged, selectLocale, selectShowTranslationIndicator } from "@/store/slices/settings";
import { SUPPORTED_LOCALES, getTranslationSource } from "@/i18n";
import type { SupportedLocale } from "@/i18n";
import * as Flags from "country-flag-icons/react/3x2";
import { CherokeeFlag } from "@/components/languages/custom-flag-icons/CherokeeFlag";
import { YiddishFlag } from "@/components/languages/custom-flag-icons/YiddishFlag";

const FlagIcon: React.FC<{ countryCode: string }> = ({ countryCode }) => {
    if (countryCode === "CHEROKEE") return <CherokeeFlag />;
    if (countryCode === "YIDDISH") return <YiddishFlag />;
    const Flag = Flags[countryCode as keyof typeof Flags];
    if (!Flag) return null;
    return <Flag style={{ width: 20, height: 14, borderRadius: 2, flexShrink: 0 }} />;
};

export const LanguageSwitcher: React.FC = () => {
    const { t } = useTranslation();
    const dispatch = useAppDispatch();
    const currentLocale = useAppSelector(selectLocale);
    const showIndicator = useAppSelector(selectShowTranslationIndicator);
    const translationSource = getTranslationSource(currentLocale);

    const [open, setOpen] = useState(false);
    const containerRef = useRef<HTMLDivElement>(null);

    // Close on outside click
    useEffect(() => {
        const handleClickOutside = (e: MouseEvent) => {
            if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
                setOpen(false);
            }
        };
        document.addEventListener("mousedown", handleClickOutside);
        return () => document.removeEventListener("mousedown", handleClickOutside);
    }, []);

    const handleSelect = useCallback((code: SupportedLocale) => {
        dispatch(localeChanged(code));
        setOpen(false);
    }, [dispatch]);

    const currentLocaleData = SUPPORTED_LOCALES[currentLocale];

    const badgeClass = translationSource === "ai-generated" ? "ai"
        : translationSource === "human-validated" ? "human"
        : "native";

    const sourceLabel = translationSource === "human-authored" ? t("humanTranslated")
        : translationSource === "human-validated" ? t("humanValidated")
        : t("aiTranslated");

    return (
        <div className="flex items-center gap-1 flex-wrap">
            <div ref={containerRef} className="language-dropdown-container">
                {/* Trigger */}
                <button
                    className="gap-1 br-1 button sm fit-content flex-inline items-center dropdown"
                    onClick={() => setOpen((prev) => !prev)}
                >
                    <FlagIcon countryCode={currentLocaleData?.flag ?? ""} />
                    <p className="text-gray text md text-align-left text-nowrap">
                        {currentLocaleData?.label ?? currentLocale}
                    </p>
                </button>

                {/* Dropdown */}
                {open && (
                    <div className="language-dropdown-panel dropdown-container border-1 border-black elevated-sharp bg-dark br-2 reveal slide-down">
                        <div className="flex flex-col p-1 gap-1 bg-middark br-1">
                            {Object.entries(SUPPORTED_LOCALES).map(([code, { label, englishName, flag }]) => (
                                <button
                                    key={code}
                                    className={clsx("language-option button sm br-1", code === currentLocale && "selected")}
                                    onClick={() => handleSelect(code as SupportedLocale)}
                                >
                                    <FlagIcon countryCode={flag} />
                                    <p className="text-gray text md text-nowrap">{label}</p>
                                    {label !== englishName && (
                                        <p className="text-darkgray text sm text-nowrap">{englishName}</p>
                                    )}
                                    <p className="text-darkgray text sm" style={{ fontFamily: "monospace" }}>{code}</p>
                                </button>
                            ))}
                        </div>
                    </div>
                )}
            </div>

            {showIndicator && translationSource !== "human-authored" && (
                <a
                    href={EXTERNAL_URLS.TRANSLATION_LOCALES}
                    target="_blank"
                    rel="noopener noreferrer"
                    className={clsx("translation-badge pos-abs", badgeClass)}
                    title={translationSource === "ai-generated" ? t("aiTranslatedTooltip") : t("humanValidatedTooltip")}
                >
                    <span className="text sm">{sourceLabel}</span>
                </a>
            )}
        </div>
    );
};
