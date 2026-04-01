// src/components/framerate-viewer/BaseD3ChartView.tsx
import {useEffect, useRef, useState, useCallback, memo} from "react"
import * as d3 from "d3"
import {Box, Fade, IconButton, Tooltip, Typography} from "@mui/material"
import {RestartAlt, ZoomIn, ZoomOut} from "@mui/icons-material"
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
const CHART_UPDATE_INTERVAL_MS = 500

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

    // Always holds the latest updateChart without triggering re-renders.
    const updateChartRef = useRef(updateChart)
    updateChartRef.current = updateChart

    // Track container size with ResizeObserver
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

    // Build chart scaffolding on mount/resize — runs rarely
    useEffect(() => {
        if (!svgRef.current || containerSize.width === 0 || containerSize.height === 0) return

        // Tear down previous scaffolding
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

        // Set up zoom behavior
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

    // Imperative D3 data update on a fixed interval. The updateChart callback
    // (stored in the ref) reads directly from the FramerateStore each tick,
    // so no React state or re-renders are involved in the data path.
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
        <Box
            ref={containerRef}
            sx={{
                width: "100%",
                height: "100%",
                position: "relative",
                overflow: "hidden",
            }}
            onMouseEnter={() => setShowControls(true)}
            onMouseLeave={() => setShowControls(false)}
        >
            {title && (
                <Typography
                    variant="caption"
                    sx={{
                        position: "absolute",
                        top: 2,
                        left: 8,
                        fontSize: "0.7rem",
                        opacity: 0.9,
                        zIndex: 5,
                        bgcolor: "background.default",
                        px: 0.5,
                        borderRadius: 0.5,
                        lineHeight: 1.4,
                    }}
                >
                    {title}
                </Typography>
            )}

            <Fade in={showControls}>
                <Box
                    sx={{
                        position: "absolute",
                        top: "50%",
                        right: 5,
                        transform: "translateY(-50%)",
                        zIndex: 10,
                        bgcolor: "background.paper",
                        borderRadius: 1,
                        boxShadow: 1,
                        display: "flex",
                        flexDirection: "column",
                    }}
                >
                    <Tooltip title={t("zoomIn")} placement="right">
                        <IconButton size="small" onClick={handleZoomIn} sx={{p: 0.5}}>
                            <ZoomIn fontSize="small" />
                        </IconButton>
                    </Tooltip>
                    <Tooltip title={t("zoomOut")} placement="right">
                        <IconButton size="small" onClick={handleZoomOut} sx={{p: 0.5}}>
                            <ZoomOut fontSize="small" />
                        </IconButton>
                    </Tooltip>
                    <Tooltip title={t("resetZoom")} placement="right">
                        <IconButton size="small" onClick={handleResetZoom} sx={{p: 0.5}}>
                            <RestartAlt fontSize="small" />
                        </IconButton>
                    </Tooltip>
                </Box>
            </Fade>

            <svg
                ref={svgRef}
                width={containerSize.width}
                height={containerSize.height}
                style={{display: "block", overflow: "hidden"}}
            />
        </Box>
    )
}, (prev, next) => {
    return prev.title === next.title
        && prev.initChart === next.initChart
        && prev.margin === next.margin
})
