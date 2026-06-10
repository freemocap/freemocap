import React, { useEffect, useRef, useState } from 'react';
import clsx from 'clsx';
import ToggleComponent from '@/components/ui-components/ToggleComponent';
import SubactionHeader from '@/components/ui-components/SubactionHeader';
import ValueSelector from '@/components/ui-components/ValueSelector';
import ButtonSm from '@/components/ui-components/ButtonSm';
import IconButton from '@/components/ui-components/IconButton';
import { useServer } from '@/services/server/ServerContextProvider';
import { useTranslation } from 'react-i18next';
import { useAppDispatch, useAppSelector, selectCameras } from '@/store';
import { camerasConnectOrUpdate, detectCameras } from '@/store/slices/cameras/cameras-thunks';

interface CameraSettings { columns: number | null; }

interface CamerasViewSettingsOverlayProps {
    onSettingsChange: (settings: CameraSettings) => void;
    onResetLayout: () => void;
    /** When true, renders the trigger inline (no absolute positioning).
     *  The panel drops down using position:fixed anchored to the button. */
    inline?: boolean;
}

export const CamerasViewSettingsOverlay: React.FC<CamerasViewSettingsOverlayProps> = ({
    onSettingsChange,
    inline = false,
}) => {
    const { connectedCameraIds, isConnected } = useServer();
    const { t } = useTranslation();
    const dispatch = useAppDispatch();
    const cameras = useAppSelector(selectCameras);

    useEffect(() => {
        if (isConnected && cameras.length === 0) {
            dispatch(detectCameras({ filterVirtual: true }));
        }
    }, [isConnected, cameras.length, dispatch]);
    const [isOpen, setIsOpen] = useState<boolean>(false);
    const [isAuto, setIsAuto] = useState<boolean>(true);
    const [manualColumns, setManualColumns] = useState<number>(2);
    const [panelStyle, setPanelStyle] = useState<React.CSSProperties>({});
    const buttonRef = useRef<HTMLButtonElement>(null);

    const getAutoColumns = (total: number): number => {
        if (total <= 1) return 1;
        if (total <= 4) return 2;
        if (total <= 9) return 3;
        return 4;
    };
    const autoColumns = getAutoColumns(connectedCameraIds.length);

    const handleAutoToggle = (checked: boolean) => {
        setIsAuto(checked);
        onSettingsChange({ columns: checked ? null : manualColumns });
    };

    const handleColumnsChange = (value: number) => {
        setManualColumns(value);
        if (isAuto) setIsAuto(false);
        onSettingsChange({ columns: value });
    };

    const handleToggle = () => {
        if (!isOpen && inline && buttonRef.current) {
            const rect = buttonRef.current.getBoundingClientRect();
            setPanelStyle({
                position: 'fixed',
                top: rect.bottom + 4,
                right: window.innerWidth - rect.right,
                zIndex: 200,
            });
        }
        setIsOpen((prev) => !prev);
    };

    const panel = (
        <div
            className="settings-overlay-panel reveal slide-down bg-dark br-2 border-1 border-black elevated-sharp flex flex-col p-2 gap-1"
            style={inline ? panelStyle : undefined}
        >
            <SubactionHeader text={t("gridColumns")} />

            <ToggleComponent
                text={t("auto")}
                isToggled={isAuto}
                onToggle={handleAutoToggle}
            />

            <div className="gap-1 p-1 br-1 flex justify-content-space-between items-center h-25">
                <p className="text md text-gray text-nowrap">{t("columns")}</p>
                <ValueSelector
                    value={isAuto ? autoColumns : manualColumns}
                    min={1}
                    max={8}
                    unit="col"
                    onChange={handleColumnsChange}
                />
            </div>
        </div>
    );

    if (inline) {
        return (
            <>
                <IconButton
                    ref={buttonRef}
                    className="grid-settings-button icon-size-25"
                    icon={isOpen ? "close-icon" : "settings-icon"}
                    onClick={handleToggle}
                    tooltip={true}
                    tooltipText={isOpen ? t("closeSettings") : t("gridSettings")}
                    tooltipPosition="pos-bottom-right"
                />
                {isOpen && panel}
            </>
        );
    }

    return (
      <>
        <div className="mode-header live-mode w-full reveal fadeIn active-tools-header br-1-1 gap-1 p-1 flex-row flex flex-end">
          {/* <div className="all-actions-components flex flex-row">
            <div className="stream-actions-container flex flex-row gap-1 items-center">
              <ButtonSm
                text="Stream"
                iconClass="stream-icon"
                textColor="text-white"
                onClick={() => {}}
              />
            </div>
            <div className='configure-camera-action-container text-white text md text-align-left flex flex-row items-center gap-1'>
                   <p className='text-nowrap items-center flex flex-row flex-inline gap-1 text-gray'><span className='tag'>{connectedCameraIds.length}</span>Connected Cameras</p>
                   
                   <button className="button icon-button"
                        onClick={() => dispatch(camerasConnectOrUpdate())}>
                        <span className="icon icon-size-20 scan-icon" />
                    </button>
            </div>
          </div> */}
          <div className="settings-overlay-trigger"></div>
          <IconButton
            icon={isOpen ? "close-icon" : "grid2-icon"}
            onClick={handleToggle}
            tooltip={true}
            tooltipText={isOpen ? t("closeSettings") : t("gridSettings")}
            tooltipPosition="pos-bottom-right"
          />
        </div>
        {isOpen && panel}
      </>
    );
};
