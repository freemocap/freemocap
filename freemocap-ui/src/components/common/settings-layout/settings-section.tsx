import {type ReactNode, useCallback, useId, useState} from 'react';
import './settings-layout.css';

interface SettingsSectionProps {
    title: string;
    /** Stated in the header whether the section is open or closed, so collapsing
     *  summarises rather than hides. Build it from SettingsSummaryChip. */
    summary?: ReactNode;
    defaultExpanded?: boolean;
    expanded?: boolean;
    onExpandedChange?: (expanded: boolean) => void;
    /** A section rendered inside another section's body. */
    nested?: boolean;
    children: ReactNode;
}

export default function SettingsSection({
    title,
    summary,
    defaultExpanded = true,
    expanded: controlledExpanded,
    onExpandedChange,
    nested = false,
    children,
}: SettingsSectionProps) {
    const [internalExpanded, setInternalExpanded] = useState(defaultExpanded);
    const expanded = controlledExpanded ?? internalExpanded;
    const bodyId = useId();

    const toggleExpanded = useCallback(() => {
        if (controlledExpanded === undefined) setInternalExpanded(!expanded);
        onExpandedChange?.(!expanded);
    }, [controlledExpanded, expanded, onExpandedChange]);

    return <section className={`settings-section${nested ? ' settings-section-nested' : ''}`} aria-label={title}>
        <button type="button" className="settings-section-header" aria-expanded={expanded}
            aria-controls={bodyId} onClick={toggleExpanded}>
            <span className="settings-section-chevron"/>
            <h2 className="settings-section-title">{title}</h2>
            {summary && <span className="settings-section-summary">{summary}</span>}
        </button>
        <div id={bodyId} className="settings-section-body" hidden={!expanded}>{children}</div>
    </section>;
}
