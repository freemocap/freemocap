import React from 'react';
import {RecordingBrowser} from './RecordingBrowser';
import {usePlaybackContext} from './PlaybackContext';

export const RecordingBrowserSection: React.FC = () => {
    const ctx = usePlaybackContext();

    if (!ctx) return null;

    return (
        <div className="recording-browser-sidebar-panel flex flex-col flex-1 bg-middark br-2 p-1 min-h-0">
            <RecordingBrowser
                onRecordingLoaded={ctx.onRecordingLoaded}
            />
        </div>
    );
};
