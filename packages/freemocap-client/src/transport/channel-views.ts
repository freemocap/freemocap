import type {ChannelBlock, FrameMessage} from './message-contract.js';

export type ChannelOwner =
    | {scope: 'tracker'; trackerId: string; modelId: string | null}
    | {scope: 'instance'; instanceId: number; modelId: string};

/** A view of a declared channel, including kinds with no specialized renderer.
 * Names remain absent when the wire omits them; custom row semantics are never
 * inferred from a kind's spelling. Numerical storage belongs to the decoded frame. */
export interface ChannelView {
    owner: ChannelOwner;
    channelIndex: number;
    descriptor: ChannelBlock;
    rowCount: number;
    data: Float32Array;
}

export interface ChannelViewsFrame {
    frameNumber: number;
    timestamp: number;
    convention: FrameMessage['convention'];
    models: FrameMessage['models'];
    cameras: FrameMessage['cameras'];
    channels: readonly ChannelView[];
}

/** Resolve an already decoded frame without requiring earlier metadata.
 * Retain descriptors, owner identity, order, NaNs and all declared components.
 * Consumers must copy values before modifying or transferring their buffers. */
export function resolveChannelViews(frame: FrameMessage): ChannelViewsFrame {
    const channels: ChannelView[] = [];
    const append = (blocks: ChannelBlock[], owner: ChannelOwner) => {
        blocks.forEach((descriptor, channelIndex) => {
            const width = descriptor.columns.length;
            const rowBytes = width * Float32Array.BYTES_PER_ELEMENT;
            if (!width || new Set(descriptor.columns).size !== width ||
                descriptor.data.byteLength % rowBytes !== 0) {
                throw new Error('Channel bytes must match unique declared columns');
            }
            const rowCount = descriptor.data.byteLength / rowBytes;
            if (descriptor.names && descriptor.names.length !== rowCount) {
                throw new Error('Channel names must match the declared row count');
            }
            if (descriptor.sample_status && descriptor.sample_status.length !== rowCount) {
                throw new Error('Channel status must have one value per row');
            }
            const bytes = descriptor.data;
            // The decoder aligns owned bytes; retain support for validated direct inputs.
            const aligned = bytes.byteOffset % 4 === 0 ? bytes : new Uint8Array(bytes);
            channels.push({owner, channelIndex, descriptor, rowCount,
                data: new Float32Array(aligned.buffer, aligned.byteOffset, aligned.byteLength / 4)});
        });
    };
    for (const tracker of frame.trackers) append(tracker.channels,
        {scope: 'tracker', trackerId: tracker.tracker_id, modelId: tracker.model_id});
    for (const instance of frame.instances) append(instance.channels,
        {scope: 'instance', instanceId: instance.instance_id, modelId: instance.model_id});
    return {frameNumber: frame.frame_number, timestamp: frame.timestamp,
        convention: frame.convention, models: frame.models, cameras: frame.cameras, channels};
}
