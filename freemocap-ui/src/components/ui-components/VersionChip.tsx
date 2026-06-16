import React, { useEffect, useRef, useState } from 'react';
import clsx from 'clsx';
import { useTranslation } from 'react-i18next';
import { useAppVersion } from '@/hooks/useAppVersion';
import { useAutoUpdate } from '@/hooks/useAutoUpdate';
import { EXTERNAL_URLS } from '@/constants/external-urls';
import ButtonSm from '@/components/ui-components/ButtonSm';

interface VersionChipProps {
    variant?: 'compact' | 'full';
    className?: string;
    style?: React.CSSProperties;
}

type ToastType = 'success' | 'error' | 'info';

export const VersionChip: React.FC<VersionChipProps> = ({ variant = 'full', className, style }) => {
    const { t } = useTranslation();
    const version = useAppVersion();
    const { status, version: updateVersion, errorMessage, checkForUpdate } = useAutoUpdate();

    const isChecking = status === 'checking';
    const prevStatusRef = useRef(status);

    const [showSuccess, setShowSuccess] = useState(false);
    const [toast, setToast] = useState<{ message: string; type: ToastType } | null>(null);

    useEffect(() => {
        const prev = prevStatusRef.current;
        prevStatusRef.current = status;
        if (prev !== 'checking') return;

        if (status === 'up-to-date') {
            setToast({ message: t('upToDate'), type: 'success' });
            setShowSuccess(true);
            setTimeout(() => setShowSuccess(false), 3000);
        } else if (status === 'available') {
            setToast({ message: t('updateAvailableMessage', { version: updateVersion }), type: 'info' });
        } else if (status === 'error') {
            setToast({
                message: errorMessage ? `${t('updateError')}: ${errorMessage}` : t('updateError'),
                type: 'error',
            });
        }
    }, [status, updateVersion, errorMessage, t]);

    useEffect(() => {
        if (!toast) return;
        const timer = setTimeout(() => setToast(null), 4000);
        return () => clearTimeout(timer);
    }, [toast]);

    if (!version) return null;

    return (
        <div className={`version-button-container flex-start flex flex-col items-center gap-0${className ? ` ${className}` : ''}`} style={style}>
            <ButtonSm
                text={`v${version}`}
                onClick={checkForUpdate}
                textColor="text-gray"
                disabled={isChecking}
                tooltip={true}
                tooltipText={t('checkForUpdates')}
                tooltipPosition="pos-right"
                className={clsx("version-badge", showSuccess && "success")}
                iconClass={clsx(
                    "icon icon-size-20",
                    isChecking
                        ? "updateAvailable-icon"
                        : showSuccess
                        ? "upToDate-icon"
                        : "checkUpdate-icon"
                )}
            />
            <ButtonSm
                text="Releases"
                onClick={() => window.open(EXTERNAL_URLS.GITHUB_RELEASES, '_blank')}
                textColor="text-gray"
                className="externallink"
                tooltip={true}
                tooltipText="view all releases on GitHub"
                tooltipPosition="pos-right"
            />
            {toast && (
                <div className={clsx("toast-notification", toast.type)}>
                    <p className="text sm">{toast.message}</p>
                </div>
            )}
        </div>
    );
};
