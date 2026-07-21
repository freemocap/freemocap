// src/components/framerate-viewer/d3ChartUtils.ts
import * as d3 from "d3"

export type ChartTheme = {
    dividerColor: string
    textSecondaryColor: string
    textDisabledColor: string
    backgroundPaperColor: string
}

export const darkChartTheme: ChartTheme = {
    dividerColor: "rgba(255,255,255,0.12)",
    textSecondaryColor: "rgba(255,255,255,0.6)",
    textDisabledColor: "rgba(255,255,255,0.3)",
    backgroundPaperColor: "#1e1e2e",
}

export function applyAxisStyles(
    svg: d3.Selection<SVGGElement, unknown, null, undefined>,
    theme: ChartTheme = darkChartTheme
): void {
    svg.selectAll(".tick line")
        .attr("stroke", theme.dividerColor)
        .attr("stroke-dasharray", "2,2")

    svg.selectAll(".tick text")
        .style("font-family", "monospace")
        .style("font-size", "10px")
        .style("color", theme.textSecondaryColor)
}

export function renderEmptyChart(
    svg: d3.Selection<SVGGElement, unknown, null, undefined>,
    width: number,
    height: number,
    theme: ChartTheme = darkChartTheme,
    text: string = "Waiting for data…"
): void {
    svg
        .append("text")
        .attr("x", width / 2)
        .attr("y", height / 2)
        .attr("text-anchor", "middle")
        .attr("dominant-baseline", "central")
        .style("font-family", "monospace")
        .style("font-size", "12px")
        .style("fill", theme.textDisabledColor)
        .text(text)
}

export function renderThresholdLines(
    chartArea: d3.Selection<SVGGElement, unknown, null, undefined>,
    thresholds: {value: number; label: string; color: string}[],
    xScale: any,
    yScale: d3.ScaleLinear<number, number>,
    width: number,
    height: number,
    isHorizontal: boolean
): void {
    thresholds.forEach((threshold) => {
        if (isHorizontal) {
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
