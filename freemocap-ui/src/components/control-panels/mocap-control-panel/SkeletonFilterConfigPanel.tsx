import React, {useCallback} from "react";
import {useTranslation} from "react-i18next";
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
    const {t} = useTranslation();
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
                <p className="text sm text-gray" style={{fontWeight: 600}}>{t("filter.skeletonFilter")}</p>
                <button
                    className="button sm secondary"
                    onClick={handleResetDefaults}
                    disabled={isLoading}
                    style={{fontSize: 11}}
                >
                    {t("filter.resetDefaults")}
                </button>
            </div>

            {/* === Point Gate === */}
            <p className="text sm" style={{color: SECTION_COLOR, fontWeight: 600}}>{t("filter.pointGate")}</p>

            <div title={t("filter.maxReprojectionHelp")}>
                <p className="text sm text-gray">
                    {t("filter.maxReprojectionError")}: {skeletonFilterConfig.max_reprojection_error_px.toFixed(0)} px
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

            <div title={t("filter.maxVelocityHelp")}>
                <p className="text sm text-gray">
                    {t("filter.maxVelocity")}: {skeletonFilterConfig.max_velocity_m_per_s.toFixed(0)} m/s
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

            <div title={t("filter.maxRejectedStreakHelp")}>
                <p className="text sm text-gray">
                    {t("filter.maxRejectedStreak")}: {skeletonFilterConfig.max_rejected_streak}
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
            <p className="text sm" style={{color: SECTION_COLOR, fontWeight: 600}}>{t("filter.oneEuro")}</p>

            <div title={t("filter.minCutoffHelp")}>
                <p className="text sm text-gray">
                    {t("filter.minCutoff")}: {skeletonFilterConfig.min_cutoff.toFixed(2)} Hz
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

            <div title={t("filter.betaHelp")}>
                <p className="text sm text-gray">
                    {t("filter.beta")}: {skeletonFilterConfig.beta.toFixed(3)} /mm
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

            <div title={t("filter.dCutoffHelp")}>
                <p className="text sm text-gray">
                    {t("filter.dCutoff")}: {skeletonFilterConfig.d_cutoff.toFixed(2)} Hz
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

            <div title={t("filter.maxIterationsHelp")}>
                <p className="text sm text-gray">
                    {t("filter.maxIterations")}: {skeletonFilterConfig.fabrik_max_iterations}
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
            <p className="text sm" style={{color: SECTION_COLOR, fontWeight: 600}}>{t("filter.bodyModel")}</p>

            <div
                className="input-with-string"
                title={t("filter.heightHelp")}
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
                    placeholder={t("filter.heightMeters")}
                />
            </div>

            <div title={t("filter.noiseSigmaHelp")}>
                <p className="text sm text-gray">
                    {t("filter.noiseSigma")}: {skeletonFilterConfig.noise_sigma.toFixed(4)} m
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
