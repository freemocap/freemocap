// src/components/framerate-viewer/FramerateHistogramView.tsx
import {useCallback, useRef} from "react"
import * as d3 from "d3"
import {applyAxisStyles, darkChartTheme} from "./d3ChartUtils"
import BaseD3ChartView, {ChartLifecycle, ChartScaffolding} from "@/components/framerate-viewer/BaseD3ChartView"
import {useTranslation} from "react-i18next"
import {useServer} from "@/services/server/ServerContextProvider"
import {TimestampedSample} from "@/services/server/server-helpers/framerate-store"

type FramerateHistogramProps = {
    frontendColor: string
    backendColor: string
    title?: string
}

type HistogramBin = {x0: number; x1: number; count: number; density: number}

function buildHistogram(fpsValues: number[]): {
    bins: HistogramBin[]
    maxDensity: number
} | null {
    if (fpsValues.length === 0) return null

    const min = Math.floor(d3.min(fpsValues)!)
    const max = Math.ceil(d3.max(fpsValues)!)

    const range = max - min
    const binWidth = range > 40 ? Math.ceil(range / 30) : 1
    const thresholds: number[] = []
    for (let v = min; v <= max; v += binWidth) {
        thresholds.push(v)
    }

    const generator = d3
        .bin<number, number>()
        .domain([min, max + binWidth])
        .thresholds(thresholds)

    const rawBins = generator(fpsValues)
    const total = fpsValues.length
    let maxDensity = 0

    const bins = rawBins.map((b) => {
        const density = b.length / total
        if (density > maxDensity) maxDensity = density
        return {
            x0: b.x0 as number,
            x1: b.x1 as number,
            count: b.length,
            density,
        }
    })

    return {bins, maxDensity}
}

function toFpsInPlace(samples: TimestampedSample[], out: number[]): void {
    out.length = 0
    for (let i = 0; i < samples.length; i++) {
        const v = samples[i].value
        if (v > 0) out.push(1000 / v)
    }
}

type ChartState = {
    frontendBarGroup: d3.Selection<SVGGElement, unknown, null, undefined>
    backendBarGroup: d3.Selection<SVGGElement, unknown, null, undefined>
    xScale: d3.ScaleLinear<number, number>
    yScale: d3.ScaleLinear<number, number>
    height: number
    frontendFpsBuf: number[]
    backendFpsBuf: number[]
}

export default function FramerateHistogramView({
    frontendColor,
    backendColor,
    title = "Framerate Distribution",
}: FramerateHistogramProps) {
    const {t} = useTranslation()
    const stateRef = useRef<ChartState | null>(null)
    const {getFramerateStore} = useServer()

    const initChart = useCallback(
        ({svg, chartArea, width, height}: ChartScaffolding): ChartLifecycle => {
            const xScale = d3.scaleLinear().range([0, width])
            const yScale = d3.scaleLinear().range([height, 0])

            const frontendBarGroup = chartArea.append("g").attr("class", "bars-frontend")
            const backendBarGroup = chartArea.append("g").attr("class", "bars-backend")

            svg.append("text")
                .attr("class", "x-axis-label")
                .attr("x", width / 2)
                .attr("y", height + 32)
                .attr("text-anchor", "middle")
                .style("font-family", "monospace")
                .style("font-size", "10px")
                .style("fill", darkChartTheme.textSecondaryColor)
                .text("FPS")

            svg.append("text")
                .attr("class", "y-axis-label")
                .attr("transform", "rotate(-90)")
                .attr("x", -height / 2)
                .attr("y", -28)
                .attr("text-anchor", "middle")
                .style("font-family", "monospace")
                .style("font-size", "10px")
                .style("fill", darkChartTheme.textSecondaryColor)
                .text("Density")

            chartArea.append("text")
                .attr("class", "empty-text")
                .attr("x", width / 2)
                .attr("y", height / 2)
                .attr("text-anchor", "middle")
                .attr("dominant-baseline", "central")
                .style("font-family", "monospace")
                .style("font-size", "12px")
                .style("fill", darkChartTheme.textDisabledColor)
                .style("display", "none")

            stateRef.current = {
                frontendBarGroup,
                backendBarGroup,
                xScale,
                yScale,
                height,
                frontendFpsBuf: [],
                backendFpsBuf: [],
            }

            return {
                cleanup: () => {
                    stateRef.current = null
                },
            }
        },
        [frontendColor, backendColor]
    )

    const updateChart = useCallback(
        ({svg, chartArea, xAxisG, yAxisG, width, height}: ChartScaffolding) => {
            const state = stateRef.current
            if (!state) return

            const snapshot = getFramerateStore().getSnapshot()
            const recentFrontendDurations = snapshot.recentFrontendDurations
            const recentBackendDurations = snapshot.recentBackendDurations

            toFpsInPlace(recentFrontendDurations, state.frontendFpsBuf)
            toFpsInPlace(recentBackendDurations, state.backendFpsBuf)
            const frontendFps = state.frontendFpsBuf
            const backendFps = state.backendFpsBuf

            const frontendHist = buildHistogram(frontendFps)
            const backendHist = buildHistogram(backendFps)

            state.height = height

            const emptyText = chartArea.select<SVGTextElement>(".empty-text")

            if (!frontendHist && !backendHist) {
                state.frontendBarGroup.selectAll("rect").remove()
                state.backendBarGroup.selectAll("rect").remove()
                emptyText.style("display", null).text(t("waitingForData"))
                return
            }

            emptyText.style("display", "none")

            let minX = Infinity
            let maxX = -Infinity
            let maxDensity = 0

            for (const hist of [frontendHist, backendHist]) {
                if (!hist) continue
                const bins = hist.bins
                if (bins.length > 0) {
                    minX = Math.min(minX, bins[0].x0)
                    maxX = Math.max(maxX, bins[bins.length - 1].x1)
                }
                maxDensity = Math.max(maxDensity, hist.maxDensity)
            }

            if (minX === Infinity) minX = 0
            if (maxX === -Infinity) maxX = 60
            if (maxDensity === 0) maxDensity = 1

            const xPad = Math.max(1, (maxX - minX) * 0.05)

            state.xScale.domain([minX - xPad, maxX + xPad])
            state.yScale.domain([0, maxDensity * 1.15])

            const xAxisGen = d3
                .axisBottom(state.xScale)
                .ticks(Math.max(2, Math.min(8, Math.floor(width / 50))))
                .tickSize(-height)
            const yAxisGen = d3
                .axisLeft(state.yScale)
                .ticks(Math.max(2, Math.min(5, Math.floor(height / 30))))
                .tickSize(-width)

            xAxisG.call(xAxisGen)
            yAxisG.call(yAxisGen)
            applyAxisStyles(svg, darkChartTheme)

            const numSources = [frontendHist, backendHist].filter(Boolean).length
            const barInset = numSources > 1 ? 1 : 0

            const updateBars = (
                group: d3.Selection<SVGGElement, unknown, null, undefined>,
                bins: HistogramBin[],
                color: string,
                srcIdx: number,
            ) => {
                const bars = group.selectAll<SVGRectElement, HistogramBin>("rect")
                    .data(bins, (d) => `${d.x0}-${d.x1}`)

                bars.exit().remove()

                const entered = bars.enter()
                    .append("rect")
                    .attr("fill", color)
                    .attr("stroke", darkChartTheme.backgroundPaperColor)
                    .attr("stroke-width", 0.5)
                    .attr("opacity", 0.7)

                entered.merge(bars)
                    .attr("x", (d) => state.xScale(d.x0) + srcIdx * barInset)
                    .attr("width", (d) => {
                        const w = state.xScale(d.x1) - state.xScale(d.x0) - barInset
                        return Math.max(1, w)
                    })
                    .attr("y", (d) => {
                        const y = state.yScale(d.density)
                        return isNaN(y) ? height : Math.min(height, Math.max(0, y))
                    })
                    .attr("height", (d) => {
                        const y = state.yScale(d.density)
                        if (isNaN(y)) return 0
                        return Math.max(0, height - Math.min(height, Math.max(0, y)))
                    })
            }

            updateBars(state.frontendBarGroup, frontendHist?.bins ?? [], frontendColor, 0)
            updateBars(state.backendBarGroup, backendHist?.bins ?? [], backendColor, numSources > 1 ? 1 : 0)
        },
        [getFramerateStore, frontendColor, backendColor, t]
    )

    return <BaseD3ChartView title={title} initChart={initChart} updateChart={updateChart}
                            margin={{top: 20, right: 10, bottom: 42, left: 40}} />
}
