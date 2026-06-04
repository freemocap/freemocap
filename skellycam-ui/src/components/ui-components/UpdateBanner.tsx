import React from 'react';
import { useTranslation } from 'react-i18next';
import { useAutoUpdate } from '@/hooks/useAutoUpdate';

export const UpdateBanner: React.FC = () => {
    const { t } = useTranslation();
    const { status, version, progress, errorMessage, installUpdate } = useAutoUpdate();

    if (status === 'idle' || status === 'checking' || status === 'up-to-date') {
        return null;
    }

    if (status === 'error') {
        return (
            <div className="update-banner update-banner-error">
                <span className="text sm">{t('updateError')}: {errorMessage}</span>
            </div>
        );
    }

    if (status === 'downloading') {
        return (
            <div className="update-banner update-banner-info">
                <span className="text sm">{t('downloading')} {version && `v${version}`}</span>
                <div className="update-progress-track">
                    <div className="update-progress-fill" style={{ width: `${progress}%` }} />
                </div>
            </div>
        );
    }

    if (status === 'ready') {
        return (
            <div className="update-banner update-banner-success">
                <span className="text sm">{t('downloadComplete')} — v{version}</span>
                <button className="button sm" onClick={installUpdate}>
                    {t('restartToUpdate')}
                </button>
            </div>
        );
    }

    // status === 'available'
    return (
        <div className="update-banner update-banner-info">
            <span className="text sm">{t('updateAvailableMessage', { version })}</span>
        </div>
    );
};
