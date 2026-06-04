// src/components/framerate-viewer/FrameRateViewer.tsx
import {useEffect, useRef, useState} from "react"
import FramerateTimeseriesView from "./FramerateTimeseriesView"
import FramerateHistogramView from "./FramerateHistogramView"
import FramerateStatisticsView from "./FramerateStatisticsView"
import {useTranslation} from "react-i18next";
import {useServer} from "@/services/server/ServerContextProvider";
import {DetailedFramerate} from "@/services/server/server-helpers/framerate-store";

export const frontendColor: string = "#1976D2"
export const backendColor: string = "#ff4d00"

const fmtFps = (fr: DetailedFramerate | null): string => {
    if (!fr || !fr.frame_duration_mean || fr.frame_duration_mean <= 0) return "-- fps";
    return `${(1000 / fr.frame_duration_mean).toFixed(1)} fps ±${fr.frame_duration_stddev.toFixed(1)}ms`;
};

const FramerateCollapsedView = () => {
    const {getFramerateStore} = useServer();
    const backendRef = useRef<HTMLSpanElement>(null);
    const frontendRef = useRef<HTMLSpanElement>(null);

    useEffect(() => {
        const tick = () => {
            const snap = getFramerateStore().getSnapshot();
            if (backendRef.current) backendRef.current.textContent = fmtFps(snap.aggregateBackendFramerate);
            if (frontendRef.current) frontendRef.current.textContent = fmtFps(snap.aggregateFrontendFramerate);
        };
        tick();
        const id = setInterval(tick, 1000);
        return () => clearInterval(id);
    }, [getFramerateStore]);

    return (
        <div className="flex flex-row items-center gap-1" style={{height: '100%', overflow: 'hidden', paddingLeft: 8, paddingRight: 8}}>
            <p className="text sm text-gray text-nowrap" style={{flexShrink: 0, margin: 0, fontWeight: 'bold'}}>
                Camera Performance
            </p>
            <p className="text sm text-nowrap" style={{color: backendColor, flexShrink: 0, margin: 0}}>
                Server: <span ref={backendRef}>-- fps</span>
            </p>
            <p className="text sm text-nowrap" style={{color: frontendColor, flexShrink: 0, margin: 0}}>
                Display: <span ref={frontendRef}>-- fps</span>
            </p>
        </div>
    );
};

export const FramerateViewerPanel = ({isCollapsed = false}: { isCollapsed?: boolean }) => {
    if (isCollapsed) return <FramerateCollapsedView/>;
    return <FramerateViewerPanelExpanded/>;
};

const FramerateViewerPanelExpanded = () => {
    const { t } = useTranslation();
    const [showStats, setShowStats] = useState(true)
    const [showTimeseries, setShowTimeseries] = useState(true)
    const [showHistogram, setShowHistogram] = useState(true)

    return (
        <div className="flex flex-col overflow-hidden bg-dark" style={{height: '100%', padding: 4}}>
            <div className="flex flex-row items-center justify-content-space-between" style={{marginBottom: 2, paddingLeft: 4, paddingRight: 4}}>
                <p className="text sm text-white text-nowrap" style={{margin: 0}}>
                    {t('cameraPerformanceMetrics')}
                </p>

                <div className="flex flex-row" style={{gap: 2}}>
                    <button
                        title={t("statisticsView")}
                        className="button icon-button br-1"
                        onClick={() => setShowStats((v) => !v)}
                        style={{opacity: showStats ? 1 : 0.3, padding: 2}}
                    >
                        <span className="icon settings-icon icon-size-20"/>
                    </button>
                    <button
                        title={t("timelineView")}
                        className="button icon-button br-1"
                        onClick={() => setShowTimeseries((v) => !v)}
                        style={{opacity: showTimeseries ? 1 : 0.3, padding: 2}}
                    >
                        <span className="icon play-icon icon-size-20"/>
                    </button>
                    <button
                        title={t("distributionView")}
                        className="button icon-button br-1"
                        onClick={() => setShowHistogram((v) => !v)}
                        style={{opacity: showHistogram ? 1 : 0.3, padding: 2}}
                    >
                        <span className="icon frameforward-icon icon-size-20"/>
                    </button>
                </div>
            </div>

            {showStats && (
                <div style={{paddingLeft: 2, paddingRight: 2, marginBottom: 2}}>
                    <div className="bg-middark br-1 border-1 border-mid-black" style={{padding: 2}}>
                        <FramerateStatisticsView compact={true} />
                    </div>
                </div>
            )}

            <div className="flex overflow-hidden" style={{flex: 1, flexDirection: (showTimeseries && showHistogram) ? 'row' : 'column', gap: 2}}>
                {showTimeseries && (
                    <div className="flex flex-col flex-1 border-1 border-mid-black overflow-hidden">
                        <FramerateTimeseriesView
                            frontendColor={frontendColor}
                            backendColor={backendColor}
                            title={t("framerateTimeline")}
                        />
                    </div>
                )}

                {showHistogram && (
                    <div className="flex flex-col flex-1 border-1 border-mid-black overflow-hidden">
                        <FramerateHistogramView
                            frontendColor={frontendColor}
                            backendColor={backendColor}
                            title={t("framerateDistribution")}
                        />
                    </div>
                )}
            </div>
        </div>
    )
}

export default FramerateViewerPanel
