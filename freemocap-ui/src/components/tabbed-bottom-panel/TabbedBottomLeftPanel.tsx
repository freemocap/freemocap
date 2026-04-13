import FramerateViewerPanel from '@/components/framerate-viewer/FrameRateViewer';
import PipelineProgressPanel from '@/components/pipeline-progress/PipelineProgressPanel';
import {TabbedContent} from '@/components/ui-components/TabbedContent';

export default function TabbedBottomLeftPanel() {
    return (
        <TabbedContent tabs={[
            {label: 'Framerate', content: <FramerateViewerPanel/>},
            {label: 'Pipelines', content: <PipelineProgressPanel/>},
        ]}/>
    );
}
