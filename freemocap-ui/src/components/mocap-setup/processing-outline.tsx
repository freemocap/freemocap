// The window's outline: every section in pipeline order with its switch, always on the left.
import type {ResumeStage} from '@/services/recording/posthoc-processing';
import {BlenderToggle, ExportsToggle, StageToggle, useStageOutcome} from './processing-run-controls';
import type {ProcessingSection, SectionId} from './processing-sections';

function StageOutcome({stage}: {stage: ResumeStage}) {
    const outcome = useStageOutcome(stage);
    return <span className="mp-outline-state">{outcome}</span>;
}

export default function ProcessingOutline({sections, active, playback, states, onPick}: {
    sections: ProcessingSection[];
    active: SectionId | null;
    playback: boolean;
    /** Run state per section while a run is shown, else null. */
    states: Partial<Record<SectionId, string>> | null;
    onPick: (id: SectionId) => void;
}) {
    const row = (section: ProcessingSection) => <li key={section.id} className={`mp-outline-row${active === section.id ? ' active' : ''}`}>
        {playback && section.stage && <StageToggle stage={section.stage} title={section.title}/>}
        <button type="button" className="mp-outline-link" aria-label={section.title} onClick={() => onPick(section.id)}>
            {section.number !== null && <span className="mp-outline-number">{section.number}</span>}
            {section.title}
        </button>
        {states?.[section.id] ? <span className={`mp-outline-state ${states[section.id]}`}>{states[section.id]}</span>
            : playback && section.stage ? <StageOutcome stage={section.stage}/>
                : section.id === 'blender' ? <BlenderToggle/> : section.id === 'exports' ? <ExportsToggle/> : null}
    </li>;
    return <nav className="mp-outline" aria-label="Mocap processing sections">
        <span className="mp-outline-heading">Pipeline</span>
        <ul>{sections.filter(section => section.id !== 'blender' && section.id !== 'exports').map(row)}</ul>
        <span className="mp-outline-heading">After processing</span>
        <ul>{sections.filter(section => section.id === 'blender' || section.id === 'exports').map(row)}</ul>
    </nav>;
}
