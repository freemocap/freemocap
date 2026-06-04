// src/components/framerate-viewer/BaseD3ChartView.tsx
import {memo, useCallback, useEffect, useRef, useState} from "react"
import * as d3 from "d3"
import {useTranslation} from "react-i18next"

export type ChartMargins = {
    top: number
    right: number
    bottom: number
    left: number
}

/** Persistent D3 scaffolding created once on mount/resize. */
export type ChartScaffolding = {
    svg: d3.Selection<SVGGElement, unknown, null, undefined>
    chartArea: d3.Selection<SVGGElement, unknown, null, undefined>
    xAxisG: d3.Selection<SVGGElement, unknown, null, undefined>
    yAxisG: d3.Selection<SVGGElement, unknown, null, undefined>
    width: number
    height: number
    margin: ChartMargins
}

/** Returned by initChart, stored by BaseD3ChartView for the lifetime of the scaffolding. */
export type ChartLifecycle = {
    onZoom?: (transform: d3.ZoomTransform) => void
    cleanup?: () => void
}

type BaseChartViewProps = {
    title?: string
    /** Called once when the chart mounts or resizes. Creates persistent DOM elements (tooltip, etc). */
    initChart: (scaffolding: ChartScaffolding) => ChartLifecycle | void
    /** Called on every data update. Performs in-place D3 updates on the existing scaffolding. */
    updateChart: (scaffolding: ChartScaffolding) => void
    margin?: ChartMargins
}

let nextClipId = 0

/** How often (ms) to run the imperative D3 data-update. */
const CHART_UPDATE_INTERVAL_MS = 1000

export default memo(function BaseD3ChartView({
    title,
    initChart,
    updateChart,
    margin = {top: 20, right: 20, bottom: 30, left: 50},
}: BaseChartViewProps) {
    const {t} = useTranslation()
    const svgRef = useRef<SVGSVGElement>(null)
    const containerRef = useRef<HTMLDivElement>(null)
    const chartStateRef = useRef<{
        cleanup?: () => void
        onZoom?: (transform: d3.ZoomTransform) => void
        scaffolding?: ChartScaffolding
    }>({})
    const zoomRef = useRef<d3.ZoomBehavior<SVGSVGElement, unknown> | null>(null)
    const clipIdRef = useRef<string>(`clip-chart-${nextClipId++}`)
    const [showControls, setShowControls] = useState(false)
    const [containerSize, setContainerSize] = useState<{width: number; height: number}>({width: 0, height: 0})

    const updateChartRef = useRef(updateChart)
    updateChartRef.current = updateChart

    useEffect(() => {
        const container = containerRef.current
        if (!container) return

        const observer = new ResizeObserver((entries) => {
            for (const entry of entries) {
                const {width, height} = entry.contentRect
                setContainerSize(prev => {
                    const w = Math.round(width)
                    const h = Math.round(height)
                    if (prev.width === w && prev.height === h) return prev
                    return {width: w, height: h}
                })
            }
        })
        observer.observe(container)
        return () => observer.disconnect()
    }, [])

    useEffect(() => {
        if (!svgRef.current || containerSize.width === 0 || containerSize.height === 0) return

        d3.select(svgRef.current).selectAll("*").remove()
        if (chartStateRef.current.cleanup) {
            chartStateRef.current.cleanup()
        }
        chartStateRef.current = {}

        const width = Math.max(0, containerSize.width - margin.left - margin.right)
        const height = Math.max(0, containerSize.height - margin.top - margin.bottom)
        if (width <= 0 || height <= 0) return

        const clipId = clipIdRef.current

        const svg = d3.select(svgRef.current)
            .append("g")
            .attr("transform", `translate(${margin.left},${margin.top})`)

        svg.append("defs")
            .append("clipPath")
            .attr("id", clipId)
            .append("rect")
            .attr("width", width)
            .attr("height", height)

        const chartArea = svg.append("g").attr("clip-path", `url(#${clipId})`)

        const xAxisG = svg
            .append("g")
            .attr("class", "x-axis")
            .attr("transform", `translate(0,${height})`)
        const yAxisG = svg.append("g").attr("class", "y-axis")

        const scaffolding: ChartScaffolding = {svg, chartArea, xAxisG, yAxisG, width, height, margin}
        chartStateRef.current.scaffolding = scaffolding

        const result = initChart(scaffolding)
        if (result) {
            chartStateRef.current.cleanup = result.cleanup
            chartStateRef.current.onZoom = result.onZoom
        }

        const zoom = d3
            .zoom<SVGSVGElement, unknown>()
            .scaleExtent([0.5, 20])
            .extent([[0, 0], [width, height]])
            .on("zoom", (event) => {
                chartStateRef.current.onZoom?.(event.transform)
            })

        zoomRef.current = zoom
        d3.select(svgRef.current).call(zoom)

        return () => {
            if (chartStateRef.current.cleanup) {
                chartStateRef.current.cleanup()
                chartStateRef.current = {}
            }
        }
    }, [initChart, margin, containerSize])

    useEffect(() => {
        const tick = () => {
            const scaffolding = chartStateRef.current.scaffolding
            if (scaffolding) updateChartRef.current(scaffolding)
        }
        tick()
        const id = setInterval(tick, CHART_UPDATE_INTERVAL_MS)
        return () => clearInterval(id)
    }, [])

    const handleZoomIn = useCallback(() => {
        if (svgRef.current && zoomRef.current) {
            d3.select(svgRef.current).transition().duration(300).call(zoomRef.current.scaleBy, 1.5)
        }
    }, [])

    const handleZoomOut = useCallback(() => {
        if (svgRef.current && zoomRef.current) {
            d3.select(svgRef.current).transition().duration(300).call(zoomRef.current.scaleBy, 0.75)
        }
    }, [])

    const handleResetZoom = useCallback(() => {
        if (svgRef.current && zoomRef.current) {
            d3.select(svgRef.current).transition().duration(300).call(zoomRef.current.transform, d3.zoomIdentity)
        }
    }, [])

    return (
        <div
            ref={containerRef}
            className="pos-rel overflow-hidden"
            style={{width: "100%", height: "100%"}}
            onMouseEnter={() => setShowControls(true)}
            onMouseLeave={() => setShowControls(false)}
        >
            {title && (
                <p className="text sm text-gray" style={{
                    position: "absolute",
                    top: 2,
                    left: 8,
                    fontSize: "0.7rem",
                    opacity: 0.9,
                    zIndex: 5,
                    backgroundColor: "var(--color-bg-default)",
                    padding: "0 4px",
                    borderRadius: 2,
                    lineHeight: 1.4,
                    margin: 0,
                }}>
                    {title}
                </p>
            )}

            {showControls && (
                <div className="flex flex-col bg-middark br-1" style={{
                    position: "absolute",
                    top: "50%",
                    right: 5,
                    transform: "translateY(-50%)",
                    zIndex: 10,
                    boxShadow: "0 1px 4px rgba(0,0,0,0.4)",
                }}>
                    <button title={t("zoomIn")} className="button icon-button br-1" onClick={handleZoomIn}>
                        <span className="icon plus-icon icon-size-20"/>
                    </button>
                    <button title={t("zoomOut")} className="button icon-button br-1" onClick={handleZoomOut}>
                        <span className="icon minus-icon icon-size-20"/>
                    </button>
                    <button title={t("resetZoom")} className="button icon-button br-1" onClick={handleResetZoom}>
                        <span className="icon back-icon icon-size-20"/>
                    </button>
                </div>
            )}

            <svg
                ref={svgRef}
                width={containerSize.width}
                height={containerSize.height}
                style={{display: "block", overflow: "hidden"}}
            />
        </div>
    )
}, (prev, next) => {
    return prev.title === next.title
        && prev.initChart === next.initChart
        && prev.margin === next.margin
})
