import React from 'react';
import VideoLibraryIcon from '@mui/icons-material/VideoLibrary';
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
            icon={<VideoLibraryIcon sx={{fontSize: 20}}/>}
            title={t('recordings')}
            defaultExpanded
        >
            <RecordingBrowser
                onRecordingLoaded={ctx.onRecordingLoaded}
                initialLoadPath={ctx.initialLoadPath}
            />
        </CollapsibleSidebarSection>
    );
};
