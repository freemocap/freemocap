/** Integration harness exercising the application's actual controller against test HTTP media. */
import React, {useState} from 'react';
import {createRoot} from 'react-dom/client';
import {usePlaybackController} from '../../src/components/playback/usePlaybackController';
import {PlaybackControls} from '../../src/components/playback/PlaybackControls';
import '../../src/styles/playback.css';
import {serverUrls} from '../../src/constants/server-urls';

serverUrls.setHost(location.hostname); serverUrls.setPort(Number(location.port));
function Harness(): React.JSX.Element {
    const [annotated, setAnnotated] = useState(false);
    const videos = Array.from({length: 2}, (_, index) => {
        const filename = `camera${index}${annotated ? '_annotated' : ''}.mp4`;
        return {filename, videoId: filename, streamUrl: `${location.origin}/test-media/${filename}`};
    });
    const controller = usePlaybackController({videos, recordingId: 'test', recordingParentDirectory: null});
    return <>
        <output id="error">{controller.error}</output>
        <output id="ready">{String(controller.allReady)}</output>
        <output id="playing">{String(controller.isPlaying)}</output>
        <button id="play" onClick={controller.handlePlayPause}>Play/pause</button>
        <button id="back" onClick={() => controller.handleSeekCommit(2)}>Seek 2</button>
        <button id="forward" onClick={() => controller.handleSeekCommit(30)}>Seek 30</button>
        <button id="source" onClick={() => setAnnotated(value => !value)}>Switch source</button>
        <PlaybackControls {...controller} onSettingsChange={controller.setSettings}
            onPlayPause={controller.handlePlayPause} onSeekDrag={controller.handleSeekDrag}
            onSeekCommit={controller.handleSeekCommit} onFrameStep={controller.handleFrameStep}
            onPlaybackRateChange={controller.handlePlaybackRateChange} onSeekToStart={controller.handleSeekToStart}
            onSeekToEnd={controller.handleSeekToEnd} onToggleLoop={controller.handleToggleLoop}/>
        {videos.map(video => <canvas key={video.videoId} ref={canvas => controller.setVideoRef(video.videoId, canvas)}/>)}
    </>;
}
createRoot(document.getElementById('root')!).render(<Harness/>);
