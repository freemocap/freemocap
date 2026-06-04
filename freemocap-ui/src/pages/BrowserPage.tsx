import React from 'react';
import {useNavigate} from 'react-router-dom';
import {Footer} from '@/components/ui-components/Footer';
import ErrorBoundary from '@/components/common/ErrorBoundary';
import {RecordingBrowser} from '@/components/playback/RecordingBrowser';
import {usePlaybackContext} from '@/components/playback/PlaybackContext';
import {useAppSelector} from '@/store';
import {selectActiveRecordingFullPath} from '@/store/slices/active-recording/active-recording-slice';

const BrowserPage: React.FC = () => {
    const navigate = useNavigate();
    const ctx = usePlaybackContext();
    const activeRecordingPath = useAppSelector(selectActiveRecordingFullPath);

    return (
        <div className="flex flex-col flex-1 bg-dark" style={{height: '100%', border: '1px solid var(--color-border-secondary)'}}>
            <div className="flex flex-col flex-1 overflow-hidden">
                <ErrorBoundary>
                    <RecordingBrowser
                        activeRecordingPath={activeRecordingPath}
                        onRecordingLoaded={(videos, recPath, recFps, sources, preferred) => {
                            ctx?.onRecordingLoaded(videos, recPath, recFps, sources, preferred);
                            navigate('/playback');
                        }}
                    />
                </ErrorBoundary>
            </div>
            <footer style={{padding: 4}}>
                <Footer/>
            </footer>
        </div>
    );
};

export default BrowserPage;
