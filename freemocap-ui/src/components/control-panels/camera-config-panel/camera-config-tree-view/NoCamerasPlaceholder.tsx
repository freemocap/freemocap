import React from "react";
import {useTranslation} from "react-i18next";

export const NoCamerasPlaceholder: React.FC = () => {
    const { t } = useTranslation();
    return (
        <div className="flex flex-col items-center p-3 text-center">
            <p className="text md text-gray">{t('noCamerasDetected')}</p>
            <p className="text sm text-gray mt-1">{t('clickRefreshToScan')}</p>
        </div>
    );
};
