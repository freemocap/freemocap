import React, { useState } from 'react';
import { useServer } from '@/services/server/ServerContextProvider';
import { useTranslation } from 'react-i18next';
import type { CameraSettings, LayoutDirection } from '@/pages/StreamingViewPage';

interface SettingsOverlayProps {
    settings: CameraSettings;
    onSettingsChange: (partial: Partial<CameraSettings>) => void;
    onResetLayout: () => void;
}

export const SettingsOverlay: React.FC<SettingsOverlayProps> = ({
    settings,
    onSettingsChange,
    onResetLayout,
}) => {
    const { connectedCameraIds } = useServer();
    const { t } = useTranslation();
    const [isOpen, setIsOpen] = useState<boolean>(false);
    const [isAuto, setIsAuto] = useState<boolean>(settings.columns === null);
    const [manualColumns, setManualColumns] = useState<number>(settings.columns ?? 2);

    const getAutoColumns = (total: number): number => {
        if (total <= 1) return 1;
        if (total <= 4) return 2;
        if (total <= 9) return 3;
        return 4;
    };

    const autoColumns = getAutoColumns(connectedCameraIds.length);

    const handleAutoChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        const checked = event.target.checked;
        setIsAuto(checked);
        onSettingsChange({ columns: checked ? null : manualColumns });
    };

    const handleColumnsChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        const value = parseInt(event.target.value);
        if (!isNaN(value) && value > 0) {
            setManualColumns(value);
            if (isAuto) setIsAuto(false);
            onSettingsChange({ columns: value });
        }
    };

    const handle3dViewToggle = (event: React.ChangeEvent<HTMLInputElement>) => {
        onSettingsChange({ show3dView: event.target.checked });
    };

    const handleLayoutDirectionChange = (newDirection: LayoutDirection) => {
        onSettingsChange({ layoutDirection: newDirection });
    };

    return (
        <>
            {/* Settings toggle button */}
            <div style={{ position: 'absolute', top: 16, right: 16, zIndex: 1000 }}>
                <button
                    className="button icon-button br-2 bg-middark elevated-sharp"
                    onClick={() => setIsOpen(!isOpen)}
                    title={isOpen ? t('closeSettings') : t('gridSettings')}
                >
                    <span className={`icon icon-size-20 ${isOpen ? 'close-icon' : 'settings-icon'}`} />
                </button>
            </div>

            {/* Settings panel */}
            {isOpen && (
                <div
                    className="bg-middark br-2 elevated-sharp flex flex-col gap-2 p-2"
                    style={{ position: 'absolute', top: 70, right: 16, zIndex: 999, minWidth: 260 }}
                >
                    {/* Grid columns */}
                    <div className="flex flex-col gap-1">
                        <div className="flex flex-row items-center gap-1">
                            <span className="icon grid4-icon icon-size-20" />
                            <p className="text bg text-white">{t('gridColumns')}</p>
                        </div>
                        <div className="flex flex-row items-center gap-2">
                            <label className="flex flex-row items-center gap-1">
                                <input
                                    type="checkbox"
                                    checked={isAuto}
                                    onChange={handleAutoChange}
                                    style={{ accentColor: 'var(--color-info)' }}
                                />
                                <span className="text sm text-gray">{t('auto')}</span>
                            </label>
                            <div className="input-with-unit flex-1">
                                <input
                                    type="number"
                                    className="input-field numeric-input text md"
                                    value={isAuto ? autoColumns : manualColumns}
                                    onChange={handleColumnsChange}
                                    min={1}
                                    step={1}
                                />
                                <span className="unit-label text sm text-gray">{t('columns')}</span>
                            </div>
                        </div>
                        <p className="text sm text-gray">
                            {isAuto ? `Auto-detected: ${autoColumns}` : 'Enter any positive number'}
                        </p>
                    </div>

                    <div style={{ height: 1, backgroundColor: 'var(--color-border-secondary)' }} />

                    {/* 3D viewport toggle */}
                    <div className="flex flex-col gap-1">
                        <div className="flex flex-row items-center gap-1">
                            <span className="icon icon-size-20 streaming-icon" />
                            <p className="text bg text-white">3D Viewport</p>
                        </div>
                        <label className="flex flex-row items-center gap-2">
                            <input
                                type="checkbox"
                                checked={settings.show3dView}
                                onChange={handle3dViewToggle}
                                style={{ accentColor: 'var(--color-info)' }}
                            />
                            <span className="text sm text-gray">{settings.show3dView ? 'Visible' : 'Hidden'}</span>
                        </label>
                    </div>

                    {/* Layout direction (only when 3D is on) */}
                    {settings.show3dView && (
                        <>
                            <div style={{ height: 1, backgroundColor: 'var(--color-border-secondary)' }} />
                            <div className="flex flex-col gap-1">
                                <p className="text bg text-white">Layout</p>
                                <div className="flex flex-row gap-1">
                                    <button
                                        className={`button sm flex-1 ${settings.layoutDirection === 'horizontal' ? 'primary' : 'secondary'}`}
                                        onClick={() => handleLayoutDirectionChange('horizontal')}
                                    >
                                        <p className="text sm">Side by side</p>
                                    </button>
                                    <button
                                        className={`button sm flex-1 ${settings.layoutDirection === 'vertical' ? 'primary' : 'secondary'}`}
                                        onClick={() => handleLayoutDirectionChange('vertical')}
                                    >
                                        <p className="text sm">Stacked</p>
                                    </button>
                                </div>
                            </div>
                        </>
                    )}
                </div>
            )}
        </>
    );
};
