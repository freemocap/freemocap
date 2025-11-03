import React from "react";
import { TreeItem } from "@mui/x-tree-view/TreeItem";
import { useAppDispatch } from "@/store";
import { cameraDesiredConfigUpdated } from "@/store/slices/cameras/cameras-slice";
import { Camera, CameraConfig } from "@/store/slices/cameras/cameras-types";
import {CameraConfigPanel} from "@/components/camera-config-tree-view/camera-config-panel/CameraConfigPanel";

interface CameraConfigTreeSectionProps {
    camera: Camera;
}

export const CameraConfigTreeSection: React.FC<CameraConfigTreeSectionProps> = ({
                                                                                    camera,
                                                                                }) => {
    const dispatch = useAppDispatch();

    const handleConfigChange = (newConfig: CameraConfig): void => {
        dispatch(
            cameraDesiredConfigUpdated({
                cameraId: camera.id,
                config: newConfig,
            })
        );
    };

    return (
        <TreeItem
            itemId={`camera-${camera.id}-config`}
            label={
                <CameraConfigPanel
                    config={camera.desiredConfig}
                    onConfigChange={handleConfigChange}
                    isExpanded={true}
                />
            }
        />
    );
};
