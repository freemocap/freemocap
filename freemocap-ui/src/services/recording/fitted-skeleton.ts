import {Quaternion, Vector3} from 'three';
import {channelFrame, orderedChannelFrame, sampleAtTime, RecordingComponent, type PlaybackRun, type PlaybackChannelData} from './playback-data';
import type {FittedSkeleton, FittedSkeletonFrame} from './fitted-skeleton-types';

// One warning per source/reason per loaded result, including repeated seeks.
const warnings = new WeakMap<PlaybackRun, Set<string>>();
function warn(run: PlaybackRun, source: string, reason: string, detail?: unknown): void {
    let seen = warnings.get(run);
    if (!seen) {seen = new Set(); warnings.set(run, seen);}
    const key = `${source}: ${reason}`;
    if (!seen.has(key)) {seen.add(key); console.warn(`Skipping invalid fitted data (${key})`, detail ?? '');}
}

export function fittedSkeletonFrames(run: PlaybackRun, channels: PlaybackChannelData[], group: string, time: number): FittedSkeletonFrame[] {
    return Object.entries(run.fitted_skeletons ?? {}).filter(([, def]) => def.sensor_group === group).flatMap(([source, def]) => {
        try {
        const find = (kind: string) => {
            const matches = channels.filter(c => c.channel.source === source && c.channel.sensor_group === group && c.channel.kind === kind);
            if (matches.length !== 1) throw new Error(`Fitted skeleton ${source}: expected one ${kind} channel`);
            return matches[0];
        };
        const positions = find('SEGMENT_ORIGINS'), rotations = find('ROTATIONS_WORLD'), lengths = find('SEGMENT_LENGTHS');
        if (!positions.channel.reference_frame || positions.channel.reference_frame !== rotations.channel.reference_frame ||
            Object.values(positions.channel.components).some(unit => unit !== 'mm') ||
            Object.values(rotations.channel.components).some(unit => unit !== '1')) {
            throw new Error('Invalid fitted skeleton coordinate reference or units');
        }
        const index = sampleAtTime(positions.timestamps_s, time);
        if (index < 0) return [];
        for (const channel of [rotations, lengths]) {
            const other = sampleAtTime(channel.timestamps_s, time);
            if (other < 0 || channel.frame_numbers[other] !== positions.frame_numbers[index] ||
                channel.timestamps_s[other] !== positions.timestamps_s[index]) throw new Error('Fitted skeleton channels disagree on the selected frame');
        }
        const xyz = [RecordingComponent.X, RecordingComponent.Y, RecordingComponent.Z];
        const origins = orderedChannelFrame(positions, time, {names: def.geometry.names, components: xyz})!;
        const quaternions = orderedChannelFrame(rotations, time, {names: def.geometry.names, components: [RecordingComponent.W, ...xyz]})!;
        if (Object.keys(lengths.channel.components).join() !== 'length' || lengths.channel.components.length !== 'mm') throw new Error('Invalid fitted length units');
        const axial = def.geometry.names.filter((_, i) => def.geometry.references[i] > 0);
        if (axial.length !== lengths.channel.names.length || axial.some(n => !lengths.channel.names.includes(n))) throw new Error('Incomplete fitted axial lengths');
        const savedLengths = channelFrame(lengths, time)!;
        const frameLengths = Float32Array.from(def.geometry.names.map((name, i) => def.geometry.references[i] > 0
            ? savedLengths[lengths.channel.names.indexOf(name)] : 0));
        const validSegments = new Uint8Array(def.geometry.names.length);
        for (let i = 0; i < def.geometry.names.length; i++) {
            const position = origins.subarray(i * 3, i * 3 + 3);
            const rotation = quaternions.subarray(i * 4, i * 4 + 4);
            validSegments[i] = Number(position.every(Number.isFinite) && rotation.every(Number.isFinite) &&
                Number.isFinite(frameLengths[i]) && Math.abs(Math.hypot(...rotation) - 1) <= 1e-4 &&
                (def.geometry.references[i] <= 0 || frameLengths[i] > 0));
        }
        if (validSegments.includes(0)) warn(run, source, 'nonfinite position, invalid rotation or axial length', {
            frame: positions.frame_numbers[index], segments: def.geometry.names.filter((_, i) => !validSegments[i]),
        });
        return [{source, origins, quaternions, lengths: frameLengths, validSegments}];
        } catch (failure) {
            warn(run, source, failure instanceof Error ? failure.message : String(failure));
            return [];
        }
    });
}

/** Apply the stored segment transform and its stored axial deformation only. */
export function fittedWorldPoint(def: FittedSkeleton, frame: FittedSkeletonFrame, segment: number, local: readonly number[]): Vector3 {
    const reference = def.geometry.references[segment];
    const scale = reference > 0 ? frame.lengths[segment] / reference : 1;
    const q = frame.quaternions.subarray(segment * 4, segment * 4 + 4);
    return new Vector3(local[0], local[1], local[2] * scale)
        .applyQuaternion(new Quaternion(q[1], q[2], q[3], q[0]))
        .add(new Vector3().fromArray(frame.origins, segment * 3));
}
