/** Draws viewport timing text without changing DOM content or canvas dimensions. */
export class PlaybackLabel {
    private readonly context: CanvasRenderingContext2D;
    constructor(private readonly canvas: HTMLCanvasElement) {
        const context = canvas.getContext('2d');
        if (!context) throw new Error('Playback label rendering is unavailable');
        this.context = context;
        context.font = '11px monospace';
        context.fillStyle = '#00ff88';
        context.textAlign = 'right';
    }
    draw(text: string): void {
        this.context.clearRect(0, 0, this.canvas.width, this.canvas.height);
        this.context.fillText(text, this.canvas.width - 5, 13);
    }
}
