import React, {useCallback} from "react";
import {useMocap} from "@/hooks/useMocap";
import {DEFAULT_REALTIME_FILTER_CONFIG, RealtimeFilterConfig} from "@/store/slices/mocap";

/** Warm amber for section headings — visible on dark backgrounds. */
const SECTION_COLOR = "#ffb74d";

interface SkeletonFilterConfigPanelProps {
    updateSkeletonFilterConfig?: (updates: Partial<RealtimeFilterConfig>) => void;
    replaceSkeletonFilterConfig?: (config: RealtimeFilterConfig) => void;
}

export const SkeletonFilterConfigPanel: React.FC<SkeletonFilterConfigPanelProps> = ({
    updateSkeletonFilterConfig: updateSkeletonFilterConfigProp,
    replaceSkeletonFilterConfig: replaceSkeletonFilterConfigProp,
}) => {
    const {
        skeletonFilterConfig,
        updateSkeletonFilterConfig: updateSkeletonFilterConfigHook,
        replaceSkeletonFilterConfig: replaceSkeletonFilterConfigHook,
        isLoading,
    } = useMocap();
    const updateSkeletonFilterConfig = updateSkeletonFilterConfigProp ?? updateSkeletonFilterConfigHook;
    const replaceSkeletonFilterConfig = replaceSkeletonFilterConfigProp ?? replaceSkeletonFilterConfigHook;

    const handleResetDefaults = useCallback(() => {
        replaceSkeletonFilterConfig({...DEFAULT_REALTIME_FILTER_CONFIG});
    }, [replaceSkeletonFilterConfig]);

    return (
        <div className="flex flex-col gap-1">
            <div className="flex flex-row justify-content-space-between items-center">
                <p className="text sm text-gray" style={{fontWeight: 600}}>Skeleton Filter</p>
                <button
                    className="button sm secondary"
                    onClick={handleResetDefaults}
                    disabled={isLoading}
                    style={{fontSize: 11}}
                >
                    Reset Defaults
                </button>
            </div>

            {/* === Point Gate === */}
            <p className="text sm" style={{color: SECTION_COLOR, fontWeight: 600}}>Point Gate</p>

            <div title="Reject triangulated points whose mean reprojection error exceeds this. Higher = keep more (noisier) points.">
                <p className="text sm text-gray">
                    Max Reproj Error: {skeletonFilterConfig.max_reprojection_error_px.toFixed(0)} px
                </p>
                <input
                    type="range"
                    value={skeletonFilterConfig.max_reprojection_error_px}
                    onChange={(e) => updateSkeletonFilterConfig({max_reprojection_error_px: parseFloat(e.target.value)})}
                    min={5} max={200} step={1} disabled={isLoading}
                    className="w-full"
                    style={{accentColor: 'var(--color-info)'}}
                />
            </div>

            <div title="Reject points moving faster than this between frames. Catches teleportation spikes. Human limbs rarely exceed ~15 m/s.">
                <p className="text sm text-gray">
                    Max Velocity: {skeletonFilterConfig.max_velocity_m_per_s.toFixed(0)} m/s
                </p>
                <input
                    type="range"
                    value={skeletonFilterConfig.max_velocity_m_per_s}
                    onChange={(e) => updateSkeletonFilterConfig({max_velocity_m_per_s: parseFloat(e.target.value)})}
                    min={5} max={200} step={1} disabled={isLoading}
                    className="w-full"
                    style={{accentColor: 'var(--color-info)'}}
                />
            </div>

            <div title="After this many consecutive velocity rejections, accept unconditionally to prevent permanent lockout.">
                <p className="text sm text-gray">
                    Max Rejected Streak: {skeletonFilterConfig.max_rejected_streak}
                </p>
                <input
                    type="range"
                    value={skeletonFilterConfig.max_rejected_streak}
                    onChange={(e) => updateSkeletonFilterConfig({max_rejected_streak: parseInt(e.target.value)})}
                    min={1} max={30} step={1} disabled={isLoading}
                    className="w-full"
                    style={{accentColor: 'var(--color-info)'}}
                />
            </div>

            <div style={{height: 1, backgroundColor: 'var(--color-border-secondary)', margin: '4px 0'}} />

            {/* === One Euro Filter === */}
            <p className="text sm" style={{color: SECTION_COLOR, fontWeight: 600}}>One Euro Filter</p>

            <div title="Minimum cutoff frequency (Hz) — controls how quickly the filter settles when motion stops. At 30 fps: 0.5 Hz ≈ 0.8 s settling, 1.0 Hz ≈ 0.4 s, 2.0 Hz ≈ 0.2 s. Raise if skeleton feels dragged; lower if it jitters at rest.">
                <p className="text sm text-gray">
                    Min Cutoff: {skeletonFilterConfig.min_cutoff.toFixed(2)} Hz
                </p>
                <input
                    type="range"
                    value={skeletonFilterConfig.min_cutoff}
                    onChange={(e) => updateSkeletonFilterConfig({min_cutoff: parseFloat(e.target.value)})}
                    min={0.1} max={10} step={0.1} disabled={isLoading}
                    className="w-full"
                    style={{accentColor: 'var(--color-info)'}}
                />
            </div>

            <div title="Speed coefficient (1/mm). Raises the cutoff during motion so fast movements pass through with less lag. Positions are in millimetres, so good values are 0.003–0.02. At 0.007: walking speed (500 mm/s) adds 3.5 Hz; a fast swing (2000 mm/s) adds 14 Hz. Zero = same smoothing at all speeds.">
                <p className="text sm text-gray">
                    Beta: {skeletonFilterConfig.beta.toFixed(3)} /mm
                </p>
                <input
                    type="range"
                    value={skeletonFilterConfig.beta}
                    onChange={(e) => updateSkeletonFilterConfig({beta: parseFloat(e.target.value)})}
                    min={0} max={0.05} step={0.001} disabled={isLoading}
                    className="w-full"
                    style={{accentColor: 'var(--color-info)'}}
                />
            </div>

            <div title="Cutoff frequency (Hz) for the internal velocity estimator. Controls how quickly the filter adapts to speed changes. 1.0 Hz is a safe default — lower to 0.3–0.5 if noisy triangulation causes the skeleton to over-react to speed spikes.">
                <p className="text sm text-gray">
                    D Cutoff: {skeletonFilterConfig.d_cutoff.toFixed(2)} Hz
                </p>
                <input
                    type="range"
                    value={skeletonFilterConfig.d_cutoff}
                    onChange={(e) => updateSkeletonFilterConfig({d_cutoff: parseFloat(e.target.value)})}
                    min={0.1} max={5} step={0.1} disabled={isLoading}
                    className="w-full"
                    style={{accentColor: 'var(--color-info)'}}
                />
            </div>

            <div style={{height: 1, backgroundColor: 'var(--color-border-secondary)', margin: '4px 0'}} />

            {/* === FABRIK === */}
            <p className="text sm" style={{color: SECTION_COLOR, fontWeight: 600}}>FABRIK</p>

            <div title="Max solver iterations per frame for bone length constraint enforcement. 10–30 is usually plenty.">
                <p className="text sm text-gray">
                    Max Iterations: {skeletonFilterConfig.fabrik_max_iterations}
                </p>
                <input
                    type="range"
                    value={skeletonFilterConfig.fabrik_max_iterations}
                    onChange={(e) => updateSkeletonFilterConfig({fabrik_max_iterations: parseInt(e.target.value)})}
                    min={1} max={100} step={1} disabled={isLoading}
                    className="w-full"
                    style={{accentColor: 'var(--color-info)'}}
                />
            </div>

            <div style={{height: 1, backgroundColor: 'var(--color-border-secondary)', margin: '4px 0'}} />

            {/* === Body Model === */}
            <p className="text sm" style={{color: SECTION_COLOR, fontWeight: 600}}>Body Model</p>

            <div
                className="input-with-string"
                title="Subject's approximate height. Scales the anthropometric bone length prior. Doesn't need to be exact."
            >
                <input
                    className="input-field text md"
                    type="number"
                    value={skeletonFilterConfig.height_meters}
                    onChange={(e) => {
                        const val = parseFloat(e.target.value);
                        if (!isNaN(val) && val > 0) {
                            updateSkeletonFilterConfig({height_meters: val});
                        }
                    }}
                    step={0.01} min={0.5} max={3.0}
                    disabled={isLoading}
                    placeholder="Height (m)"
                />
            </div>

            <div title="Expected measurement noise (meters). Higher = trust raw positions less, rely more on prior estimates.">
                <p className="text sm text-gray">
                    Noise Sigma: {skeletonFilterConfig.noise_sigma.toFixed(4)} m
                </p>
                <input
                    type="range"
                    value={skeletonFilterConfig.noise_sigma}
                    onChange={(e) => updateSkeletonFilterConfig({noise_sigma: parseFloat(e.target.value)})}
                    min={0.001} max={0.05} step={0.001} disabled={isLoading}
                    className="w-full"
                    style={{accentColor: 'var(--color-info)'}}
                />
            </div>
        </div>
    );
};
