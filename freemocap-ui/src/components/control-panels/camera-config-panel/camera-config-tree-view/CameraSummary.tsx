import React from "react";

interface CameraSummaryProps {
    cameraCount: number;
    connectedCount: number;
}

export const CameraSummary: React.FC<CameraSummaryProps> = ({
    cameraCount,
    connectedCount,
}) => {
    if (cameraCount === 0) {
        return (
            <span className="text sm text-gray text-nowrap" style={{fontWeight: 500}}>
                No cameras
            </span>
        );
    }

    return (
        <span className="tag text sm">
            {connectedCount > 0 ? `${connectedCount} connected` : `${cameraCount} available`}
        </span>
    );
};
