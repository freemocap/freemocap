import React, { useEffect, useState, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useElectronIPC } from '@/services';
import { useServer } from '@/services/server/ServerContextProvider';
import { LanguageSwitcher } from '@/components/languages/LanguageSwitcher';
import { VersionChip } from '@/components/ui-components/VersionChip';
import { useAppDispatch } from '@/store';
import { camerasConnectOrUpdate } from '@/store/slices/cameras/cameras-thunks';
import { EXTERNAL_URLS } from '@/constants/external-urls';
import ButtonSm from '@/components/ui-components/ButtonSm';
import ButtonCard from '@/components/ui-components/ButtonCard';
import IconButton from '@/components/ui-components/IconButton';
import ToggleComponent from '@/components/ui-components/ToggleComponent';

interface WelcomeModalProps {
    open: boolean;
    onClose: () => void;
}

export const WelcomeModal: React.FC<WelcomeModalProps> = ({ open, onClose }) => {
    const { t } = useTranslation();
    const navigate = useNavigate();
    const dispatch = useAppDispatch();
    const [telemetryEnabled, setTelemetryEnabled] = useState<boolean>(true);
    const [telemetryLoaded, setTelemetryLoaded] = useState<boolean>(false);
    const { isElectron, api } = useElectronIPC();
    const { connectedCameraIds } = useServer();
    const prevCountRef = useRef(connectedCameraIds.length);

    // Close automatically when cameras first connect
    useEffect(() => {
        if (!open) return;
        const prevCount = prevCountRef.current;
        const currentCount = connectedCameraIds.length;
        if (prevCount === 0 && currentCount > 0) onClose();
        prevCountRef.current = currentCount;
    }, [connectedCameraIds, open, onClose]);

    useEffect(() => {
        const loadTelemetryPref = async (): Promise<void> => {
            try {
                if (isElectron && api) {
                    const enabled = await api.telemetry.getEnabled.query();
                    setTelemetryEnabled(enabled);
                }
            } catch (error) {
                console.error('Failed to load telemetry preference:', error);
            } finally {
                setTelemetryLoaded(true);
            }
        };
        loadTelemetryPref();
    }, [isElectron, api]);

    useEffect(() => {
        if (!open) return;
        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.key === 'Escape') onClose();
        };
        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [open, onClose]);

    const handleTelemetryToggle = useCallback(async (checked: boolean) => {
        setTelemetryEnabled(checked);
        try {
            if (isElectron && api) {
                await api.telemetry.setEnabled.mutate({ enabled: checked });
            }
        } catch (error) {
            console.error('Failed to save telemetry preference:', error);
        }
    }, [isElectron, api]);

    const handleGoToCameras = useCallback(() => {
        navigate('/streaming');
        onClose();
        dispatch(camerasConnectOrUpdate());
    }, [navigate, onClose, dispatch]);

    const handleGoToPlayback = useCallback(() => {
        navigate('/playback');
        onClose();
    }, [navigate, onClose]);

    if (!open) return null;

    return (
        <div
            className="splash-overlay inset-0 reveal fadeIn"
            style={{ position: "fixed", zIndex: 100 }}
            onClick={onClose}
        >
            <div
                className="pos-rel splash-modal fade reveal main-container br-2 flex flex-col p-1 bg-dark border-1 border-black"
                onClick={(e) => e.stopPropagation()}
            >
                <div className="overflow-hidden flex-1 bg-middark br-1 flex flex-row gap-3 p-2">
                    <div className="icon-button-holder flex flex-row pos-abs top-4 right-4 z-2">
                        <IconButton
                            icon="icon close-icon icon-size-20"
                            onClick={onClose}
                            className="pos-abs top-0 right-0 tertiary"
                        />
                    </div>

                    {/* Left column — splash art */}
                    <div className="splash-image-container flex flex-1 pos-rel">
                        <div className="pos-abs bottom-10 left-10 fit-content">
                            <VersionChip variant="compact" />
                        </div>
                    </div>

                    {/* Right column — content */}
                    <div className="splash-action-group flex-1 flex flex-col gap-1 p-1 justify-content-space-between">
                        {/* Top actions */}
                        <div className="flex flex-col pl-2 pr-2 pt-2 pb-0 mb-0">
                            <h1 className="title flex flex-col gap-1">
                                <span className="text-white">{t('welcomeTitle')}</span>
                                <span className="text-gray">{t('welcomeSubtitle')}</span>
                            </h1>

                            {/* Primary navigation cards */}
                            <div className="flex gap-2 mt-3">
                                <ButtonCard
                                    text={t('connectToCameras')}
                                    iconClass="live-icon icon-size-42"
                                    onClick={handleGoToCameras}
                                />
                                <ButtonCard
                                    text={t('videoPlayback')}
                                    iconClass="importVideos-icon icon-size-42"
                                    onClick={handleGoToPlayback}
                                />
                            </div>

                            {/* Telemetry toggle */}
                            {telemetryLoaded && (
                                <div className="mt-2">
                                    <ToggleComponent
                                        text={t('sendAnonymousPings')}
                                        isToggled={telemetryEnabled}
                                        onToggle={handleTelemetryToggle}
                                    />
                                </div>
                            )}

                            <div className="pos-abs top-10 left-10 fit-content">
                                <LanguageSwitcher />
                            </div>
                        </div>

                        {/* Bottom links */}
                        <div className="splash-bottom-links flex flex-col gap-1 pl-1">
                            <ButtonSm
                                iconClass="learn-icon"
                                text={t('documentation')}
                                rightSideIcon="externallink"
                                textColor="text-gray"
                                onClick={() => window.open(EXTERNAL_URLS.DOCS, '_blank')}
                            />
                            <ButtonSm
                                iconClass=""
                                text={t('roadmap')}
                                rightSideIcon="externallink"
                                textColor="text-gray"
                                onClick={() => window.open(EXTERNAL_URLS.ROADMAP, '_blank')}
                            />
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};
