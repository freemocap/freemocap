// src/components/framerate-viewer/FrameRateViewer.tsx
import {useState} from "react"
import {Box, IconButton, Paper, Stack, Tooltip, Typography} from "@mui/material"
import {BarChart, ShowChart, ViewCompact, ViewDay} from "@mui/icons-material"
import {alpha, useTheme} from "@mui/material/styles"
import FramerateTimeseriesView from "./FramerateTimeseriesView"
import FramerateHistogramView from "./FramerateHistogramView"
import FramerateStatisticsView from "./FramerateStatisticsView"
import {useAppSelector, selectFramerateViewerData} from "@/store";

type ViewType = "timeseries" | "histogram" | "both"
export const frontendColor: string = "#1976D2"
export const backendColor: string = "#ff4d00"

export const FramerateViewerPanel = () => {
    const theme = useTheme()
    const [viewType, setViewType] = useState<ViewType>("both")

    // Use the new selector to get all framerate data
    const {
        currentFrontendFramerate,
        currentBackendFramerate,
        recentFrontendFrameDurations,
        recentBackendFrameDurations
    } = useAppSelector(selectFramerateViewerData);

    return (
        <Box sx={{
            height: '100%',
            display: 'flex',
            flexDirection: 'column',
            backgroundColor: theme.palette.background.default,
            p: 0.5,
            overflow: 'hidden'  // Prevent content overflow
        }}>
            {/* Ultra-compact header with controls */}
            <Box sx={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                mb: 0.25,
                px: 0.5
            }}>
                <Typography variant="body2" fontWeight="medium" noWrap sx={{fontSize: '0.75rem'}}>
                    Camera Performance Metrics
                </Typography>

                {/* View type selector as icon buttons */}
                <Stack direction="row" spacing={0.25}>
                    <Tooltip title="Timeline View">
                        <IconButton
                            size="small"
                            onClick={() => setViewType("timeseries")}
                            color={viewType === "timeseries" ? "primary" : "default"}
                            sx={{padding: '2px'}}
                        >
                            <ShowChart sx={{fontSize: '1rem'}}/>
                        </IconButton>
                    </Tooltip>
                    <Tooltip title="Distribution View">
                        <IconButton
                            size="small"
                            onClick={() => setViewType("histogram")}
                            color={viewType === "histogram" ? "primary" : "default"}
                            sx={{padding: '2px'}}
                        >
                            <BarChart sx={{fontSize: '1rem'}}/>
                        </IconButton>
                    </Tooltip>
                    <Tooltip title="Combined View">
                        <IconButton
                            size="small"
                            onClick={() => setViewType("both")}
                            color={viewType === "both" ? "primary" : "default"}
                            sx={{padding: '2px'}}
                        >
                            {theme.direction === 'ltr' ? (
                                <ViewDay sx={{fontSize: '1rem'}}/>
                            ) : (
                                <ViewCompact sx={{fontSize: '1rem'}}/>
                            )}
                        </IconButton>
                    </Tooltip>
                </Stack>
            </Box>

            {/* Stats section - ultra compact */}
            <Box sx={{
                px: 0.25,
                mb: 0.25,
            }}>
                <Paper
                    elevation={0}
                    sx={{
                        p: 0.25,
                        bgcolor: alpha(theme.palette.background.paper, theme.palette.mode === 'dark' ? 0.15 : 0.05),
                        border: `1px solid ${alpha(theme.palette.divider, 0.1)}`
                    }}
                >
                    <FramerateStatisticsView
                        frontendFramerate={currentFrontendFramerate}
                        backendFramerate={currentBackendFramerate}
                        compact={true}
                    />
                </Paper>
            </Box>

            {/* Main visualization area with flex-based layout */}
            <Box sx={{
                flex: 1,
                display: 'flex',
                flexDirection: viewType === 'both' ? 'row' : 'column',
                gap: 0.25,
                overflow: 'hidden'  // Critical to prevent overflow
            }}>
                {(viewType === 'timeseries' || viewType === 'both') && (
                    <Paper
                        elevation={0}
                        sx={{
                            flex: 1,
                            display: 'flex',
                            flexDirection: 'column',
                            border: '1px solid',
                            borderColor: alpha(theme.palette.divider, 0.2),
                            overflow: 'hidden'  // Ensure chart doesn't overflow
                        }}
                    >
                        <FramerateTimeseriesView
                            frontendFramerate={currentFrontendFramerate}
                            backendFramerate={currentBackendFramerate}
                            recentFrontendFrameDurations={recentFrontendFrameDurations}
                            recentBackendFrameDurations={recentBackendFrameDurations}
                            frontendColor={frontendColor}
                            backendColor={backendColor}
                            title="Frame Duration Timeline"
                        />
                    </Paper>
                )}

                {(viewType === 'histogram' || viewType === 'both') && (
                    <Paper
                        elevation={0}
                        sx={{
                            flex: 1,
                            display: 'flex',
                            flexDirection: 'column',
                            border: '1px solid',
                            borderColor: alpha(theme.palette.divider, 0.2),
                            overflow: 'hidden'  // Ensure chart doesn't overflow
                        }}
                    >
                        <FramerateHistogramView
                            frontendFramerate={currentFrontendFramerate}
                            backendFramerate={currentBackendFramerate}
                            recentFrontendFrameDurations={recentFrontendFrameDurations}
                            recentBackendFrameDurations={recentBackendFrameDurations}
                            frontendColor={frontendColor}
                            backendColor={backendColor}
                            title="Frame Duration Distribution"
                        />
                    </Paper>
                )}
            </Box>
        </Box>
    )
}

export default FramerateViewerPanel
