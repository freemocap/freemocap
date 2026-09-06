import {sampleAtTime, type PlaybackMedia} from './playback-data';

export function mediaFrameAtRecordingTime(binding: PlaybackMedia, time: number): number | null {
    const {frame_numbers: frames, timestamps_s: times} = binding.timeline;
    if (!Number.isFinite(time) || !times.length || frames.length !== times.length) throw new Error('Invalid media sample grid');
    const index = sampleAtTime(times, time);
    return index < 0 || time > times[times.length - 1] ? null : frames[index];
}
