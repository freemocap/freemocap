import React from 'react';
import SegmentedControl from '@/components/ui-components/SegmentedControl';
import { ROTATION_DEGREE_LABELS, ROTATION_OPTIONS, RotationValue } from '@/store/slices/cameras/cameras-types';
import { useTranslation } from 'react-i18next';

interface CameraConfigRotationProps {
    rotation?: RotationValue;
    onChange: (rotation: RotationValue) => void;
}

export const CameraConfigRotation: React.FC<CameraConfigRotationProps> = ({
    rotation = -1,
    onChange,
}) => {
    const { t } = useTranslation();

    return (
        <div title={t("selectCameraRotation")}>
            <SegmentedControl
                options={ROTATION_OPTIONS.map((o: RotationValue) => ({
                    label: ROTATION_DEGREE_LABELS[o],
                    value: String(o),
                }))}
                value={String(rotation)}
                onChange={(v) => onChange(Number(v) as RotationValue)}
                size="sm"
                className="segmented-control-sm"
            />
        </div>
    );
};
