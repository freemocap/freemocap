import React from 'react';
import {ROTATION_DEGREE_LABELS, ROTATION_OPTIONS, RotationValue} from '@/store/slices/cameras/cameras-types';
import {useTranslation} from 'react-i18next';

interface CameraConfigRotationProps {
    rotation?: RotationValue;
    onChange: (rotation: RotationValue) => void;
}

export const CameraConfigRotation: React.FC<CameraConfigRotationProps> = ({
    rotation = -1,
    onChange
}) => {
    const {t} = useTranslation();

    return (
        <div title={t("selectCameraRotation")}>
            <div className="flex flex-row gap-1 flex-wrap">
                {ROTATION_OPTIONS.map((option: RotationValue) => (
                    <button
                        key={option}
                        className={`button sm${rotation === option ? ' primary' : ' secondary'}`}
                        onClick={() => onChange(option)}
                        aria-label={t("cameraRotation")}
                        style={{padding: '2px 8px', fontSize: 11}}
                    >
                        {ROTATION_DEGREE_LABELS[option]}
                    </button>
                ))}
            </div>
        </div>
    );
};
