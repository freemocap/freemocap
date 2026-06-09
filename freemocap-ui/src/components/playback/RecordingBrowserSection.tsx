import React from 'react';
import {CollapsibleSidebarSection} from '@/components/common/CollapsibleSidebarSection';
import {RecordingBrowser} from './RecordingBrowser';
import {usePlaybackContext} from './PlaybackContext';
import {useTranslation} from 'react-i18next';

export const RecordingBrowserSection: React.FC = () => {
    const {t} = useTranslation();
    const ctx = usePlaybackContext();

    if (!ctx) return null;

    return (
        <CollapsibleSidebarSection
            icon={<span className="icon load-icon icon-size-20"/>}
            title={t('recordings')}
            defaultExpanded
        >
            <div style={{ height: '60vh', overflow: 'hidden' }}>
                <RecordingBrowser
                    onRecordingLoaded={ctx.onRecordingLoaded}
                />
            </div>
        </CollapsibleSidebarSection>
    );
};
