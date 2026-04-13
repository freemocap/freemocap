import {useLocation, useNavigate} from "react-router-dom";
import {StreamingViewPage} from "@/pages/StreamingViewPage";
import PlaybackPage from "@/pages/PlaybackPage";
import {TabbedContent} from "@/components/ui-components/TabbedContent";
import {useCallback, useMemo} from "react";
import Box from "@mui/material/Box";

const PAGE_TABS = [
    {path: '/streaming', label: 'Streaming'},
    {path: '/playback', label: 'Playback'},
] as const;

export const PageTabButtons = () => {
    const location = useLocation();
    const navigate = useNavigate();

    const isTabRoute = PAGE_TABS.some(t => location.pathname === t.path);

    const activeTab = useMemo(() => {
        const idx = PAGE_TABS.findIndex(t => location.pathname === t.path);
        return idx >= 0 ? idx : 0;
    }, [location.pathname]);

    const handleTabChange = useCallback((index: number) => {
        navigate(PAGE_TABS[index].path);
    }, [navigate]);

    const tabs = useMemo(() => [
        {label: PAGE_TABS[0].label, content: <StreamingViewPage/>},
        {label: PAGE_TABS[1].label, content: <PlaybackPage/>},
    ], []);

    return (
        <Box sx={{display: isTabRoute ? 'flex' : 'none', flexDirection: 'column', height: '100%'}}>
            <TabbedContent
                tabs={tabs}
                activeTab={activeTab}
                onTabChange={handleTabChange}
            />
        </Box>
    );
};
