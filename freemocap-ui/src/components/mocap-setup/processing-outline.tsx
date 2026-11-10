// The window's outline: every section in pipeline order with its switch, always on the left. A section may bring
// its own switch and state, items it switches one by one, and key setting rows for an outline that shows controls.
import {Fragment, type ReactNode} from 'react';
import type {ResumeStage} from '@/services/recording/posthoc-processing';
import {BlenderToggle, ExportsToggle, StageToggle, useStageOutcome} from './processing-run-controls';
import type {ProcessingSection} from './processing-sections';

function StageOutcome({stage}: {stage: ResumeStage}) {
    const outcome = useStageOutcome(stage);
    return <span className="mp-outline-state">{outcome}</span>;
}

export default function ProcessingOutline<Id extends string>({sections, active, playback, states, onPick,
    afterTitle = 'After processing', label = 'Mocap processing sections', controls = false}: {
    sections: ProcessingSection<Id>[];
    active: Id | null;
    playback: boolean;
    /** Run state per section while a run is shown, else null. */
    states: Partial<Record<Id, string>> | null;
    onPick: (id: Id) => void;
    /** The heading of the trailing group. */
    afterTitle?: string;
    /** The outline's accessible name. */
    label?: string;
    /** Whether each section's and item's key setting rows show under its row, as in a quick menu. */
    controls?: boolean;
}) {
    const keyRows = (quick: ReactNode) => controls && quick ? <li className="mp-outline-controls settings-layout">{quick}</li> : null;
    const rows = (section: ProcessingSection<Id>) => <Fragment key={section.id}>
        <li className={`mp-outline-row${active === section.id ? ' active' : ''}`}>
            {section.toggle !== undefined ? section.toggle : playback && section.stage && <StageToggle stage={section.stage} title={section.title}/>}
            <button type="button" className="mp-outline-link" aria-label={section.title} onClick={() => onPick(section.id)}>
                {section.number !== null && <span className="mp-outline-number">{section.number}</span>}
                {section.title}
            </button>
            {section.state !== undefined ? <span className="mp-outline-state">{section.state}</span>
                : states?.[section.id] ? <span className={`mp-outline-state ${states[section.id]}`}>{states[section.id]}</span>
                    : playback && section.stage ? <StageOutcome stage={section.stage}/>
                        : section.id === 'blender' ? <BlenderToggle/> : section.id === 'exports' ? <ExportsToggle/> : null}
        </li>
        {keyRows(section.quick)}
        {section.items?.map(item => <Fragment key={item.id}>
            <li className="mp-outline-row mp-outline-item">
                {item.toggle}
                <button type="button" className="mp-outline-link" aria-label={item.title} onClick={() => onPick(section.id)}>{item.title}</button>
                {item.state !== undefined && <span className="mp-outline-state">{item.state}</span>}
            </li>
            {keyRows(item.quick)}
        </Fragment>)}
    </Fragment>;
    const after = (section: ProcessingSection<Id>): boolean => section.after ?? (section.id === 'blender' || section.id === 'exports');
    return <nav className="mp-outline" aria-label={label}>
        <span className="mp-outline-heading">Pipeline</span>
        <ul>{sections.filter(section => !after(section)).map(rows)}</ul>
        <span className="mp-outline-heading">{afterTitle}</span>
        <ul>{sections.filter(after).map(rows)}</ul>
    </nav>;
}
