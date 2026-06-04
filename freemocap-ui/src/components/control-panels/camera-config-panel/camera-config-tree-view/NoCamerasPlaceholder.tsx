import React from "react";
import {useTranslation} from "react-i18next";

export const NoCamerasPlaceholder: React.FC = () => {
    const { t } = useTranslation();
    return (
        <div className="flex flex-col items-center p-3" style={{textAlign: "center"}}>
            <p className="text md text-gray">{t('noCamerasDetected')}</p>
            <p className="text sm text-gray" style={{marginTop: 4}}>{t('clickRefreshToScan')}</p>
        </div>
    );
};
