import React, { useState } from 'react';

export interface TabDef {
    label: React.ReactNode;
    content: React.ReactNode;
}

interface TabbedContentProps {
    tabs: TabDef[];
    activeTab?: number;
    onTabChange?: (index: number) => void;
}

export function TabbedContent({ tabs, activeTab, onTabChange }: TabbedContentProps) {
    const [internalTab, setInternalTab] = useState(0);
    const controlled = activeTab !== undefined;
    const currentTab = controlled ? activeTab : internalTab;

    const handleClick = (idx: number) => {
        if (onTabChange) onTabChange(idx);
        if (!controlled) setInternalTab(idx);
    };

    return (
        <div className="h-full flex flex-col">
            <div className="main-tab-bar">
                {tabs.map((t, i) => (
                    <button
                        key={i}
                        className={`segmented-control-button button${currentTab === i ? ' activated' : ''}`}
                        onClick={() => handleClick(i)}
                    >
                        <p className={`text md${currentTab === i ? ' text-white' : ' text-gray'}`}>{t.label}</p>
                    </button>
                ))}
            </div>
            {tabs.map((t, i) => (
                <div key={i} className="flex-1 overflow-hidden" style={{ display: currentTab === i ? 'block' : 'none' }}>
                    {t.content}
                </div>
            ))}
        </div>
    );
}
