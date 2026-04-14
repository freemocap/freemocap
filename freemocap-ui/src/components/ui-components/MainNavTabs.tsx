import {useLocation, useNavigate} from "react-router-dom";
import {useCallback, useMemo} from "react";
import {alpha, darken} from "@mui/material/styles";
import {Tab, Tabs} from "@mui/material";

const NAV_TABS = [
    {path: '/welcome', label: 'Home'},
    {path: '/streaming', label: 'Streaming'},
    {path: '/playback', label: 'Playback'},
] as const;

export const MainNavTabs = () => {
    const location = useLocation();
    const navigate = useNavigate();

    const activeTab = useMemo(() => {
        const idx = NAV_TABS.findIndex(t => location.pathname === t.path);
        return idx >= 0 ? idx : 0;
    }, [location.pathname]);

    const handleTabChange = useCallback((_: React.SyntheticEvent, index: number) => {
        navigate(NAV_TABS[index].path);
    }, [navigate]);

    return (
        <Tabs
            value={activeTab}
            onChange={handleTabChange}
            sx={(theme) => ({
                minHeight: 28,
                px: 0.5,
                borderRadius: 1,
                backgroundColor: darken(theme.palette.background.default, 0.2),
                borderBottom: `1px solid ${alpha(theme.palette.divider, 0.2)}`,
                '& .MuiTab-root': {
                    minHeight: 28,
                    fontSize: '0.75rem',
                    py: 0.5,
                    borderRadius: 0.75,
                    position: 'relative',
                },
                '& .MuiTab-root:not(:last-of-type)::after': {
                    content: '""',
                    position: 'absolute',
                    right: 0,
                    top: '22%',
                    height: '56%',
                    borderRight: `1px solid ${alpha(theme.palette.divider, 0.15)}`,
                },
                '& .MuiTab-root.Mui-selected': {
                    backgroundColor: darken(theme.palette.background.paper, 0.15),
                },
            })}
        >
            {NAV_TABS.map(tab => (
                <Tab key={tab.path} label={tab.label}/>
            ))}
        </Tabs>
    );
};
