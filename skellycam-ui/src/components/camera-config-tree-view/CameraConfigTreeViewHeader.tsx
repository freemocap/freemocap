import React from "react";
import clsx from "clsx";
import ButtonSm from "@/components/ui-components/ButtonSm";
import { useAppDispatch, useAppSelector } from "@/store";
import { selectSelectedCameras } from "@/store/slices/cameras/cameras-selectors";
import {
    closeCameras,
    camerasConnectOrUpdate,
    detectCameras,
    pauseUnpauseCameras,
} from "@/store/slices/cameras/cameras-thunks";
import { savedSettingsCleared } from "@/store/slices/cameras/cameras-slice";
import { useTranslation } from 'react-i18next';
import { useRecordingGuard } from '@/components/RecordingGuardProvider';

interface CameraConfigTreeViewHeaderProps {
    cameraCount: number;
    isLoading: boolean;
    isPaused: boolean;
    hasSelectedCameras: boolean;
}

export const CameraConfigTreeViewHeader: React.FC<CameraConfigTreeViewHeaderProps> = ({
    cameraCount, isLoading, isPaused,
}) => {
    const dispatch = useAppDispatch();
    const { t } = useTranslation();
    const { requestGuardedAction } = useRecordingGuard();
    const [isActionInProgress, setIsActionInProgress] = React.useState(false);

    const wrap = (fn: () => Promise<any>) => () => {
        setIsActionInProgress(true);
        fn().catch(console.error).finally(() => setIsActionInProgress(false));
    };

    return (
        <div className="camera-tree-header" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center gap-1 flex-1">
                <span className="icon stream-icon icon-size-20" />
                <p className="text bg text-white flex-1">{t('camerasCount', { count: cameraCount })}</p>
            </div>

            <div className="flex gap-1">
                <ButtonSm
                    text=""
                    iconClass="stream-icon"
                    textColor="text-white"
                    title={t("connectCameras")}
                    onClick={() => requestGuardedAction('Stop Recording & Update Camera Config', wrap(() => dispatch(camerasConnectOrUpdate()).unwrap()))}
                />
                <ButtonSm
                    text=""
                    iconClass={isPaused ? "stream-icon" : "record-icon"}
                    textColor="text-white"
                    title={isPaused ? t("resumeStreaming") : t("pauseStreaming")}
                    onClick={() => requestGuardedAction('Stop Recording & Pause Cameras', wrap(() => dispatch(pauseUnpauseCameras()).unwrap()))}
                />
                <ButtonSm
                    text=""
                    iconClass="close-icon"
                    textColor="text-white"
                    title={t("closeAllCameras")}
                    onClick={() => requestGuardedAction('Stop Recording & Close Cameras', wrap(() => dispatch(closeCameras()).unwrap()))}
                />
                <ButtonSm
                    text=""
                    iconClass={isLoading || isActionInProgress ? "loader-icon" : "rotate-icon"}
                    textColor="text-white"
                    title={t("detectCameras")}
                    onClick={() => requestGuardedAction('Stop Recording & Detect Cameras', wrap(() => dispatch(detectCameras({ filterVirtual: true })).unwrap()))}
                />
                <ButtonSm
                    text=""
                    iconClass="minus-icon"
                    textColor="text-white"
                    title={t("clearCameraSettings")}
                    onClick={() => requestGuardedAction('Stop Recording & Clear Camera Settings', () => dispatch(savedSettingsCleared()))}
                />
            </div>
        </div>
    );
};
