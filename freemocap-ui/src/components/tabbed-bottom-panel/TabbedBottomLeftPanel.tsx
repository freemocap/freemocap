import FramerateViewerPanel from '@/components/framerate-viewer/FrameRateViewer';

export default function TabbedBottomLeftPanel({isCollapsed = false}: { isCollapsed?: boolean }) {
    return <FramerateViewerPanel isCollapsed={isCollapsed}/>;
}
