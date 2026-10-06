import React from 'react';
import { useTranslation } from 'react-i18next';
import { useAutoUpdate } from '@/hooks/useAutoUpdate';
import { EXTERNAL_URLS } from '@/constants/external-urls';

const bannerStyle: React.CSSProperties = {
    position: 'fixed',
    left: 0,
    right: 0,
    bottom: 0,
    zIndex: 250,
    borderTop: '1px solid var(--color-bg-elevated)',
};

const availableBannerStyle: React.CSSProperties = {
    ...bannerStyle,
    backgroundColor: '#cf563d',
    color: '#ffffff',
    justifyContent: 'center',
    padding: '8px 44px',
    borderTop: '1px solid rgba(241, 0, 0, 0.2)',
};

const upToDateBannerStyle: React.CSSProperties = {
    ...bannerStyle,
    backgroundColor: '#3f7d5a',
    color: '#ffffff',
    justifyContent: 'center',
    padding: '8px 44px',
};

const dismissButtonStyle: React.CSSProperties = {
    position: 'absolute',
    right: '12px',
    width: '28px',
    height: '28px',
    padding: 0,
    border: 'none',
    borderRadius: '4px',
    background: 'transparent',
    color: 'inherit',
    fontSize: '20px',
    lineHeight: 1,
    cursor: 'pointer',
};

export const UpdateBanner: React.FC = () => {
    const { t } = useTranslation();
    const {
        status,
        version,
        progress,
        errorMessage,
        installUpdate,
        dismissUpdate,
    } = useAutoUpdate();

    if (status === 'idle' || 
        status === 'checking') {
        return null;
    }
    
    if (status === 'up-to-date') {
        return (
            <div
                className="update-banner"
                style={upToDateBannerStyle}
            >
                <span
                    className="text sm"
                    style={{ textAlign: 'center' }}
                >
                    <strong>
                        FreeMoCap {version} is up to date
                    </strong>
                </span>
            </div>
        );
    }


    if (status === 'error') {
        return (
            <div
                className="update-banner update-banner-error"
                style={bannerStyle}
            >
                <span className="text sm">
                    {t('updateError')}: {errorMessage}
                </span>
            </div>
        );
    }

    if (status === 'downloading') {
        return (
            <div
                className="update-banner update-banner-info"
                style={bannerStyle}
            >
                <span className="text sm">
                    {t('downloading')} {version && `v${version}`}
                </span>

                <div className="update-progress-track">
                    <div
                        className="update-progress-fill"
                        style={{ width: `${progress}%` }}
                    />
                </div>
            </div>
        );
    }

    if (status === 'ready') {
        return (
            <div
                className="update-banner update-banner-success"
                style={bannerStyle}
            >
                <span className="text sm">
                    {t('downloadComplete')} — v{version}
                </span>

                <button
                    className="button sm"
                    onClick={installUpdate}
                >
                    {t('restartToUpdate')}
                </button>
            </div>
        );
    }

    return (
        <div
            className="update-banner"
            style={availableBannerStyle}
        >
            <span
                className="text sm"
                style={{ textAlign: 'center' }}
            >
                <strong>
                    FreeMoCap {version} is available
                </strong>
                {' — '}
                Download it at:{' '}
                <a
                    href={EXTERNAL_URLS.DOWNLOADS}
                    target="_blank"
                    rel="noreferrer"
                    style={{
                        color: 'inherit',
                        fontWeight: 600,
                        textDecoration: 'underline',
                    }}
                >
                    FreeMoCap.org
                </a>
            </span>

            <button
                onClick={dismissUpdate}
                aria-label="Hide this update notification"
                title="Hide until the next update"
                style={dismissButtonStyle}
            >
                ×
            </button>
        </div>
    );
};