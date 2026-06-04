import {useAppDispatch, useAppSelector} from '@/store/hooks';
import {
    selectGroupedPipelines,
    selectHasCompletedPipelines,
    selectShowCompleted,
    selectFilterText,
    toggleShowCompleted,
    filterTextChanged,
} from '@/store/slices/pipelines';
import PipelineGroupCard from './PipelineGroupCard';

export default function PipelineProgressPanel() {
    const groups = useAppSelector(selectGroupedPipelines);
    const hasCompleted = useAppSelector(selectHasCompletedPipelines);
    const showCompleted = useAppSelector(selectShowCompleted);
    const filterText = useAppSelector(selectFilterText);
    const dispatch = useAppDispatch();

    return (
        <div className="flex flex-col" style={{height: '100%'}}>
            <div className="flex flex-row items-center gap-1" style={{padding: '4px 8px', flexShrink: 0}}>
                <div className="input-with-string flex-1">
                    <input
                        className="input-field text md"
                        placeholder="Filter..."
                        value={filterText}
                        onChange={(e) => dispatch(filterTextChanged(e.target.value))}
                        style={{height: 28, fontSize: '0.75rem'}}
                    />
                </div>
                {hasCompleted && (
                    <label className="flex flex-row items-center gap-1">
                        <input
                            type="checkbox"
                            checked={showCompleted}
                            onChange={() => dispatch(toggleShowCompleted())}
                            style={{accentColor: 'var(--color-info)'}}
                        />
                        <span className="text sm text-gray">Show completed</span>
                    </label>
                )}
            </div>

            <div className="flex-1 overflow-y">
                {groups.length === 0 ? (
                    <div className="flex items-center justify-center" style={{height: '100%'}}>
                        <p className="text sm text-gray">No active pipelines</p>
                    </div>
                ) : (
                    groups.map((group) => (
                        <PipelineGroupCard key={group.basePipelineId} group={group}/>
                    ))
                )}
            </div>
        </div>
    );
}
