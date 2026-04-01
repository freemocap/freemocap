// src/components/framerate-viewer/FramerateHistogramView.tsx
import {useCallback} from "react"
import * as d3 from "d3"
import {useTheme} from "@mui/material/styles"
import {applyAxisStyles, createTooltip, renderEmptyChart} from "./d3ChartUtils"
import {CurrentFramerate} from "@/store/slices/framerate/framerate-slice";
import BaseD3ChartView from "@/components/framerate-viewer/BaseD3ChartView";

type FramerateHistogramProps = {
    frontendFramerate: CurrentFramerate | null
    backendFramerate: CurrentFramerate | null
    recentFrontendFrameDurations: number[]
    recentBackendFrameDurations: number[]
    frontendColor: string
    backendColor: string
    title?: string
}

export default function FramerateHistogramView({
                                                   frontendFramerate,
                                                   backendFramerate,
                                                   recentFrontendFrameDurations,
                                                   recentBackendFrameDurations,
                                                   frontendColor,
                                                   backendColor,
                                                   title = "Frame Duration Distribution",
                                               }: FramerateHistogramProps) {
    const theme = useTheme()

    // Generate histogram data
    const generateHistogram = (data: number[], binCount = 100) => {
        if (data.length === 0) return null;

        // Calculate bins using d3's histogram generator
        const histGenerator = d3.histogram()
            .domain([0, d3.max(data) as number * 1.1]) // Add 10% padding to max
            .thresholds(binCount);

        const bins = histGenerator(data);

        // Calculate densities (normalized counts)
        const totalCount = data.length;
        const binCounts = bins.map(bin => bin.length);
        const binDensities = binCounts.map(count => count / totalCount);

        return {
            bin_edges: bins.map(bin => bin.x0 as number),
            bin_counts: binCounts,
            bin_densities: binDensities
        };
    };

    const renderChart = useCallback(({
                                         svg,
                                         chartArea,
                                         width,
                                         height,
                                         margin,
                                         transform
                                     }: {
        svg: d3.Selection<SVGGElement, unknown, null, undefined>;
        chartArea: d3.Selection<SVGGElement, unknown, null, undefined>;
        width: number;
        height: number;
        margin: { top: number; right: number; bottom: number; left: number };
        transform: d3.ZoomTransform;
    }) => {
        // Prepare the sources with histogram data
        const sources = [
            {
                id: 'frontend',
                name: frontendFramerate?.framerate_source || 'Frontend',
                color: frontendColor,
                histogram: generateHistogram(recentFrontendFrameDurations),
                totalSamples: recentFrontendFrameDurations.length
            },
            {
                id: 'backend',
                name: backendFramerate?.framerate_source || 'Backend',
                color: backendColor,
                histogram: generateHistogram(recentBackendFrameDurations),
                totalSamples: recentBackendFrameDurations.length
            }
        ];

        // Check if we have valid histogram data
        if (sources.every(s => !s.histogram)) {
            renderEmptyChart(svg, width, height, theme);
            return;
        }

        // Find domain bounds from all histograms
        let minX = Infinity;
        let maxX = -Infinity;
        let maxDensity = 0;

        sources.forEach(source => {
            if (source.histogram) {
                const edges = source.histogram.bin_edges;
                const densities = source.histogram.bin_densities;

                if (edges.length > 0) {
                    minX = Math.min(minX, edges[0]);
                    maxX = Math.max(maxX, edges[edges.length - 1]);
                }

                if (densities.length > 0) {
                    maxDensity = Math.max(maxDensity, Math.max(...densities));
                }
            }
        });

        // If we couldn't determine bounds, use defaults
        if (minX === Infinity) minX = 0;
        if (maxX === -Infinity) maxX = 100;
        if (maxDensity === 0) maxDensity = 1;

        // Add padding to domain
        const xPadding = (maxX - minX) * 0.1;
        const xDomain = [Math.max(0, minX - xPadding), maxX + xPadding];

        // Set up scales
        const xScale = d3.scaleLinear().domain(xDomain).range([0, width]);
        const yScale = d3.scaleLinear().domain([0, maxDensity * 1.1]).range([height, 0]);

        // Apply the current zoom transform
        const xScaleZoomed = d3.scaleLinear()
            .domain([Math.max(0, transform.rescaleX(xScale).domain()[0]), transform.rescaleX(xScale).domain()[1]])
            .range([0, width]);

        const yScaleZoomed = d3.scaleLinear()
            .domain([Math.max(0, transform.rescaleY(yScale).domain()[0]), transform.rescaleY(yScale).domain()[1]])
            .range([height, 0]);
        // Create axes
        const xAxis = d3.axisBottom(xScaleZoomed).ticks(10).tickSize(-height);
        const yAxis = d3.axisLeft(yScaleZoomed).ticks(5).tickSize(-width);

        // Add X axis with label
        const xAxisGroup = svg
            .append("g")
            .attr("class", "x-axis")
            .attr("transform", `translate(0,${height})`)
            .call(xAxis);

        svg
            .append("text")
            .attr("transform", `translate(${width / 2}, ${height + margin.bottom - 5})`)
            .style("text-anchor", "middle")
            .style("font-family", "monospace")
            .style("font-size", "10px")
            .style("fill", theme.palette.text.secondary)
            .text("Frame Duration (ms)");

        // Add Y axis with label
        const yAxisGroup = svg
            .append("g")
            .attr("class", "y-axis")
            .call(yAxis);

        svg
            .append("text")
            .attr("transform", "rotate(-90)")
            .attr("y", 0 - margin.left)
            .attr("x", 0 - height / 2)
            .attr("dy", "1em")
            .style("text-anchor", "middle")
            .style("font-family", "monospace")
            .style("font-size", "10px")
            .style("fill", theme.palette.text.secondary)
            .text("Density");

        // Style axes
        applyAxisStyles(svg, theme);

        // Add threshold lines
        // const thresholds = [
        //   { value: 16.67, label: "60 FPS", color: theme.palette.success.main },
        //   { value: 33.33, label: "30 FPS", color: theme.palette.warning.main },
        // ];
        //
        // renderThresholdLines(chartArea, thresholds, xScaleZoomed, yScaleZoomed, width, height, false);

        // Draw histograms
        sources.forEach(source => {
            if (!source.histogram || source.histogram.bin_edges.length === 0) return;

            const bins = source.histogram.bin_edges.map((edge, i) => ({
                x0: edge,
                x1: i < source.histogram!.bin_edges.length - 1 ? source.histogram!.bin_edges[i + 1] : edge + 0.1,
                density: i < source.histogram!.bin_densities.length ? source.histogram!.bin_densities[i] : 0,
                count: i < source.histogram!.bin_counts.length ? source.histogram!.bin_counts[i] : 0
            }));

            // Add histogram bars
            chartArea
                .selectAll(`.bar-${source.id}`)
                .data(bins)
                .enter()
                .append("rect")
                .attr("class", `bar-${source.id}`)
                .attr("x", d => xScaleZoomed(d.x0))
                .attr("width", d => Math.max(0, xScaleZoomed(d.x1) - xScaleZoomed(d.x0) - 1))
                .attr("y", d => {
                    const y = yScaleZoomed(d.density);
                    // Ensure y is valid and not greater than height
                    return isNaN(y) ? height : Math.min(height, Math.max(0, y));
                })
                .attr("height", d => {
                    const y = yScaleZoomed(d.density);
                    // Calculate height ensuring it's always positive
                    if (isNaN(y)) return 0;
                    const barHeight = height - Math.min(height, Math.max(0, y));
                    return Math.max(0, barHeight);
                })
                .attr("fill", source.color)
                .attr("stroke", theme.palette.background.paper)
                .attr("stroke-width", 0.5)
                .attr("opacity", 0.7);
        });

        // Add legend
        const legend = svg
            .append("g")
            .attr("transform", `translate(${width + 10}, 0)`)
            .attr("font-family", "monospace")
            .attr("font-size", "10px");

        sources.forEach((source, i) => {
            if (!source.histogram) return;

            const legendItem = legend.append("g").attr("transform", `translate(0, ${i * 20})`);
            legendItem.append("rect").attr("width", 12).attr("height", 12).attr("fill", source.color);
            legendItem.append("text")
                .attr("x", 20)
                .attr("y", 10)
                .style("fill", theme.palette.text.primary)
                .text(`${source.name} (${source.totalSamples})`);
        });

        // Add tooltip
        const tooltip = createTooltip(theme);

        // Add tooltip for histogram bars
        sources.forEach(source => {
            if (!source.histogram) return;

            chartArea
                .selectAll(`.bar-${source.id}`)
                .on("mouseover", function (event, d: any) {
                    d3.select(this).attr("opacity", 1).attr("stroke-width", 1);

                    tooltip
                        .style("opacity", 1)
                        .html(`
              <div style="display: grid; grid-template-columns: auto auto; gap: 4px;">
                <span style="color: ${theme.palette.text.secondary};">SOURCE:</span>
                <span style="color: ${source.color};">${source.name}</span>
                <span style="color: ${theme.palette.text.secondary};">RANGE:</span>
                <span>${d.x0.toFixed(2)} - ${d.x1.toFixed(2)} ms</span>
                <span style="color: ${theme.palette.text.secondary};">COUNT:</span>
                <span>${d.count} samples</span>
                <span style="color: ${theme.palette.text.secondary};">PERCENTAGE:</span>
                <span>${(d.density * 100).toFixed(1)}%</span>
                <span style="color: ${theme.palette.text.secondary};">FPS RANGE:</span>
                <span>${(1000 / d.x1).toFixed(1)} - ${(1000 / d.x0).toFixed(1)} fps</span>
              </div>
            `)
                        .style("left", event.pageX + 10 + "px")
                        .style("top", event.pageY - 28 + "px");
                })
                .on("mouseout", function () {
                    d3.select(this).attr("opacity", 0.7).attr("stroke-width", 0.5);
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
