import React, { useState } from "react";
import { CameraTreeItem } from "./CameraTreeItem";
import { Camera } from "@/store/slices/cameras/cameras-types";

interface CameraGroupTreeItemProps {
    groupId: string;
    title: string;
    cameras: Camera[];
    icon?: React.ReactNode;
    expandedItems?: string[];
}

export const CameraGroupTreeItem: React.FC<CameraGroupTreeItemProps> = ({
    title, cameras,
}) => {
    const [expanded, setExpanded] = useState(true);

    return (
        <div className="flex flex-col">
            <div
                className="camera-section-header toggle-button gap-1 p-1 br-1 flex justify-content-space-between items-center h-25"
                onClick={() => setExpanded(prev => !prev)}
            >
                <p className="text bg text-gray">{title} ({cameras.length})</p>
                <span className={`icon icon-size-20 ${expanded ? 'close-icon' : 'dropdown-icon'}`} />
            </div>

            {expanded && (
                <div className="flex flex-col reveal slide-down">
                    {cameras.map((camera: Camera) => (
                        <CameraTreeItem key={camera.id} camera={camera} />
                    ))}
                </div>
            )}
        </div>
    );
};
