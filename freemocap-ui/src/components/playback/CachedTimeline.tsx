import {useEffect, useRef} from 'react';

/** Samples cache residency independently of the video presentation loop. */
export function CachedTimeline({totalFrames, getCachedFrames}: {
    totalFrames: number; getCachedFrames: () => number[];
}): React.JSX.Element {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;
        const context = canvas.getContext('2d');
        if (!context) throw new Error('Cache timeline canvas is unavailable');
        const draw = (): void => {
            const width = Math.max(1, Math.round(canvas.clientWidth * devicePixelRatio));
            const height = Math.max(1, Math.round(canvas.clientHeight * devicePixelRatio));
            if (canvas.width !== width) canvas.width = width;
            if (canvas.height !== height) canvas.height = height;
            context.clearRect(0, 0, width, height);
            context.fillStyle = getComputedStyle(canvas).color;
            if (totalFrames < 1) return;
            for (const ordinal of getCachedFrames()) {
                context.fillRect(ordinal / totalFrames * width, 0, Math.max(1, width / totalFrames), height);
            }
        };
        draw();
        const timer = setInterval(draw, 250);
        return () => clearInterval(timer);
    }, [totalFrames, getCachedFrames]);
    return <canvas ref={canvasRef} className="playback-cache-timeline"
        aria-label="Buffered video"/>;
}
