import React from "react";
import { useTranslation } from "react-i18next";

export const NoCamerasPlaceholder: React.FC = () => {
    const { t } = useTranslation();
    return (
        <div className="flex flex-col items-center gap-1 p-3">
            <p className="text bg text-gray">{t('noCamerasDetected')}</p>
            <p className="text sm text-darkgray">{t('clickRefreshToScan')}</p>
        </div>
    );
};
