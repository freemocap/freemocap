import React, { useState } from "react";

interface PipelineStageTreeItemProps {
    itemId: string;
    label: string;
    checked: boolean;
    indeterminate?: boolean;
    onToggle: (newValue: boolean) => void;
    disabled?: boolean;
    disabledReason?: string;
    summaryWhenCollapsed?: string;
    isExpanded?: boolean;
    children?: React.ReactNode;
}

export const RealtimePipelineStageTreeItem: React.FC<PipelineStageTreeItemProps> = ({
    itemId,
    label,
    checked,
    indeterminate = false,
    onToggle,
    disabled = false,
    disabledReason,
    summaryWhenCollapsed,
    children,
}) => {
    const [expanded, setExpanded] = useState(false);

    const handleCheckboxClick = (e: React.MouseEvent) => {
        e.stopPropagation();
        if (!disabled) onToggle(!(checked || indeterminate));
    };

    const checkboxEl = (
        <input
            type="checkbox"
            checked={checked}
            ref={(el) => { if (el) el.indeterminate = indeterminate; }}
            disabled={disabled}
            onMouseDown={(e) => e.stopPropagation()}
            onClick={handleCheckboxClick}
            onChange={() => {}}
            style={{ accentColor: 'var(--color-info)', flexShrink: 0 }}
        />
    );

    return (
        <div className="flex flex-col">
            <div
                className="flex flex-row items-center gap-1 p-1"
                style={{ minHeight: 32, cursor: children ? 'pointer' : 'default' }}
                onClick={() => children && setExpanded(v => !v)}
            >
                {disabled && disabledReason ? (
                    <span title={disabledReason}>{checkboxEl}</span>
                ) : (
                    checkboxEl
                )}
                <p className="text sm flex-1" style={{ color: disabled ? 'var(--color-text-disabled)' : 'var(--color-text-primary)' }}>
                    {label}
                </p>
                {!expanded && summaryWhenCollapsed && (
                    <span className="tag text sm" style={{ height: 18, fontSize: 10 }}>{summaryWhenCollapsed}</span>
                )}
                {children && (
                    <span className="icon icon-size-20 collapse-icon" style={{ transform: expanded ? 'rotate(0deg)' : 'rotate(-90deg)' }} />
                )}
            </div>
            {expanded && children && (
                <div className="pl-2">{children}</div>
            )}
        </div>
    );
};
