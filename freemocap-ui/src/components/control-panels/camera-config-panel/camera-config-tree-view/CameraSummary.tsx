import React from "react";
import {useTranslation} from "react-i18next";

interface CameraSummaryProps {
    cameraCount: number;
    connectedCount: number;
}

export const CameraSummary: React.FC<CameraSummaryProps> = ({
    cameraCount,
    connectedCount,
}) => {
    const {t} = useTranslation();
    if (cameraCount === 0) {
        return (
            <span className="text sm text-gray text-nowrap" style={{fontWeight: 500}}>
                {t("noCamerasConnected")}
            </span>
        );
    }

    return (
        <span className="tag text sm">
            {connectedCount > 0
                ? t("camera.connectedCount", {count: connectedCount})
                : t("camera.availableCount", {count: cameraCount})}
        </span>
    );
};
