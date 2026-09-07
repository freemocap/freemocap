import {RenderCommand, RenderEvent, type PreparedImage, type ScheduledRenderReply} from './render-protocol';

interface PendingRender {resolve: () => void; reject: (error: Error) => void; expected: RenderEvent}

/** Explicit presentation on the same camera worker used by live streaming. */
export class ScheduledRenderer {
    private readonly worker = new Worker(new URL('./offscreen-renderer.worker.ts', import.meta.url), {type: 'module'});
    private readonly pending = new Map<number, PendingRender>();
    private nextId = 0;
    private failure: Error | null = null;

    constructor(canvas: HTMLCanvasElement, private readonly onFailure: (error: Error) => void) {
        this.worker.onmessage = (event: MessageEvent<ScheduledRenderReply>): void => {
            const message = event.data;
            const pending = this.pending.get(message.id);
            if (message.type === RenderEvent.Failed) {this.fail(new Error(message.detail)); return;}
            if (!pending) return;
            if (message.type !== pending.expected) {this.fail(new Error('Unexpected camera renderer response')); return;}
            this.pending.delete(message.id);
            pending.resolve();
        };
        this.worker.onerror = (event): void => this.fail(new Error(event.message));
        this.worker.onmessageerror = (): void => this.fail(new Error('Camera renderer message could not be read'));
        try {
            const offscreen = canvas.transferControlToOffscreen();
            this.worker.postMessage({type: 'init', canvas: offscreen}, [offscreen]);
        } catch (error) {
            this.worker.terminate();
            throw error;
        }
    }

    async prepare(pixelBuffer: ArrayBuffer, width: number, height: number): Promise<PreparedImage> {
        const id = ++this.nextId;
        await this.request(id, RenderEvent.Prepared, (): void => this.worker.postMessage(
            {type: RenderCommand.Prepare, id, pixelBuffer, width, height}, [pixelBuffer]));
        return {id, width, height};
    }

    present(image: PreparedImage): Promise<void> {
        return this.request(image.id, RenderEvent.Presented, (): void => this.worker.postMessage({type: RenderCommand.Present, id: image.id}));
    }

    release(image: PreparedImage): void {
        if (!this.failure) this.worker.postMessage({type: RenderCommand.Release, id: image.id});
    }

    private request(id: number, expected: RenderEvent, send: () => void): Promise<void> {
        if (this.failure) return Promise.reject(this.failure);
        return new Promise((resolve, reject) => {
            this.pending.set(id, {resolve, reject, expected});
            try {send();} catch (error) {this.fail(error instanceof Error ? error : new Error(String(error)));}
        });
    }

    private fail(error: Error): void {
        if (this.failure) return;
        this.close(error);
        this.onFailure(error);
    }

    close(error = new Error('Camera renderer closed')): void {
        this.failure = error;
        this.worker.terminate();
        for (const pending of this.pending.values()) pending.reject(error);
        this.pending.clear();
    }
}
