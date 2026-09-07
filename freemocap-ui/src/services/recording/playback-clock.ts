/** Wall-clock position and actual completed multiframe presentation rate. */
export class PlaybackClock {
    private readonly presentations: number[] = [];
    private positionStartedAt: number;
    constructor(private startFrame: number, private readonly startedAt: number,
        private readonly framesPerSecond: number) {
        this.positionStartedAt = startedAt;
        if (!Number.isFinite(framesPerSecond) || framesPerSecond <= 0) throw new Error('Invalid playback frame rate');
    }
    frameAt(now: number): number {
        return this.startFrame + Math.floor(Math.max(0, now - this.positionStartedAt) * this.framesPerSecond / 1000);
    }
    resumeAt(frame: number, now: number): void {
        this.startFrame = frame;
        this.positionStartedAt = now;
    }
    presented(now: number): void {
        this.presentations.push(now);
        this.trim(now);
    }
    displayFps(now: number): number | null {
        const elapsed = Math.min(1000, Math.max(0, now - this.startedAt));
        if (elapsed < 250) return null;
        this.trim(now);
        return this.presentations.length * 1000 / elapsed;
    }
    private trim(now: number): void {
        while (this.presentations.length && this.presentations[0] <= now - 1000) this.presentations.shift();
    }
}
