import FramerateViewerPanel from '@/components/framerate-viewer/FrameRateViewer';
import {TabbedContent} from '@/components/ui-components/TabbedContent';
import {useAppSelector} from '@/store/hooks';
import {selectActiveBasePipelineCount} from '@/store/slices/pipelines';

function PipelineTabLabel() {
    const activeCount = useAppSelector(selectActiveBasePipelineCount);
    return (
        <div className="flex items-center" style={{gap: '0.375rem'}}>
            Pipelines
            {activeCount > 0 && (
                <div
                    style={{
                        width: 7,
                        height: 7,
                        borderRadius: '50%',
                        backgroundColor: 'var(--color-info)',
                        flexShrink: 0,
                        animation: 'fmcPulse 1.4s ease-in-out infinite',
                    }}
                />
            )}
        </div>
    );
}

export default function TabbedBottomLeftPanel({isCollapsed = false}: { isCollapsed?: boolean }) {
    if (isCollapsed) {
        return <FramerateViewerPanel isCollapsed={true}/>;
    }
    return (
        <TabbedContent tabs={[
            {label: 'Framerate', content: <FramerateViewerPanel/>},
            // {label: <PipelineTabLabel/>, content: <PipelineProgressPanel/>},
        ]}/>
    );
}
