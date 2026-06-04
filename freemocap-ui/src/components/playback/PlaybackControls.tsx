import React, {useState} from 'react';
import type {PlaybackSettings} from './SyncedVideoPlayer';
import {useTranslation} from 'react-i18next';

interface PlaybackControlsProps {
    isPlaying: boolean;
    currentTime: number;
    duration: number;
    playbackRate: number;
    currentFrame: number;
    totalFrames: number;
    fps: number;
    recordingFps?: number;
    settings: PlaybackSettings;
    onSettingsChange: (settings: PlaybackSettings) => void;
    onPlayPause: () => void;
    onSeekDrag: (frame: number) => void;
    onSeekCommit: (frame: number) => void;
    onFrameStep: (delta: number) => void;
    onPlaybackRateChange: (rate: number) => void;
    onSeekToStart: () => void;
    onSeekToEnd: () => void;
    isLooping: boolean;
    onToggleLoop: () => void;
    availableSources?: Record<string, { available: boolean; valid: boolean }> | null;
    selectedSource?: string | null;
    onSourceChange?: (source: string) => void;
}

const PLAYBACK_RATES = [0.1, 0.25, 0.5, 1, 1.5, 2, 4, 8];

function formatTime(seconds: number): string {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    const ms = Math.floor((seconds % 1) * 100);
    return `${mins}:${secs.toString().padStart(2, '0')}.${ms.toString().padStart(2, '0')}`;
}

export const PlaybackControls: React.FC<PlaybackControlsProps> = ({
    isPlaying,
    currentTime,
    duration,
    playbackRate,
    currentFrame,
    totalFrames,
    fps,
    recordingFps,
    settings,
    onSettingsChange,
    onPlayPause,
    onSeekDrag,
    onSeekCommit,
    onFrameStep,
    onPlaybackRateChange,
    onSeekToStart,
    onSeekToEnd,
    isLooping,
    onToggleLoop,
    availableSources,
    selectedSource,
    onSourceChange,
}) => {
    const { t } = useTranslation();
    const monoFont = '"JetBrains Mono", "Fira Code", "SF Mono", monospace';

    const [settingsOpen, setSettingsOpen] = useState(false);
    const [syncInfoOpen, setSyncInfoOpen] = useState(true);

    const updateSetting = <K extends keyof PlaybackSettings>(key: K, value: PlaybackSettings[K]) => {
        onSettingsChange({ ...settings, [key]: value });
    };

    const validSources = availableSources && selectedSource && onSourceChange
        ? Object.entries(availableSources).filter(([, s]) => s.available && s.valid).map(([key]) => key)
        : [];

    return (
        <div className="flex flex-col gap-1 bg-middark" style={{padding: '8px 16px', borderTop: '1px solid var(--color-border-secondary)'}}>
            <div className="flex flex-row items-center gap-1">
                <span
                    title={t("estimatedTime")}
                    className="text sm"
                    style={{fontFamily: monoFont, minWidth: 70, textAlign: 'right', color: '#00ff88', fontWeight: 600, fontSize: '0.8rem'}}
                >
                    ~{formatTime(currentTime)}
                </span>
                <input
                    type="range"
                    value={currentFrame}
                    min={0}
                    max={Math.max(totalFrames - 1, 1)}
                    step={1}
                    onChange={(e) => onSeekDrag(Number(e.target.value))}
                    onMouseUp={(e) => onSeekCommit(Number((e.target as HTMLInputElement).value))}
                    style={{flex: 1, accentColor: 'var(--color-info)', width: '100%'}}
                />
                <span
                    title={t("estimatedDuration")}
                    className="text sm text-gray"
                    style={{fontFamily: monoFont, minWidth: 70}}
                >
                    ~{formatTime(duration)}
                </span>
            </div>

            <div className="flex flex-row items-center justify-center gap-1">
                <div className="flex flex-row items-center gap-1" style={{minWidth: 240, justifyContent: 'flex-end', marginRight: 8}}>
                    <span
                        className="tag text sm"
                        style={{fontFamily: monoFont, fontSize: '0.85rem', fontWeight: 700, color: '#00ff88', backgroundColor: 'rgba(0,255,136,0.08)', padding: '2px 8px', borderRadius: 4, border: '1px solid rgba(0,255,136,0.2)'}}
                    >
                        Frame {currentFrame} / {totalFrames}
                    </span>

                    {recordingFps != null && recordingFps > 0 && (
                        <span
                            title={t("recordingCaptureFps")}
                            className="tag text sm"
                            style={{fontFamily: monoFont, fontSize: '0.7rem', color: '#ffcc80', backgroundColor: 'rgba(255,204,128,0.08)', padding: '1px 6px', borderRadius: 4, border: 'rgba(255,204,128,0.2)', whiteSpace: 'nowrap'}}
                        >
                            rec: {recordingFps} fps
                        </span>
                    )}
                </div>

                <button title={t("jumpToStart")} className="button icon-button br-1" onClick={onSeekToStart}>
                    <span className="icon skipbackward-icon icon-size-20"/>
                </button>

                <button title={t("previousFrame")} className="button icon-button br-1" onClick={() => onFrameStep(-1)}>
                    <span className="icon framebackward-icon icon-size-20"/>
                </button>

                <button
                    title={isPlaying ? 'Pause (Space)' : 'Play (Space)'}
                    className="button icon-button br-1"
                    onClick={onPlayPause}
                    style={{margin: '0 4px', border: '2px solid #4caf50', color: '#4caf50'}}
                >
                    {isPlaying
                        ? <span className="icon pause-icon icon-size-20"/>
                        : <span className="icon play-icon icon-size-20"/>}
                </button>

                <button title={t("nextFrame")} className="button icon-button br-1" onClick={() => onFrameStep(1)}>
                    <span className="icon frameforward-icon icon-size-20"/>
                </button>

                <button title={t("jumpToEnd")} className="button icon-button br-1" onClick={onSeekToEnd}>
                    <span className="icon skipforward-icon icon-size-20"/>
                </button>

                <button
                    title={isLooping ? t("loopOn") : t("loopOff")}
                    className="button icon-button br-1"
                    onClick={onToggleLoop}
                    style={{
                        color: isLooping ? 'var(--color-info)' : undefined,
                        backgroundColor: isLooping ? 'rgba(41, 182, 246, 0.15)' : undefined,
                        border: isLooping ? '1px solid var(--color-info)' : '1px solid transparent',
                    }}
                >
                    <span className={`icon icon-size-20 ${isLooping ? 'loopactive-icon' : 'loop-icon'}`}/>
                </button>

                {validSources.length >= 2 && selectedSource && onSourceChange && (
                    <div className="flex flex-row gap-1" style={{marginLeft: 8}}>
                        {['annotated', 'synchronized'].map((src) => (
                            <button
                                key={src}
                                className={`button sm ${selectedSource === src ? 'primary' : 'secondary'}`}
                                onClick={() => onSourceChange(src)}
                                style={{fontFamily: monoFont, fontSize: '0.7rem', textTransform: 'capitalize'}}
                            >
                                {src}
                            </button>
                        ))}
                    </div>
                )}

                <div className="flex flex-row items-center gap-1" style={{marginLeft: 8}}>
                    <span title={t("playbackSpeed")} className="text sm text-gray" style={{fontSize: '0.8rem'}}>Speed:</span>
                    <select
                        className="input-field text md"
                        value={playbackRate}
                        onChange={(e) => onPlaybackRateChange(Number(e.target.value))}
                        style={{minWidth: 70, fontFamily: monoFont, fontSize: '0.8rem'}}
                    >
                        {PLAYBACK_RATES.map((rate) => (
                            <option key={rate} value={rate}>{rate}×</option>
                        ))}
                    </select>

                    <button
                        title={t("syncInfo")}
                        className="button icon-button br-1"
                        onClick={() => setSyncInfoOpen((prev) => !prev)}
                        style={{color: syncInfoOpen ? '#ffcc80' : 'rgba(255,255,255,0.3)'}}
                    >
                        <span className="icon settings-icon icon-size-20"/>
                    </button>

                    <button
                        title={t("playbackSettings")}
                        className="button icon-button br-1"
                        onClick={() => setSettingsOpen(v => !v)}
                        style={{color: settingsOpen ? 'var(--color-info)' : undefined}}
                    >
                        <span className="icon settings-icon icon-size-20"/>
                    </button>
                </div>
            </div>

            {settingsOpen && (
                <div
                    className="splash-overlay inset-0"
                    style={{position: 'fixed', zIndex: 100}}
                    onClick={() => setSettingsOpen(false)}
                >
                    <div
                        className="bg-middark br-2 flex flex-col p-3"
                        style={{position: 'fixed', bottom: 80, right: 16, minWidth: 260}}
                        onClick={(e) => e.stopPropagation()}
                    >
                        <p className="text md text-white" style={{fontWeight: 600, marginBottom: 12}}>Display Settings</p>

                        <label className="flex flex-row items-center gap-1" style={{marginBottom: 12}}>
                            <input
                                type="checkbox"
                                checked={settings.showOverlays}
                                onChange={(e) => updateSetting('showOverlays', e.target.checked)}
                                style={{accentColor: 'var(--color-info)'}}
                            />
                            <span className="text sm text-white">Show frame overlays</span>
                        </label>

                        <p className="text sm text-gray" style={{marginBottom: 6}}>Timestamp format</p>
                        <div className="flex flex-row gap-1">
                            {(['seconds', 'timecode'] as const).map(fmt => (
                                <button
                                    key={fmt}
                                    className={`button sm flex-1 ${settings.timestampFormat === fmt ? 'primary' : 'secondary'}`}
                                    style={{fontFamily: monoFont, fontSize: '0.75rem'}}
                                    onClick={() => updateSetting('timestampFormat', fmt)}
                                >
                                    {fmt === 'seconds' ? '1.234s' : 'HH:MM:SS:FF'}
                                </button>
                            ))}
                        </div>
                    </div>
                </div>
            )}

            {syncInfoOpen && (
                <div style={{padding: '8px 16px', marginTop: 4, borderRadius: 4, backgroundColor: 'rgba(255, 204, 128, 0.06)', border: '1px solid rgba(255, 204, 128, 0.15)'}}>
                    <p className="text sm" style={{color: '#ffcc80', fontWeight: 600, marginBottom: 4}}>
                        {t("syncInfoTitle")}
                    </p>
                </div>
            )}
        </div>
    );
};
