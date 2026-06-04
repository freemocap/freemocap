import React, {useState} from 'react';
import {useServerPanel} from './useServerPanel';
import {ServerStatusBar} from './ServerStatusBar';
import {ServerProcessSection} from './ServerProcessSection';
import {WebSocketSection} from './WebSocketSection';

export const ServerConnectionStatus: React.FC = () => {
    const panel = useServerPanel();
    const {expanded, setExpanded, isElectron} = panel;

    return (
        <div style={{borderBottom: '1px solid var(--color-border-secondary)', backgroundColor: 'rgba(0,0,0,0.2)'}}>
            <ServerStatusBar {...panel} setExpanded={setExpanded} expanded={expanded}/>

            {expanded && (
                <div className="flex flex-col" style={{padding: '0 12px 12px', gap: '12px'}}>
                    {isElectron && <ServerProcessSection {...panel}/>}
                    <WebSocketSection {...panel}/>
                </div>
            )}
        </div>
    );
};
