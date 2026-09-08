import {useEffect, useState} from 'react';

/** Low-frequency telemetry; image presentation never updates React state here. */
export function DisplayFramerate({getDisplayFps}: {getDisplayFps: () => number | null}): React.JSX.Element {
    const [fps, setFps] = useState<number | null>(null);
    useEffect(() => {
        const timer = setInterval(() => setFps(getDisplayFps()), 250);
        return () => clearInterval(timer);
    }, [getDisplayFps]);
    return <span className="playback-display-framerate" title="Actual synchronized images presented per second. Playback skips frames when behind to maintain the selected speed.">
        {'\u00b7'} Display: {fps === null ? '\u2014' : fps.toFixed(2)} fps
    </span>;
}
