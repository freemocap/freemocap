// src/components/framerate-viewer/FrameRateViewer.tsx
import {useEffect, useRef, useState} from "react"
import clsx from "clsx"
import FramerateTimeseriesView from "./FramerateTimeseriesView"
import FramerateHistogramView from "./FramerateHistogramView"
import FramerateStatisticsView from "./FramerateStatisticsView"
import { useTranslation } from "react-i18next"
import { useServer } from "@/services/server/ServerContextProvider"

export const frontendColor: string = "var(--chart-frontend)"
export const backendColor: string = "var(--chart-backend)"

const COLLAPSED_POLL_MS = 500;

const FramerateCollapsedView = () => {
    const { t } = useTranslation()
    const { getFramerateStore } = useServer()
    const serverRef = useRef<HTMLSpanElement>(null)
    const displayRef = useRef<HTMLSpanElement>(null)

    useEffect(() => {
        const tick = () => {
            const snap = getFramerateStore().getSnapshot()
            const serverFps = snap.currentBackendFramerate?.mean_frames_per_second
            const displayFps = snap.currentFrontendFramerate?.mean_frames_per_second
            if (serverRef.current) serverRef.current.textContent = serverFps != null ? serverFps.toFixed(1) : "--"
            if (displayRef.current) displayRef.current.textContent = displayFps != null ? displayFps.toFixed(1) : "--"
        }
        tick()
        const id = setInterval(tick, COLLAPSED_POLL_MS)
        return () => clearInterval(id)
    }, [getFramerateStore])

    return (
        <div className="framerate-collapsed-summary flex items-center h-full gap-2">
            <p className="text bg text-gray">{t("cameraPerformanceMetrics")}</p>
            <p className="text sm text-gray">|</p>
            <p className="text sm text-gray">{t("server")}: <span ref={serverRef}>--</span> fps</p>
            <p className="text sm text-gray">|</p>
            <p className="text sm text-gray">{t("display")}: <span ref={displayRef}>--</span> fps</p>
        </div>
    )
}

export const FramerateViewerPanel = ({ isCollapsed = false }: { isCollapsed?: boolean }) => {
    const { t } = useTranslation()
    const [showStats, setShowStats] = useState(true)
    const [showTimeseries, setShowTimeseries] = useState(true)
    const [showHistogram, setShowHistogram] = useState(true)

    if (isCollapsed) return <FramerateCollapsedView />

    return (
        <div className="framerate-viewer br-1">
            {/* Header */}
            <div className="framerate-viewer-header">
                <p className="text bg text-gray">{t('cameraPerformanceMetrics')}</p>
                <div className="flex gap-1">
                    <button
                        className={clsx("button sm br-1", showStats && "isOn")}
                        onClick={() => setShowStats(v => !v)}
                        title={t("statisticsView")}
                    >
                        <p className="text sm">Stats</p>
                    </button>
                    <button
                        className={clsx("button sm br-1", showTimeseries && "isOn")}
                        onClick={() => setShowTimeseries(v => !v)}
                        title={t("timelineView")}
                    >
                        <p className="text sm">Timeline</p>
                    </button>
                    <button
                        className={clsx("button sm br-1", showHistogram && "isOn")}
                        onClick={() => setShowHistogram(v => !v)}
                        title={t("distributionView")}
                    >
                        <p className="text sm">Distribution</p>
                    </button>
                </div>
            </div>

            {/* Stats table */}
            {showStats && (
                <div className="framerate-stats-wrapper br-1 border-1 border-black p-1">
                    <FramerateStatisticsView compact={true} />
                </div>
            )}

            {/* Chart area */}
            <div className={clsx("framerate-charts-area", showTimeseries && showHistogram ? "row" : "column")}>
                {showTimeseries && (
                    <div className="framerate-chart-panel border-1 border-black br-1">
                        <FramerateTimeseriesView
                            frontendColor={frontendColor}
                            backendColor={backendColor}
                            title={t("framerateTimeline")}
                        />
                    </div>
                )}
                {showHistogram && (
                    <div className="framerate-chart-panel border-1 border-black br-1">
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
