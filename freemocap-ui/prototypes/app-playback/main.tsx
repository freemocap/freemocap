import {ZoomableVideoTile} from '../../src/components/playback/ZoomableVideoTile';
import '../../src/styles/App.css';
import type {PlaybackBundle} from '../../src/store/slices/playback-data/playback-data-slice';
/** Integration harness exercising the application's actual controller against the native playback socket. */
import React, {useState, useEffect} from 'react';
import {createRoot} from 'react-dom/client';
import {usePlaybackController} from '../../src/components/playback/usePlaybackController';
import {PlaybackControls} from '../../src/components/playback/PlaybackControls';
import '../../src/styles/playback.css';
import '../../src/styles/color.css';
import {serverUrls} from '../../src/constants/server-urls';

serverUrls.setHost(location.hostname); serverUrls.setPort(Number(location.port));
function Harness(): React.JSX.Element {
    const [bundle, setBundle] = useState<PlaybackBundle | null>(null);
    const [recordingId, setRecordingId] = useState('test');
    const [annotated, setAnnotated] = useState(false);
    const videos = Array.from({length: 2}, (_, index) => {
        const filename = `camera${index}${annotated ? '_annotated' : ''}.mp4`;
        return {filename, sizeBytes: bundle ? Object.values(bundle.videos.sources).flatMap(source => source.videos).find(video => video.filename === filename)!.sizeBytes : 0, videoId: filename, streamUrl: `${location.origin}/test-media/${filename}`};
    });
    useEffect(() => {setBundle(null); void fetch(`/freemocap/playback/${recordingId}/bundle`).then(response => {
        if (!response.ok) throw new Error('Bundle failed');
        return response.json();
    }).then(setBundle);}, [recordingId]);
    const controller = usePlaybackController({videos, recordingId, recordingParentDirectory: null,
        bundle, cacheBudgetBytes: 512 * 1024 ** 2, reloadManifest: () => {throw new Error('Unexpected reload');}});
    useEffect(() => {
        if (bundle) controller.setPlaybackRun({run_id: 0, models: [], channels: [], static_channels: [], timelines: [],
            media: bundle.media.filter(item => !item.video_filename.includes('_annotated'))});
    }, [bundle, controller.setPlaybackRun]);
    return <>
        <output id="error">{controller.error}</output>
        <output id="ready">{String(controller.allReady)}</output>
        <output id="playing">{String(controller.isPlaying)}</output>
        <button id="play" onClick={controller.handlePlayPause}>Play/pause</button>
        <button id="back" onClick={() => controller.handleSeekCommit(2)}>Seek 2</button>
        <button id="forward" onClick={() => controller.handleSeekCommit(30)}>Seek 30</button>
        <button id="source" onClick={() => setAnnotated(value => !value)}>Switch source</button>
        <button id="recording" onClick={() => setRecordingId(value => value === 'test' ? 'test-other' : 'test')}>Switch recording</button>
        <PlaybackControls {...controller} onSettingsChange={controller.setSettings}
            onPlayPause={controller.handlePlayPause} onSeekDrag={controller.handleSeekDrag}
            onSeekCommit={controller.handleSeekCommit} onFrameStep={controller.handleFrameStep}
            onPlaybackRateChange={controller.handlePlaybackRateChange} onSeekToStart={controller.handleSeekToStart}
            onSeekToEnd={controller.handleSeekToEnd} onToggleLoop={controller.handleToggleLoop}/>
        {videos.map(video => <div key={video.videoId} className="test-video-panel" style={{width: 320, height: 240, display: 'inline-block'}}>
            <ZoomableVideoTile videoId={video.videoId} streamUrl={video.streamUrl} filename={video.filename}
                showOverlays={false} hasError={false} setVideoRef={controller.setVideoRef}
                setFrameOverlayRef={controller.setFrameOverlayRef}/>
        </div>)}
    </>;
}
createRoot(document.getElementById('root')!).render(<React.StrictMode><Harness/></React.StrictMode>);
