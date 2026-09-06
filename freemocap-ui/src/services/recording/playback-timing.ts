import {sampleAtTime, type PlaybackMedia} from './playback-data';

export interface MediaPosition {filename: string; time_s: number}

export function mediaFrameAtRecordingTime(binding: PlaybackMedia, time: number): number | null {
    const {frame_numbers: frames, timestamps_s: times} = binding.timeline;
    if (!Number.isFinite(time) || !times.length || frames.length !== times.length) throw new Error('Invalid media sample grid');
    const index = sampleAtTime(times, time);
    return index < 0 || time > times[times.length - 1] ? null : frames[index];
}

/** Resolve encoded video time against that video's recorded capture clock. */
export function recordingTimeForMedia(media: readonly PlaybackMedia[], position: MediaPosition): number | null {
    const matches = media.filter(item => item.video_filename === position.filename);
    if (matches.length !== 1) throw new Error(`Expected one recorded timing binding for video ${position.filename}; found ${matches.length}`);
    const binding = matches[0];
    const {frame_numbers: frames, timestamps_s: times} = binding.timeline;
    if (!Number.isFinite(position.time_s) || !Number.isFinite(binding.nominal_fps) || binding.nominal_fps <= 0 ||
        frames.length === 0 || frames.length !== times.length) throw new Error('Invalid video timing binding');
    const frame = position.time_s * binding.nominal_fps;
    const index = sampleAtTime(frames, frame);
    if (index < 0 || frame >= frames[frames.length - 1] + 1) return null;
    if (index === frames.length - 1) return times[index];
    const fraction = (frame - frames[index]) / (frames[index + 1] - frames[index]);
    return times[index] + fraction * (times[index + 1] - times[index]);
}
