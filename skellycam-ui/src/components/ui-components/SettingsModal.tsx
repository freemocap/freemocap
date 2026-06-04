import React, { useCallback, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import useDraggableTooltips from '@/hooks/useDraggableTooltips';
import SubactionHeader from './SubactionHeader';
import ToggleComponent from './ToggleComponent';
import { VersionChip } from './VersionChip';
import { Footer } from './Footer';
import { LanguageSwitcher } from '@/components/languages/LanguageSwitcher';
import { useAppDispatch, useAppSelector } from '@/store';
import {
    showTranslationIndicatorToggled,
    selectShowTranslationIndicator,
    selectLocale,
} from '@/store/slices/settings';
import { getTranslationSource } from '@/i18n';
import { EXTERNAL_URLS } from '@/constants/external-urls';

interface SettingsModalProps {
    open: boolean;
    onClose: () => void;
}

export const SettingsModal: React.FC<SettingsModalProps> = ({ open, onClose }) => {
    const { t } = useTranslation();
    const dispatch = useAppDispatch();

    const showTranslationIndicator = useAppSelector(selectShowTranslationIndicator);
    const currentLocale = useAppSelector(selectLocale);
    const translationSource = getTranslationSource(currentLocale);

    useDraggableTooltips();

    useEffect(() => {
        if (!open) return;
        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.key === 'Escape') onClose();
        };
        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [open, onClose]);

    const handleTranslationIndicatorToggle = useCallback(() => {
        dispatch(showTranslationIndicatorToggled());
    }, [dispatch]);

    if (!open) return null;

    return (
        <div
            className="splash-overlay inset-0 reveal fadeIn"
            style={{ position: 'fixed', zIndex: 50 }}
            onClick={onClose}
        >
            <div
                className="draggable bg-dark br-2 border-1 border-black elevated-sharp flex flex-col p-2 gap-2"
                style={{ minWidth: 360, maxWidth: 480, maxHeight: '85vh', overflowY: 'auto' }}
                onClick={(e) => e.stopPropagation()}
            >
                {/* Header */}
                <div className="flex justify-content-space-between items-center">
                    <p className="text bg text-white">{t('settings')}</p>
                    <button className="button icon-button" onClick={onClose}>
                        <span className="icon close-icon icon-size-20" />
                    </button>
                </div>

                {/* Language & Localization */}
                <div className="flex flex-col gap-1 bg-middark br-1 p-2">
                    <SubactionHeader text={t('languageSettings')} />

                    <LanguageSwitcher />

                    {translationSource === 'ai-generated' && (
                        <p className="text sm text-gray">
                            {t('aiTranslatedTooltip')}{' '}
                            <a
                                href={EXTERNAL_URLS.TRANSLATING_GUIDE}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-warning"
                                style={{ textDecoration: 'underline' }}
                            >
                                {t('helpTranslate')}
                            </a>
                        </p>
                    )}

                    <ToggleComponent
                        text={t('showTranslationIndicator')}
                        isToggled={showTranslationIndicator}
                        onToggle={handleTranslationIndicatorToggle}
                    />
                </div>

                {/* About */}
                <div className="flex flex-col gap-1 bg-middark br-1 p-2">
                    <SubactionHeader text={t('about')} />

                    <p className="text sm text-gray">
                        {t('appName')} — {t('welcomeSubtitle')}
                    </p>
                    <VersionChip variant="compact" />
                </div>

                <Footer />
            </div>
        </div>
    );
};
