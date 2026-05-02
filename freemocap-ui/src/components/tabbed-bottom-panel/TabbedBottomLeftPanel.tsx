import FramerateViewerPanel from '@/components/framerate-viewer/FrameRateViewer';
import PipelineProgressPanel from '@/components/pipeline-progress/PipelineProgressPanel';
import {TabbedContent} from '@/components/ui-components/TabbedContent';

export default function TabbedBottomLeftPanel({isCollapsed = false}: { isCollapsed?: boolean }) {
    if (isCollapsed) {
        return <FramerateViewerPanel isCollapsed={true}/>;
    }
    return (
        <TabbedContent tabs={[
            {label: 'Framerate', content: <FramerateViewerPanel/>},
            {label: 'Pipelines', content: <PipelineProgressPanel/>},
        ]}/>
    );
}
