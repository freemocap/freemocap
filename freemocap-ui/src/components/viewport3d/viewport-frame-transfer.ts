import type {KeypointsFrame} from './KeypointsSourceContext';
import type {ResolvedModelFrame} from '@/services/server/transport/frame-types';
import {frameLayoutMatches, prepareFrameLayout, readFrameBuffer, writeFrameBuffer,
    type FrameLayout, type NumericalFrame, type NumericalStream} from './viewport-frame-codec';

type PostMessage = (message: unknown, transfer?: Transferable[]) => void;
interface FramePacket {
    type: 'viewportFrame'; sessionId: string; stream: NumericalStream; sequence: number;
    layoutVersion: number; layout?: FrameLayout; buffer: ArrayBuffer;
}
interface BufferReply {type: 'viewportBufferReturned'; sessionId: string; stream: NumericalStream; buffer: ArrayBuffer}
interface ReceiptReply {type: 'viewportFrameReceived'; sessionId: string; stream: NumericalStream; sequence: number; retainedPackets: number}
interface SenderStream {
    pending: NumericalFrame | null;
    inFlight: number | null;
    sequence: number;
    capacity: number;
    allocated: number;
    available: ArrayBuffer[];
    layout: FrameLayout | null;
    layoutVersion: number;
}

/** At most one queued delivery and one latest pending value per numerical stream. */
export class ViewportFrameSender {
    readonly sessionId = crypto.randomUUID();
    private readonly streams = new Map<NumericalStream, SenderStream>();
    private disposed = false;
    constructor(private readonly post: PostMessage) {
        post({type: 'viewportFrameStart', sessionId: this.sessionId});
    }
    sendKeypoints(frame: KeypointsFrame): void {this.enqueue('keypoints', frame);}
    sendModels(frames: ResolvedModelFrame[]): void {this.enqueue('modelFrames', frames);}
    receive(message: unknown): void {
        const reply = message as BufferReply | ReceiptReply;
        if (this.disposed || reply?.sessionId !== this.sessionId) return;
        const state = this.streams.get(reply.stream);
        if (!state) return;
        if (reply.type === 'viewportFrameReceived') {
            if (state.inFlight !== reply.sequence) return;
            state.inFlight = null;
            // Live holdover can contain more identities than any one incoming frame.
            state.capacity = Math.max(state.capacity, reply.retainedPackets + 2);
        } else if (reply.type === 'viewportBufferReturned') {
            if (state.layout && reply.buffer.byteLength === state.layout.byteLength && state.allocated <= state.capacity) state.available.push(reply.buffer);
            else state.allocated--;
        } else return;
        this.flush(reply.stream, state);
    }
    dispose(): void {
        if (this.disposed) return;
        this.disposed = true;
        this.streams.clear();
        this.post({type: 'viewportFrameEnd', sessionId: this.sessionId});
    }
    private enqueue(stream: NumericalStream, frame: NumericalFrame): void {
        if (this.disposed) return;
        let state = this.streams.get(stream);
        if (!state) {
            state = {pending: null, inFlight: null, sequence: 0, capacity: 3, allocated: 0, available: [], layout: null, layoutVersion: 0};
            this.streams.set(stream, state);
        }
        // A held model can retain an older packet; two spares permit receipt before recycling.
        if (stream === 'modelFrames') state.capacity = Math.max(state.capacity, (frame as ResolvedModelFrame[]).length + 2);
        state.pending = frame;
        this.flush(stream, state);
    }
    private flush(stream: NumericalStream, state: SenderStream): void {
        if (!state.pending || state.inFlight !== null) return;
        const frame = state.pending;
        let changed = false;
        if (!state.layout || !frameLayoutMatches(state.layout, stream, frame)) {
            state.layout = prepareFrameLayout(stream, frame); state.layoutVersion++; changed = true;
        }
        let buffer = state.available.pop();
        while (buffer && buffer.byteLength !== state.layout.byteLength) {state.allocated--; buffer = state.available.pop();}
        if (!buffer) {
            if (state.allocated >= state.capacity) return;
            buffer = new ArrayBuffer(state.layout.byteLength); state.allocated++;
        }
        writeFrameBuffer(buffer, state.layout, stream, frame);
        state.pending = null;
        const sequence = ++state.sequence;
        state.inFlight = sequence;
        // Re-send layout until its first delivery, even if all buffers were retained at the layout change.
        const packet: FramePacket = {type: 'viewportFrame', sessionId: this.sessionId, stream, sequence,
            layoutVersion: state.layoutVersion, buffer};
        if (changed || state.layoutVersion !== this.sentLayoutVersions.get(stream)) {
            packet.layout = state.layout; this.sentLayoutVersions.set(stream, state.layoutVersion);
        }
        this.post(packet, [buffer]);
    }
    private readonly sentLayoutVersions = new Map<NumericalStream, number>();
}

/** Recycles only packets no longer referenced by published/held presentation values. */
export class ViewportFrameReceiver {
    private sessionId: string | null = null;
    private readonly layouts = new Map<NumericalStream, {version: number; layout: FrameLayout}>();
    private readonly owned = new Map<ArrayBuffer, {sessionId: string; stream: NumericalStream}>();
    private releaseScheduled = false;
    constructor(private readonly post: PostMessage, private readonly dispatch: (stream: NumericalStream, frame: NumericalFrame) => void,
        private readonly retainedBuffers: () => Set<ArrayBufferLike>, private readonly clearFrames: () => void) {}
    receive(message: unknown): boolean {
        const packet = message as FramePacket | {type: 'viewportFrameStart' | 'viewportFrameEnd'; sessionId: string};
        if (packet?.type === 'viewportFrameStart') {
            this.clearFrames(); this.releaseUnused(); this.layouts.clear(); this.sessionId = packet.sessionId;
            return true;
        }
        if (packet?.type === 'viewportFrameEnd') {
            if (packet.sessionId === this.sessionId) this.reset();
            return true;
        }
        if (packet?.type !== 'viewportFrame') return false;
        if (packet.sessionId !== this.sessionId) {
            this.post({type: 'viewportBufferReturned', sessionId: packet.sessionId, stream: packet.stream, buffer: packet.buffer}, [packet.buffer]);
            return true;
        }
        if (packet.layout) this.layouts.set(packet.stream, {version: packet.layoutVersion, layout: packet.layout});
        const prepared = this.layouts.get(packet.stream);
        if (!prepared || prepared.version !== packet.layoutVersion) throw new Error('Missing viewport transfer layout');
        const frame = readFrameBuffer(packet.buffer, prepared.layout, packet.stream);
        this.owned.set(packet.buffer, {sessionId: packet.sessionId, stream: packet.stream});
        this.dispatch(packet.stream, frame);
        this.scheduleRelease();
        // Receipt and buffer return are separate: current presentation still owns the received buffer.
        const retained = this.retainedBuffers();
        let retainedPackets = 0;
        for (const [buffer, owner] of this.owned) {
            if (owner.stream === packet.stream && owner.sessionId === packet.sessionId && retained.has(buffer)) retainedPackets++;
        }
        this.post({type: 'viewportFrameReceived', sessionId: packet.sessionId, stream: packet.stream, sequence: packet.sequence, retainedPackets});
        return true;
    }
    scheduleRelease(): void {
        if (this.releaseScheduled) return;
        this.releaseScheduled = true;
        queueMicrotask(() => {this.releaseScheduled = false; this.releaseUnused();});
    }
    reset(): void {
        this.clearFrames(); this.releaseUnused(); this.layouts.clear(); this.sessionId = null;
    }
    private releaseUnused(): void {
        const retained = this.retainedBuffers();
        for (const [buffer, owner] of this.owned) {
            if (retained.has(buffer)) continue;
            this.owned.delete(buffer);
            this.post({type: 'viewportBufferReturned', ...owner, buffer}, [buffer]);
        }
    }
}
