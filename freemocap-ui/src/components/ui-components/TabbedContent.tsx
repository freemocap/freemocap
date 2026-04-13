import React, {useState} from 'react';
import Box from '@mui/material/Box';
import Tabs from '@mui/material/Tabs';
import Tab from '@mui/material/Tab';
import type {SxProps, Theme} from '@mui/material/styles';

export interface TabDef {
    label: string;
    content: React.ReactNode;
}

interface TabbedContentProps {
    tabs: TabDef[];
    activeTab?: number;
    onTabChange?: (index: number) => void;
    tabsSx?: SxProps<Theme>;
}

/**
 * Generic tabbed content container.
 * All tab panels stay mounted — only visibility is toggled (display block/none).
 * Can be controlled (activeTab + onTabChange) or uncontrolled (internal state).
 */
export function TabbedContent({tabs, activeTab, onTabChange, tabsSx}: TabbedContentProps) {
    const [internalTab, setInternalTab] = useState(0);
    const controlled = activeTab !== undefined;
    const currentTab = controlled ? activeTab : internalTab;

    const handleChange = (_: React.SyntheticEvent, value: number) => {
        if (onTabChange) onTabChange(value);
        if (!controlled) setInternalTab(value);
    };

    return (
        <Box sx={{height: '100%', display: 'flex', flexDirection: 'column'}}>
            <Tabs
                value={currentTab}
                onChange={handleChange}
                sx={{
                    minHeight: 28,
                    '& .MuiTab-root': {minHeight: 28, py: 0, fontSize: '0.75rem'},
                    ...tabsSx as any,
                }}
            >
                {tabs.map((t, i) => (
                    <Tab key={i} label={t.label}/>
                ))}
            </Tabs>
            {tabs.map((t, i) => (
                <Box key={i} sx={{flex: 1, overflow: 'hidden', display: currentTab === i ? 'block' : 'none'}}>
                    {t.content}
                </Box>
            ))}
        </Box>
    );
}
