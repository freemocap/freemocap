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
import ToggleComponent from '@/components/ui-components/ToggleComponent';

export default function PipelineProgressPanel() {
    const groups = useAppSelector(selectGroupedPipelines);
    const hasCompleted = useAppSelector(selectHasCompletedPipelines);
    const showCompleted = useAppSelector(selectShowCompleted);
    const filterText = useAppSelector(selectFilterText);
    const dispatch = useAppDispatch();

    return (
        <div className="flex flex-col h-full">
            <div className="flex flex-col gap-1 flex-shrink-0" style={{padding: '4px 8px'}}>
                <div className="input-with-string">
                    <input
                        className="input-field text md"
                        placeholder="Filter..."
                        value={filterText}
                        onChange={(e) => dispatch(filterTextChanged(e.target.value))}
                        style={{height: 28, fontSize: '0.75rem'}}
                    />
                </div>
                {hasCompleted && (
                    <ToggleComponent
                        text="Show completed"
                        isToggled={showCompleted}
                        onToggle={() => dispatch(toggleShowCompleted())}
                    />
                )}
            </div>

            <div className="flex-1 overflow-y">
                {groups.length === 0 ? (
                    <div className="flex items-center justify-center h-full">
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
