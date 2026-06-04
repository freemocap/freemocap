import React, {useState} from "react";
import {CameraTreeItem} from "./CameraTreeItem";
import {Camera} from "@/store/slices/cameras/cameras-types";

interface CameraGroupTreeItemProps {
    groupId: string;
    title: string;
    cameras: Camera[];
    icon?: React.ReactNode;
    expandedItems?: string[];
}

export const CameraGroupTreeItem: React.FC<CameraGroupTreeItemProps> = ({
    groupId,
    title,
    cameras,
    icon,
    expandedItems,
}) => {
    const [expanded, setExpanded] = useState(true);

    return (
        <div>
            <div
                className="flex flex-row items-center gap-1 p-1"
                style={{cursor: 'pointer', userSelect: 'none'}}
                onClick={() => setExpanded((prev) => !prev)}
            >
                <span className={`icon icon-size-20 ${expanded ? 'collapse-icon' : 'expand-icon'}`}
                    style={{transform: expanded ? 'rotate(0deg)' : 'rotate(-90deg)', flexShrink: 0}} />
                {icon && <span className="flex items-center">{icon}</span>}
                <span className="text sm text-white" style={{marginLeft: 4}}>
                    {title} ({cameras.length})
                </span>
            </div>
            {expanded && (
                <div>
                    {cameras.map((camera: Camera) => (
                        <CameraTreeItem
                            key={camera.id}
                            camera={camera}
                            isExpanded={expandedItems?.includes(`camera-${camera.id}`)}
                        />
                    ))}
                </div>
            )}
        </div>
    );
};
