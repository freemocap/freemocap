// src/components/framerate-viewer/FramerateTimeseriesView.tsx
import {useCallback} from "react"
import * as d3 from "d3"
import {useTheme} from "@mui/material/styles"
import {CurrentFramerate} from "@/store/slices/framerate/framerate-slice"
import {applyAxisStyles, createTooltip, renderEmptyChart} from "@/components/framerate-viewer/d3ChartUtils";
import BaseD3ChartView from "@/components/framerate-viewer/BaseD3ChartView";

type FramerateTimeseriesProps = {
    frontendFramerate: CurrentFramerate | null
    backendFramerate: CurrentFramerate | null
    recentFrontendFrameDurations: number[]
    recentBackendFrameDurations: number[]
    frontendColor: string
    backendColor: string
    title?: string
}
type ChartRenderProps = {
    svg: d3.Selection<SVGGElement, unknown, null, undefined>;
    chartArea: d3.Selection<SVGGElement, unknown, null, undefined>;
    width: number;
    height: number;
    margin: { top: number; right: number; bottom: number; left: number };
    transform: d3.ZoomTransform;
};

export default function FramerateTimeseriesView({
                                                    frontendFramerate,
                                                    backendFramerate,
                                                    recentFrontendFrameDurations,
                                                    recentBackendFrameDurations,
                                                    frontendColor,
                                                    backendColor,
                                                    title = "Frame Duration Over Time"
                                                }: FramerateTimeseriesProps) {
    const theme = useTheme()

    const renderChart = useCallback(({svg, chartArea, width, height, margin, transform}: ChartRenderProps) => {
        // Prepare data sources - using the recent frame durations arrays
        const sources = [
            {
                id: "frontend",
                name: frontendFramerate?.framerate_source || "Frontend",
                color: frontendColor,
                data: recentFrontendFrameDurations.map((value, index) => ({
                    timestamp: Date.now() - (recentFrontendFrameDurations.length - index) *
                        (frontendFramerate?.mean_frame_duration_ms || 16.67),
                    value
                }))
            },
            {
                id: "backend",
                name: backendFramerate?.framerate_source || "Backend",
                color: backendColor,
                data: recentBackendFrameDurations.map((value, index) => ({
                    timestamp: Date.now() - (recentBackendFrameDurations.length - index) *
                        (backendFramerate?.mean_frame_duration_ms || 33.33),
                    value
                }))
            }
        ];

        if (sources.every((s) => s.data.length === 0)) {
            renderEmptyChart(svg, width, height, theme);
            return;
        }

        // Combine all data points to determine overall domain
        const allData = sources.flatMap((s) => s.data);

        // Set up scales
        const xScale = d3
            .scaleTime()
            .domain(d3.extent(allData, (d) => new Date(d.timestamp)) as [Date, Date])
            .range([0, width]);

        // Calculate y domain with some padding
        const yMax = d3.max(allData, (d) => d.value) as number;
        const yPadding = Math.max(1, yMax * 0.1);

        const yScale = d3
            .scaleLinear()
            .domain([0, yMax + yPadding])
            .range([height, 0]);

        // Apply the current zoom transform
        const xScaleZoomed = transform.rescaleX(xScale);
        const yScaleZoomed = transform.rescaleY(yScale);

        // Create axes
        const xAxis = d3
            .axisBottom(xScaleZoomed)
            .ticks(5)
            .tickSize(-height)
            .tickFormat(d3.timeFormat("%H:%M:%S") as any);

        const yAxis = d3.axisLeft(yScaleZoomed).ticks(10).tickSize(-width);

        // Add X axis
        const xAxisGroup = svg
            .append("g")
            .attr("class", "x-axis")
            .attr("transform", `translate(0,${height})`)
            .call(xAxis);

        xAxisGroup
            .selectAll("text")
            .style("text-anchor", "end")
            .attr("dx", "-.8em")
            .attr("dy", ".15em")
            .attr("transform", "rotate(-45)");

        // Add Y axis
        const yAxisGroup = svg
            .append("g")
            .attr("class", "y-axis")
            .call(yAxis);

        // Add Y axis label
        svg
            .append("text")
            .attr("transform", "rotate(-90)")
            .attr("y", 0 - margin.left)
            .attr("x", 0 - height / 2)
            .attr("dy", "1em")
            .style("text-anchor", "middle")
            .style("font-family", "monospace")
            .style("font-size", "14px")
            .style("fill", theme.palette.text.secondary)
            .text("Frame Duration (ms)");

        // Style axes
        applyAxisStyles(svg, theme);

        // Add threshold lines
        // const thresholds = [
        //   { value: 16.67, label: "60 FPS", color: theme.palette.success.main },
        //   { value: 33.33, label: "30 FPS", color: theme.palette.warning.main },
        // ];
        //
        // renderThresholdLines(chartArea, thresholds, xScaleZoomed, yScaleZoomed, width, height, true);

        // Create line generator
        const line = d3
            .line<{ timestamp: number, value: number }>()
            .x((d) => xScaleZoomed(new Date(d.timestamp)))
            .y((d) => yScaleZoomed(d.value))
            .curve(d3.curveLinear);

        // Add lines and points for each source
        sources.forEach((source) => {
            if (source.data.length === 0) return;

            // Add the line path
            chartArea
                .append("path")
                .datum(source.data)
                .attr("fill", "none")
                .attr("stroke", source.color)
                .attr("stroke-width", 1.5)
                .attr("d", line);

        });

        // Add legend
        const legend = svg
            .append("g")
            .attr("transform", `translate(${width + 10}, 0)`)
            .attr("font-family", "monospace")
            .attr("font-size", "10px");

        sources.forEach((source, i) => {
            if (source.data.length === 0) return;

            const legendItem = legend.append("g").attr("transform", `translate(0, ${i * 20})`);
            legendItem.append("rect").attr("width", 12).attr("height", 12).attr("fill", source.color);
            legendItem.append("text")
                .attr("x", 20)
                .attr("y", 10)
                .style("fill", theme.palette.text.primary)
                .text(source.name);
        });

        // Add tooltip
        const tooltip = createTooltip(theme);

        // Add tooltip for data points
        sources.forEach((source) => {
            if (source.data.length === 0) return;

            chartArea
                .selectAll(`.data-point-${source.id}`)
                .on("mouseover", function (event: MouseEvent, d: any) {
                    const element = this as unknown as SVGCircleElement;
                    d3.select(element).attr("r", 5).attr("fill", d3.color(source.color)!.brighter(0.5).toString());

                    tooltip
                        .style("opacity", 1)
                        .html(`
              <div style="display: grid; grid-template-columns: auto auto; gap: 4px;">
                <span style="color: ${theme.palette.text.secondary};">SOURCE:</span>
                <span style="color: ${source.color};">${source.name}</span>
                <span style="color: ${theme.palette.text.secondary};">TIME:</span>
                <span>${new Date(d.timestamp).toISOString().substr(11, 12)}</span>
                <span style="color: ${theme.palette.text.secondary};">DURATION:</span>
                <span>${d.value.toFixed(2)} ms</span>
                <span style="color: ${theme.palette.text.secondary};">FPS:</span>
                <span>${(1000 / d.value).toFixed(2)}</span>
              </div>
            `)
                        .style("left", event.pageX + 10 + "px")
                        .style("top", event.pageY - 28 + "px");
                })
                .on("mouseout", function (event: MouseEvent, d: any) {
                    d3.select(this).attr("r", 3).attr("fill", source.color);
                    tooltip.style("opacity", 0);
                });
        });

        return () => tooltip.remove();
    }, [
        frontendFramerate,
        backendFramerate,
        recentFrontendFrameDurations,
        recentBackendFrameDurations,
        frontendColor,
        backendColor,
        theme
    ]);

    return (
        <BaseD3ChartView
            title={title}
            renderChart={renderChart}
        />
    );
}
