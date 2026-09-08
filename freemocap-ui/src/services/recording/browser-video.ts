/** Native media presentation with an in-memory codec compatibility stream. */
export interface VideoEntry {videoId: string; filename: string; streamUrl: string; sizeBytes: number}

export class BrowserVideo {
    private abort = new AbortController();
    private objectUrl: string | null = null;
    private converted = false;
    private generation = 0;
    private closed = false;

    constructor(readonly element: HTMLVideoElement, private readonly url: string,
        private readonly duration: number, private readonly fail: (error: Error) => void) {}

    async open(time: number): Promise<void> {
        this.element.preload = 'auto';
        this.element.muted = true;
        const ready = this.waitFor('loadeddata');
        this.element.src = this.url;
        this.element.load();
        try {await ready;}
        catch (error) {
            if (this.closed) return;
            const code = this.element.error?.code;
            if (code !== MediaError.MEDIA_ERR_SRC_NOT_SUPPORTED && code !== MediaError.MEDIA_ERR_DECODE) throw error;
            this.converted = true;
            await this.restart(time);
            return;
        }
        if (!this.closed) await this.seek(time);
    }

    async seek(time: number): Promise<void> {
        if (this.closed) return;
        const buffered = this.element.buffered;
        const available = Array.from({length: buffered.length}, (_, i) =>
            time >= buffered.start(i) && time < buffered.end(i)).some(Boolean);
        if (this.converted && !available) {await this.restart(time); return;}
        if (Math.abs(this.element.currentTime - time) < 0.001) return;
        const ready = this.waitFor('seeked');
        this.element.currentTime = time;
        await ready;
    }

    private waitFor(event: string): Promise<void> {
        const signal = this.abort.signal;
        return new Promise((resolve, reject) => {
            const cleanup = (): void => {
                clearTimeout(timer); this.element.removeEventListener(event, done);
                this.element.removeEventListener('error', error); signal.removeEventListener('abort', cancelled);
            };
            const done = (): void => {cleanup(); resolve();};
            const error = (): void => {cleanup(); reject(new Error(this.element.error?.message ?? 'Video failed'));};
            const cancelled = (): void => {cleanup(); reject(signal.reason);};
            const timer = setTimeout(() => {cleanup(); reject(new Error(`Video timed out waiting for ${event}`));}, 30000);
            this.element.addEventListener(event, done, {once: true});
            this.element.addEventListener('error', error, {once: true});
            signal.addEventListener('abort', cancelled, {once: true});
        });
    }

    private async restart(time: number): Promise<void> {
        this.abort.abort(); this.abort = new AbortController();
        const signal = this.abort.signal;
        const generation = ++this.generation;
        const media = new MediaSource();
        const mime = 'video/mp4; codecs="avc1.42E01F"';
        if (!MediaSource.isTypeSupported(mime)) throw new Error('This runtime cannot play the H.264 compatibility stream');
        if (this.objectUrl) URL.revokeObjectURL(this.objectUrl);
        this.objectUrl = URL.createObjectURL(media);
        this.element.src = this.objectUrl;
        const ready = this.waitFor('loadeddata');
        const pump = async (): Promise<void> => {
            await new Promise<void>((resolve, reject) => {
                media.addEventListener('sourceopen', () => resolve(), {once: true});
                signal.addEventListener('abort', () => reject(new DOMException('Cancelled', 'AbortError')), {once: true});
            });
            const buffer = media.addSourceBuffer(mime);
            buffer.timestampOffset = time;
            media.duration = this.duration;
            this.element.currentTime = time;
            const url = new URL(this.url, location.href);
            url.pathname += '/browser';
            url.searchParams.set('start_seconds', String(time));
            url.searchParams.set('duration_seconds', String(Math.max(0.1, this.duration - time)));
            const response = await fetch(url, {signal});
            if (!response.ok || !response.body) throw new Error(`Video conversion failed (${response.status}): ${await response.text()}`);
            const reader = response.body.getReader();
            const update = (operation: () => void): Promise<void> => new Promise((resolve, reject) => {
                const cleanup = (): void => {buffer.removeEventListener('updateend', done); buffer.removeEventListener('error', failed); signal.removeEventListener('abort', cancelled);};
                const done = (): void => {cleanup(); resolve();};
                const failed = (): void => {cleanup(); reject(new Error('Video buffer rejected the stream'));};
                const cancelled = (): void => {cleanup(); reject(new DOMException('Cancelled', 'AbortError'));};
                buffer.addEventListener('updateend', done, {once: true}); buffer.addEventListener('error', failed, {once: true});
                signal.addEventListener('abort', cancelled, {once: true});
                try {operation();} catch (error) {cleanup(); reject(error);}
            });
            try {
                for (;;) {
                    if (signal.aborted) return;
                    if (buffer.buffered.length && buffer.buffered.end(buffer.buffered.length - 1) - this.element.currentTime > 8) {
                        await new Promise<void>(resolve => setTimeout(resolve, 100)); continue;
                    }
                    if (this.element.currentTime > 3 && buffer.buffered.length && buffer.buffered.start(0) < this.element.currentTime - 3)
                        await update(() => buffer.remove(0, this.element.currentTime - 2));
                    const chunk = await reader.read();
                    if (chunk.done) {if (media.readyState === 'open') media.endOfStream(); return;}
                    await update(() => buffer.appendBuffer(chunk.value));
                }
            } finally {await reader.cancel(); reader.releaseLock();}
        };
        void pump().catch(error => {
            if (!signal.aborted && generation === this.generation) {this.fail(error instanceof Error ? error : new Error(String(error))); this.abort.abort(error);}
        });
        await ready;
        if (!signal.aborted) this.element.currentTime = time;
    }

    close(): void {
        this.closed = true; this.abort.abort(); this.element.pause();
        this.element.removeAttribute('src'); this.element.load();
        if (this.objectUrl) URL.revokeObjectURL(this.objectUrl);
    }
}
