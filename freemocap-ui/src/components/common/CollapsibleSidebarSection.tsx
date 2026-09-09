import React, {ReactNode, useCallback, useState} from "react";

interface CollapsibleSidebarSectionProps {
    icon: ReactNode;
    title: string;
    summaryContent?: ReactNode;
    primaryControl?: ReactNode;
    secondaryControls?: ReactNode;
    children: ReactNode;
    defaultExpanded?: boolean;
    keepMounted?: boolean;
    expanded?: boolean;
    onExpandedChange?: (expanded: boolean) => void;
}

export const CollapsibleSidebarSection: React.FC<CollapsibleSidebarSectionProps> = ({
    icon,
    title,
    summaryContent,
    primaryControl,
    secondaryControls,
    children,
    defaultExpanded = false,
    keepMounted = false,
    expanded: controlledExpanded,
    onExpandedChange,
}) => {
    const [internalExpanded, setExpanded] = useState(defaultExpanded);
    const expanded = controlledExpanded ?? internalExpanded;

    const handleToggle = useCallback(() => {
        setExpanded(!expanded);
        onExpandedChange?.(!expanded);
    }, [expanded, onExpandedChange]);
    const handleControlClick = useCallback((e: React.MouseEvent) => e.stopPropagation(), []);

    return (
        <div className="collapsible-sidebar-section bg-darkgray br-1 overflow-hidden hidden motion-caption-left-side-bar">
            {/* Header row */}
            <div
                role="button"
                tabIndex={0}
                aria-expanded={expanded}
                onKeyDown={event => {
                    if (event.target === event.currentTarget && (event.key === 'Enter' || event.key === ' ')) {
                        event.preventDefault(); handleToggle();
                    }
                }}
                onClick={handleToggle}
                className="collapsible-sidebar-header flex flex-row items-center gap-1 p-1 pr-2"
            >
                {/* Chevron */}
                <span className={`collapsible-sidebar-chevron icon icon-size-20 flex-shrink-0 ${expanded ? 'collapse-icon' : 'expand-icon'}`} />

                {/* Section icon */}
                <span className="flex items-center flex-shrink-0">{icon}</span>

                {/* Title */}
                <span className="text bg text-white flex-shrink-0">{title}</span>

                {/* Summary */}
                {summaryContent && (
                    <div className="collapsible-sidebar-summary flex-1 flex flex-row items-center flex-end overflow-hidden">
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
                    <div onClick={handleControlClick} className="flex items-center pr-1">
                        {primaryControl}
                    </div>
                )}
            </div>

            {/* Detail panel */}
            {(expanded || keepMounted) && (
                <div className="bg-darkgray" hidden={!expanded}>
                    {children}
                </div>
            )}
        </div>
    );
};
