import {type ReactNode, useId, useState} from 'react';
import {BlenderToggle, ExportsToggle, StageToggle} from './processing-run-controls';
import type {ProcessingSection} from './processing-sections';

/** One section of the list view: its switch (its own when it brings one), number, title and state chips, then its settings. */
export default function StageSection<Id extends string>({section, playback, children}: {
    section: ProcessingSection<Id>; playback: boolean; children: ReactNode;
}) {
    const [expanded, setExpanded] = useState(true);
    const bodyId = useId();
    return <section className="settings-section mp-section" aria-label={section.title}>
        <div className="settings-section-header mp-section-header">
            {section.toggle !== undefined ? section.toggle : playback && section.stage && <StageToggle stage={section.stage} title={section.title}/>}
            <button type="button" className="mp-section-title" aria-expanded={expanded} aria-controls={bodyId}
                disabled={section.content === null} onClick={() => setExpanded(!expanded)}>
                {section.content !== null && <span className="settings-section-chevron"/>}
                {section.number !== null && <span className="mp-outline-number">{section.number}</span>}
                <h2 className="settings-section-title">{section.title}</h2>
            </button>
            {section.summary && <span className="settings-section-summary">{section.summary}</span>}
            {section.id === 'blender' && <BlenderToggle/>}
            {section.id === 'exports' && <ExportsToggle/>}
        </div>
        {section.content !== null && <div id={bodyId} className="settings-section-body" hidden={!expanded}>{children}</div>}
    </section>;
}
