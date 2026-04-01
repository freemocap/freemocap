// src/components/framerate-viewer/FramerateTimeseriesView.tsx
import {useCallback, useRef} from "react"
import * as d3 from "d3"
import {useTheme} from "@mui/material/styles"
import {TimestampedSample} from "@/services/server/server-helpers/framerate-store"
import {applyAxisStyles} from "@/components/framerate-viewer/d3ChartUtils"
import BaseD3ChartView, {ChartScaffolding, ChartLifecycle} from "@/components/framerate-viewer/BaseD3ChartView"
import {useTranslation} from "react-i18next"
import {useServer} from "@/services/server/ServerContextProvider"

type FramerateTimeseriesProps = {
    frontendColor: string
    backendColor: string
    title?: string
}

type FpsSample = { timestamp: number; value: number }

/** How many seconds of data the rolling window shows. */
const WINDOW_SECONDS = 60

/** Fixed relative-time tick positions (seconds ago). These never change,
 *  so D3's axis join always matches existing tick elements — zero DOM churn. */
const RELATIVE_TICK_SECONDS = [0, -15, -30, -45, -60]

/**
 * Convert duration samples to FPS in-place into a reusable output array.
 * Avoids allocating a fresh array on every update call.
 */
function toFpsInPlace(
    samples: TimestampedSample[],
    out: FpsSample[],
): void {
    let writeIdx = 0
    for (let i = 0; i < samples.length; i++) {
        const s = samples[i]
        if (s.value > 0) {
            if (writeIdx < out.length) {
                out[writeIdx].timestamp = s.timestamp
                out[writeIdx].value = 1000 / s.value
            } else {
                out.push({timestamp: s.timestamp, value: 1000 / s.value})
            }
            writeIdx++
        }
    }
    out.length = writeIdx
}

/**
 * Persistent mutable state shared between initChart and updateChart.
 * Stored in a ref so it survives across data updates without triggering
 * React re-renders or D3 DOM teardown.
 */
type ChartState = {
    frontendPath: d3.Selection<SVGPathElement, unknown, null, undefined>
    backendPath: d3.Selection<SVGPathElement, unknown, null, undefined>
    xScale: d3.ScaleLinear<number, number>
    yScale: d3.ScaleLinear<number, number>
    frontendData: FpsSample[]
    backendData: FpsSample[]
    windowEnd: number
    // Reusable scratch arrays to avoid per-update allocations
    frontendFpsBuf: FpsSample[]
    backendFpsBuf: FpsSample[]
}

export default function FramerateTimeseriesView({
    frontendColor,
    backendColor,
    title = "Framerate Over Time",
}: FramerateTimeseriesProps) {
    const theme = useTheme()
    const {t} = useTranslation()
    const stateRef = useRef<ChartState | null>(null)
    const {getFramerateStore} = useServer()

    // initChart — creates persistent SVG elements that live for the chart's lifetime
    const initChart = useCallback(
        ({svg, chartArea, xAxisG, yAxisG, width, height}: ChartScaffolding): ChartLifecycle => {
            // X-axis uses relative seconds (0 = now, -60 = oldest).
            // Fixed domain means axis ticks never enter/exit — zero DOM churn.
            const xScale = d3.scaleLinear().domain([-WINDOW_SECONDS, 0]).range([0, width])
            const yScale = d3.scaleLinear().range([height, 0])

            // Build the x-axis once with fixed tick values
            const xAxisGen = d3
                .axisBottom(xScale)
                .tickValues(RELATIVE_TICK_SECONDS)
                .tickSize(-height)
                .tickFormat((d) => {
                    const sec = d as number
                    return sec === 0 ? "now" : `${sec}s`
                })
            xAxisG.call(xAxisGen)

            // Build the y-axis with initial placeholder ticks
            const yAxisGen = d3
                .axisLeft(yScale)
                .ticks(Math.max(2, Math.min(5, Math.floor(height / 30))))
                .tickSize(-width)
            yAxisG.call(yAxisGen)

            applyAxisStyles(chartArea, theme)

            // Axis labels (appended to svg root group, outside clip-path)
            svg.append("text")
                .attr("class", "x-axis-label")
                .attr("x", width / 2)
                .attr("y", height + 32)
                .attr("text-anchor", "middle")
                .style("font-family", "monospace")
                .style("font-size", "10px")
                .style("fill", theme.palette.text.secondary)
                .text("Time")

            svg.append("text")
                .attr("class", "y-axis-label")
                .attr("transform", "rotate(-90)")
                .attr("x", -height / 2)
                .attr("y", -28)
                .attr("text-anchor", "middle")
                .style("font-family", "monospace")
                .style("font-size", "10px")
                .style("fill", theme.palette.text.secondary)
                .text("FPS")

            // Persistent path elements — one per series, never removed
            const frontendPath = chartArea.append("path")
                .attr("fill", "none")
                .attr("stroke", frontendColor)
                .attr("stroke-width", 1.5)

            const backendPath = chartArea.append("path")
                .attr("fill", "none")
                .attr("stroke", backendColor)
                .attr("stroke-width", 1.5)

            // Persistent empty-state text (hidden by default)
            chartArea.append("text")
                .attr("class", "empty-text")
                .attr("x", width / 2)
                .attr("y", height / 2)
                .attr("text-anchor", "middle")
                .attr("dominant-baseline", "central")
                .style("font-family", "monospace")
                .style("font-size", "12px")
                .style("fill", theme.palette.text.disabled)
                .style("display", "none")

            stateRef.current = {
                frontendPath,
                backendPath,
                xScale,
                yScale,
                frontendData: [],
                backendData: [],
                windowEnd: 0,
                frontendFpsBuf: [],
                backendFpsBuf: [],
            }

            return {
                cleanup: () => {
                    stateRef.current = null
                },
            }
        },
        [theme, frontendColor, backendColor]
    )

    // updateChart — only mutates path `d` attrs and y-axis ticks. Zero DOM adds/removes for x-axis.
    const updateChart = useCallback(
        ({svg, yAxisG, width, height}: ChartScaffolding) => {
            const state = stateRef.current
            if (!state) return

            // Read fresh data directly from the store — no React state involved.
            const snapshot = getFramerateStore().getSnapshot()
            const recentFrontendDurations = snapshot.recentFrontendDurations
            const recentBackendDurations = snapshot.recentBackendDurations

            // Convert durations→FPS using reusable scratch buffers
            toFpsInPlace(recentFrontendDurations, state.frontendFpsBuf)
            toFpsInPlace(recentBackendDurations, state.backendFpsBuf)

            const frontendFps = state.frontendFpsBuf
            const backendFps = state.backendFpsBuf

            const emptyText = svg.select<SVGTextElement>(".empty-text")

            if (frontendFps.length === 0 && backendFps.length === 0) {
                state.frontendPath.attr("d", null)
                state.backendPath.attr("d", null)
                emptyText.style("display", null).text(t("waitingForData"))
                return
            }

            emptyText.style("display", "none")

            // Find latest timestamp without allocating
            let latestTimestamp = -Infinity
            for (let i = 0; i < frontendFps.length; i++) {
                if (frontendFps[i].timestamp > latestTimestamp) latestTimestamp = frontendFps[i].timestamp
            }
            for (let i = 0; i < backendFps.length; i++) {
                if (backendFps[i].timestamp > latestTimestamp) latestTimestamp = backendFps[i].timestamp
            }

            const windowEnd = latestTimestamp
            const windowStart = windowEnd - WINDOW_SECONDS * 1000
            state.windowEnd = windowEnd

            // Filter to window
            state.frontendData = frontendFps.filter((d) => d.timestamp >= windowStart)
            state.backendData = backendFps.filter((d) => d.timestamp >= windowStart)

            if (state.frontendData.length === 0 && state.backendData.length === 0) {
                state.frontendPath.attr("d", null)
                state.backendPath.attr("d", null)
                emptyText.style("display", null).text(t("waitingForData"))
                return
            }

            // Compute y-domain without allocating a merged array
            let yMin = Infinity
            let yMax = -Infinity
            for (let i = 0; i < state.frontendData.length; i++) {
                const v = state.frontendData[i].value
                if (v < yMin) yMin = v
                if (v > yMax) yMax = v
            }
            for (let i = 0; i < state.backendData.length; i++) {
                const v = state.backendData[i].value
                if (v < yMin) yMin = v
                if (v > yMax) yMax = v
            }

            const yRange = yMax - yMin
            const yPadding = Math.max(1, yRange * 0.3)
            state.yScale.domain([Math.max(0, yMin - yPadding), yMax + yPadding])

            // Only y-axis needs updating (domain changes with data).
            // X-axis is fixed at [-60, 0] with stable tick elements.
            const yAxisGen = d3
                .axisLeft(state.yScale)
                .ticks(Math.max(2, Math.min(5, Math.floor(height / 30))))
                .tickSize(-width)
            yAxisG.call(yAxisGen)
            applyAxisStyles(svg, theme)

            // Line generator maps absolute timestamps → relative seconds for the fixed x-axis
            const line = d3
                .line<FpsSample>()
                .x((d) => state.xScale((d.timestamp - windowEnd) / 1000))
                .y((d) => state.yScale(d.value))
                .curve(d3.curveLinear)

            state.frontendPath.attr("d", state.frontendData.length > 0 ? line(state.frontendData) : null)
            state.backendPath.attr("d", state.backendData.length > 0 ? line(state.backendData) : null)
        },
        [getFramerateStore, frontendColor, backendColor, theme, t]
    )

    return <BaseD3ChartView title={title} initChart={initChart} updateChart={updateChart}
                            margin={{top: 20, right: 10, bottom: 42, left: 40}}/>
}
