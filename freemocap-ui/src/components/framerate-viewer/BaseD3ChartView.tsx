// src/components/framerate-viewer/BaseD3ChartView.tsx
import {useEffect, useRef, useState} from "react"
import * as d3 from "d3"
import {Box, Fade, IconButton, Tooltip, Typography} from "@mui/material"
import {RestartAlt, ZoomIn, ZoomOut} from "@mui/icons-material"

export type ChartMargins = {
    top: number
    right: number
    bottom: number
    left: number
}

// Define a type for elements that should be updated on zoom
export type ZoomableElement = {
    selector: string;
    updateFn: (selection: d3.Selection<any, any, any, any>, transform: d3.ZoomTransform) => void;
}

type BaseChartViewProps = {
    title?: string
    renderChart: (params: {
        svg: d3.Selection<SVGGElement, unknown, null, undefined>
        chartArea: d3.Selection<SVGGElement, unknown, null, undefined>
        width: number
        height: number
        margin: ChartMargins
        transform: d3.ZoomTransform
    }) => void
    margin?: ChartMargins
}

export default function BaseD3ChartView({
                                            title,
                                            renderChart,
                                            margin = {top: 20, right: 100, bottom: 30, left: 60}
                                        }: BaseChartViewProps) {
    const svgRef = useRef<SVGSVGElement>(null)
    const chartRef = useRef<{
        cleanup?: () => void
    }>({})
    const [transform, setTransform] = useState<d3.ZoomTransform>(d3.zoomIdentity)
    const zoomRef = useRef<d3.ZoomBehavior<SVGSVGElement, unknown> | null>(null)
    const [showControls, setShowControls] = useState(false)

    useEffect(() => {
        if (!svgRef.current) return

        // Clear previous chart
        d3.select(svgRef.current).selectAll("*").remove()

        // Set up dimensions
        let width = svgRef.current.clientWidth - margin.left - margin.right
        let height = svgRef.current.clientHeight - margin.top - margin.bottom
        if (width < 0) {
            width = 0
        }
        if (height < 0) {
            height = 0
        }
        // Create SVG with a clip path for zooming
        const svg = d3.select(svgRef.current)
            .append("g")
            .attr("transform", `translate(${margin.left},${margin.top})`)

        // Add clip path to prevent drawing outside the chart area
        svg
            .append("defs")
            .append("clipPath")
            .attr("id", "clip-chart")
            .append("rect")
            .attr("width", width)
            .attr("height", height)

        // Create a group for the chart content that will be clipped
        const chartArea = svg.append("g").attr("clip-path", "url(#clip-chart)")

        // Call the render function provided by the child component
        const cleanup = renderChart({svg, chartArea, width, height, margin, transform})

        // Store cleanup function if one is returned
        if (typeof cleanup === 'function') {
            chartRef.current.cleanup = cleanup
        }

        // Define zoom behavior
        const zoom = d3
            .zoom<SVGSVGElement, unknown>()
            .scaleExtent([0.5, 20])
            .extent([
                [0, 0],
                [width, height],
            ])
            .on("zoom", (event) => {
                // Update the transform state
                setTransform(event.transform)
            })

        // Store zoom reference for external controls
        zoomRef.current = zoom

        // Apply zoom to the SVG
        d3.select(svgRef.current).call(zoom)

        // Cleanup function
        return () => {
            if (chartRef.current.cleanup) {
                chartRef.current.cleanup()
            }
        }
    }, [renderChart, margin, transform])

    // Zoom control handlers
    const handleZoomIn = () => {
        if (svgRef.current && zoomRef.current) {
            d3.select(svgRef.current).transition().duration(300).call(zoomRef.current.scaleBy, 1.5)
        }
    }

    const handleZoomOut = () => {
        if (svgRef.current && zoomRef.current) {
            d3.select(svgRef.current).transition().duration(300).call(zoomRef.current.scaleBy, 0.75)
        }
    }

    const handleResetZoom = () => {
        if (svgRef.current && zoomRef.current) {
            d3.select(svgRef.current).transition().duration(300).call(zoomRef.current.transform, d3.zoomIdentity)
        }
    }

    return (
        <Box
            sx={{
                width: "100%",
                height: "100%",
                position: "relative",
                overflow: "hidden"
            }}
            onMouseEnter={() => setShowControls(true)}
            onMouseLeave={() => setShowControls(false)}
        >
            {title && (
                <Typography
                    variant="caption"
                    sx={{
                        position: "absolute",
                        top: 5,
                        left: 10,
                        fontSize: '0.7rem',
                        opacity: 0.8
                    }}
                >
                    {title}
                </Typography>
            )}

            {/* Zoom controls that fade in/out on hover */}
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
                    <Tooltip title="Zoom In" placement="right">
                        <IconButton size="small" onClick={handleZoomIn} sx={{p: 0.5}}>
                            <ZoomIn fontSize="small"/>
                        </IconButton>
                    </Tooltip>
                    <Tooltip title="Zoom Out" placement="right">
                        <IconButton size="small" onClick={handleZoomOut} sx={{p: 0.5}}>
                            <ZoomOut fontSize="small"/>
                        </IconButton>
                    </Tooltip>
                    <Tooltip title="Reset Zoom" placement="right">
                        <IconButton size="small" onClick={handleResetZoom} sx={{p: 0.5}}>
                            <RestartAlt fontSize="small"/>
                        </IconButton>
                    </Tooltip>
                </Box>
            </Fade>

            <svg
                ref={svgRef}
                width="100%"
                height="100%"
                style={{
                    display: 'block',
                    overflow: "visible"
                }}
            />
        </Box>
    )
}
