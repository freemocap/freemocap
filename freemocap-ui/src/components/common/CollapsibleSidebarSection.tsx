import React, {ReactNode, useCallback, useState} from "react";
import {useDragHandle} from "@/components/common/DragHandleContext";

interface CollapsibleSidebarSectionProps {
    icon: ReactNode;
    title: string;
    summaryContent?: ReactNode;
    primaryControl?: ReactNode;
    secondaryControls?: ReactNode;
    children: ReactNode;
    defaultExpanded?: boolean;
}

export const CollapsibleSidebarSection: React.FC<CollapsibleSidebarSectionProps> = ({
    icon,
    title,
    summaryContent,
    primaryControl,
    secondaryControls,
    children,
    defaultExpanded = false,
}) => {
    const [expanded, setExpanded] = useState(defaultExpanded);
    const dragHandle = useDragHandle();

    const handleToggle = useCallback(() => setExpanded((prev) => !prev), []);
    const handleControlClick = useCallback((e: React.MouseEvent) => e.stopPropagation(), []);

    return (
        <div className="bg-darkgray br-1 overflow-hidden">
            {/* Header row */}
            <div
                onClick={handleToggle}
                className="flex flex-row items-center gap-1 p-1"
                style={{
                    minHeight: 40,
                    cursor: 'pointer',
                    userSelect: 'none',
                    backgroundColor: 'var(--color-bg-elevated)',
                    paddingLeft: dragHandle ? 4 : 12,
                    paddingRight: 8,
                }}
            >
                {/* Drag handle */}
                {dragHandle && (
                    <div
                        {...dragHandle.attributes}
                        {...dragHandle.listeners}
                        onClick={(e) => e.stopPropagation()}
                        style={{ cursor: 'grab', opacity: 0.4, display: 'flex', alignItems: 'center', padding: '0 2px' }}
                    >
                        <span className="icon icon-size-20" style={{ backgroundImage: 'repeating-linear-gradient(transparent, transparent 2px, var(--gray-400) 2px, var(--gray-400) 3px)', backgroundSize: '4px 100%' }} />
                    </div>
                )}

                {/* Chevron */}
                <span className={`icon icon-size-20 ${expanded ? 'collapse-icon' : 'expand-icon'}`} style={{ transform: expanded ? 'rotate(0deg)' : 'rotate(-90deg)', flexShrink: 0 }} />

                {/* Section icon */}
                <span className="flex items-center" style={{ flexShrink: 0 }}>{icon}</span>

                {/* Title */}
                <span className="text bg text-white" style={{ flexShrink: 0 }}>{title}</span>

                {/* Summary */}
                {summaryContent && (
                    <div className="flex-1 flex flex-row items-center flex-end overflow-hidden" style={{ margin: '0 6px' }}>
                        {summaryContent}
                    </div>
                )}

                {/* Secondary controls */}
                {secondaryControls && (
                    <div onClick={handleControlClick} className="flex flex-row items-center gap-1">
                        {secondaryControls}
                    </div>
                )}

                {/* Primary control */}
                {primaryControl && (
                    <div onClick={handleControlClick} className="flex items-center" style={{ paddingRight: 4 }}>
                        {primaryControl}
                    </div>
                )}
            </div>

            {/* Detail panel */}
            {expanded && (
                <div className="bg-darkgray">
                    {children}
                </div>
            )}
        </div>
    );
};
