// src/components/framerate-viewer/d3ChartUtils.ts
import * as d3 from "d3"
import {Theme} from "@mui/material/styles"

export function createTooltip(theme: Theme) {
  return d3
    .select("body")
    .append("div")
    .style("position", "absolute")
    .style("background-color", theme.palette.mode === "dark" ? "rgba(0, 0, 0, 0.85)" : "rgba(255, 255, 255, 0.9)")
    .style("border", `1px solid ${theme.palette.divider}`)
    .style("border-radius", "4px")
    .style("padding", "8px")
    .style("font-family", "monospace")
    .style("font-size", "12px")
    .style("pointer-events", "none")
    .style("opacity", 0)
    .style("z-index", 1000)
    .style("color", theme.palette.text.primary)
}

export function applyAxisStyles(
  svg: d3.Selection<SVGGElement, unknown, null, undefined>,
  theme: Theme
) {
  svg.selectAll(".tick line")
    .attr("stroke", theme.palette.divider)
    .attr("stroke-dasharray", "2,2")

  svg.selectAll(".tick text")
    .style("font-family", "monospace")
    .style("font-size", "10px")
    .style("color", theme.palette.text.secondary)
}

export function renderEmptyChart(
  svg: d3.Selection<SVGGElement, unknown, null, undefined>,
  width: number,
  height: number,
  theme: Theme
) {
  // Create empty scales
  const xScale = d3.scaleLinear().domain([0, 100]).range([0, width])
  const yScale = d3.scaleLinear().domain([0, 10]).range([height, 0])

  // Create axes
  const xAxis = d3.axisBottom(xScale).ticks(10).tickSize(-height)
  const yAxis = d3.axisLeft(yScale).ticks(5).tickSize(-width)

  // Add X axis
  svg
    .append("g")
    .attr("class", "x-axis")
    .style("font-family", "monospace")
    .style("font-size", "10px")
    .style("color", theme.palette.text.secondary)
    .attr("transform", `translate(0,${height})`)
    .call(xAxis)

  // Add Y axis
  svg
    .append("g")
    .attr("class", "y-axis")
    .style("font-family", "monospace")
    .style("font-size", "10px")
    .style("color", theme.palette.text.secondary)
    .call(yAxis)

  // Style grid lines
  svg.selectAll(".tick line").attr("stroke", theme.palette.divider).attr("stroke-dasharray", "2,2")

  // Add "No data" message
  svg
    .append("text")
    .attr("x", width / 2)
    .attr("y", height / 2)
    .attr("text-anchor", "middle")
    .style("font-family", "monospace")
    .style("font-size", "14px")
    .style("fill", theme.palette.text.disabled)
    .text("No data available")
}

export function renderThresholdLines(
  chartArea: d3.Selection<SVGGElement, unknown, null, undefined>,
  thresholds: { value: number, label: string, color: string }[],
  xScale: any, // Allow both time and linear scales
  yScale: d3.ScaleLinear<number, number>,
  width: number,
  height: number,
  isHorizontal: boolean
) {
  thresholds.forEach((threshold) => {
    if (isHorizontal) {
      // Horizontal threshold line (for time series)
      chartArea
        .append("line")
        .attr("class", "threshold-line")
        .attr("x1", 0)
        .attr("y1", yScale(threshold.value))
        .attr("x2", width)
        .attr("y2", yScale(threshold.value))
        .attr("stroke", threshold.color)
        .attr("stroke-width", 1)
        .attr("stroke-dasharray", "4,4")

      // Add threshold label
      chartArea
        .append("text")
        .attr("class", "threshold-label")
        .attr("x", width)
        .attr("y", yScale(threshold.value) - 5)
        .attr("text-anchor", "end")
        .style("font-family", "monospace")
        .style("font-size", "10px")
        .style("fill", threshold.color)
        .text(threshold.label)
    } else {
      // Vertical threshold line (for histogram)
      chartArea
        .append("line")
        .attr("class", "threshold-line")
        .attr("x1", xScale(threshold.value))
        .attr("y1", 0)
        .attr("x2", xScale(threshold.value))
        .attr("y2", height)
        .attr("stroke", threshold.color)
        .attr("stroke-width", 1.5)
        .attr("stroke-dasharray", "4,4")

      // Add threshold label
      chartArea
        .append("text")
        .attr("class", "threshold-label")
        .attr("x", xScale(threshold.value))
        .attr("y", 15)
        .attr("text-anchor", "middle")
        .style("font-family", "monospace")
        .style("font-size", "10px")
        .style("fill", threshold.color)
        .text(threshold.label)
    }
  })
}

// Helper functions for zoom updates

// Update thresholds on zoom
export function updateThresholdsOnZoom(
  chartArea: d3.Selection<SVGGElement, unknown, null, undefined>,
  transform: d3.ZoomTransform,
  xScale: any,
  yScale: d3.ScaleLinear<number, number>,
  isHorizontal: boolean
) {
  if (isHorizontal) {
    // Update horizontal threshold lines
    chartArea.selectAll(".threshold-line")
      .attr("y1", (d: any) => transform.applyY(yScale(d.value)))
      .attr("y2", (d: any) => transform.applyY(yScale(d.value)));

    // Update labels
    chartArea.selectAll(".threshold-label")
      .attr("y", (d: any) => transform.applyY(yScale(d.value)) - 5);
  } else {
    // Update vertical threshold lines
    chartArea.selectAll(".threshold-line")
      .attr("x1", (d: any) => transform.applyX(xScale(d.value)))
      .attr("x2", (d: any) => transform.applyX(xScale(d.value)));

    // Update labels
    chartArea.selectAll(".threshold-label")
      .attr("x", (d: any) => transform.applyX(xScale(d.value)));
  }
}

// Update histogram bars on zoom
export function updateHistogramBarsOnZoom(
  chartArea: d3.Selection<SVGGElement, unknown, null, undefined>,
  selector: string,
  transform: d3.ZoomTransform,
  xScale: d3.ScaleLinear<number, number>,
  yScale: d3.ScaleLinear<number, number>,
  height: number
) {
  chartArea.selectAll(selector)
    .attr("x", (d: any) => transform.applyX(xScale(d.x0)))
    .attr("y", (d: any) => transform.applyY(yScale(d.density)))
    .attr("width", (d: any) => Math.max(0, transform.k * (xScale(d.x1) - xScale(d.x0)) - 1))
    .attr("height", (d: any) => height - transform.applyY(yScale(d.density)));
}

// Update time series lines on zoom
export function updateTimeSeriesOnZoom(
  chartArea: d3.Selection<SVGGElement, unknown, null, undefined>,
  transform: d3.ZoomTransform,
  xScale: d3.ScaleTime<number, number>,
  yScale: d3.ScaleLinear<number, number>
) {
  // Update line paths
chartArea.selectAll("path")
    .attr("d", (data) => 
      d3.line<any>()
        .x(d => transform.applyX(xScale(new Date(d.timestamp))))
        .y(d => transform.applyY(yScale(d.value)))
        .curve(d3.curveLinear)(data as any)
    );
  // Update data points
  chartArea.selectAll("circle")
    .attr("cx", (d: any) => transform.applyX(xScale(new Date(d.timestamp))))
    .attr("cy", (d: any) => transform.applyY(yScale(d.value)));
}
