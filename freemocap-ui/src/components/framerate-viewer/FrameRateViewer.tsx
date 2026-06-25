// src/components/framerate-viewer/FrameRateViewer.tsx
import {useEffect, useRef, useState} from "react"
import {Box, IconButton, Paper, Stack, Tab, Tabs, Tooltip, Typography} from "@mui/material"
import {BarChart, ShowChart, TableChart} from "@mui/icons-material"
import {alpha, useTheme} from "@mui/material/styles"
import FramerateTimeseriesView from "./FramerateTimeseriesView"
import FramerateHistogramView from "./FramerateHistogramView"
import FramerateStatisticsView from "./FramerateStatisticsView"
import {useTranslation} from "react-i18next";
import {useServer} from "@/services/server/ServerContextProvider";
import {DetailedFramerate} from "@/services/server/server-helpers/framerate-store";
import {openPipelineMetricsWindow} from "@/services/electron-ipc/open-pipeline-metrics-window";
export const frontendColor: string = "#1976D2"
export const backendColor: string = "#ff4d00"

const fmtFps = (fr: DetailedFramerate | null): string => {
    if (!fr || !fr.frame_duration_mean || fr.frame_duration_mean <= 0) return "-- fps";
    return `${(1000 / fr.frame_duration_mean).toFixed(1)} fps ±${fr.frame_duration_stddev.toFixed(1)}ms`;
};

const FramerateCollapsedView = () => {
    const {getFramerateStore} = useServer();
    const backendRef = useRef<HTMLSpanElement>(null);
    const frontendRef = useRef<HTMLSpanElement>(null);

    useEffect(() => {
        const tick = () => {
            const snap = getFramerateStore().getSnapshot();
            if (backendRef.current) backendRef.current.textContent = fmtFps(snap.aggregateBackendFramerate);
            if (frontendRef.current) frontendRef.current.textContent = fmtFps(snap.aggregateFrontendFramerate);
        };
        tick();
        const id = setInterval(tick, 500);
        return () => clearInterval(id);
    }, [getFramerateStore]);

    return (
        <Box sx={{height: '100%', display: 'flex', alignItems: 'center', gap: 1.5, px: 1, overflow: 'hidden'}}>
            <Typography noWrap sx={{fontSize: '0.75rem', fontWeight: 'bold', color: 'text.secondary', flexShrink: 0}}>
                Camera Performance
            </Typography>
            <Typography noWrap sx={{fontSize: '0.75rem', color: backendColor, flexShrink: 0}}>
                Server: <span ref={backendRef}>-- fps</span>
            </Typography>
            <Typography noWrap sx={{fontSize: '0.75rem', color: frontendColor, flexShrink: 0}}>
                Display: <span ref={frontendRef}>-- fps</span>
            </Typography>
        </Box>
    );
};

export const FramerateViewerPanel = ({isCollapsed = false}: { isCollapsed?: boolean }) => {
    if (isCollapsed) return <FramerateCollapsedView/>;
    return <FramerateViewerPanelExpanded/>;
};

const FramerateViewerPanelExpanded = () => {
    const theme = useTheme()
    const { t } = useTranslation();
    const [mainTab, setMainTab] = useState<'framerate' | 'pipeline'>('framerate')
    const [showStats, setShowStats] = useState(true)
    const [showTimeseries, setShowTimeseries] = useState(true)
    const [showHistogram, setShowHistogram] = useState(true)

    const handleTabChange = (_: unknown, value: 'framerate' | 'pipeline'): void => {
        if (value === 'pipeline') {
            void openPipelineMetricsWindow();
            return;
        }
        setMainTab(value);
    };

    return (
        <Box sx={{
            height: '100%',
            display: 'flex',
            flexDirection: 'column',
            backgroundColor: theme.palette.background.default,
            p: 0.5,
            overflow: 'hidden'
        }}>
            <Tabs
                value={mainTab}
                onChange={handleTabChange}
                sx={{minHeight: 32, mb: 0.5, '& .MuiTab-root': {minHeight: 32, py: 0, fontSize: '0.75rem'}}}
            >
                <Tab value="framerate" label={t('cameraPerformanceMetrics')} />
                <Tab value="pipeline" label="Pipeline stages" />
            </Tabs>

            <Box sx={{
                flex: 1,
                minHeight: 0,
                display: 'flex',
                flexDirection: 'column',
                overflow: 'hidden',
            }}>
                <Box sx={{
                    display: 'flex',
                    justifyContent: 'flex-end',
                    alignItems: 'center',
                    mb: 0.25,
                    px: 0.5
                }}>
                    <Stack direction="row" spacing={0.25}>
                        <Tooltip title={t("statisticsView")}>
                            <IconButton
                                size="small"
                                onClick={() => setShowStats((v) => !v)}
                                sx={{padding: '2px', opacity: showStats ? 1 : 0.3}}
                            >
                                <TableChart sx={{fontSize: '1rem'}}/>
                            </IconButton>
                        </Tooltip>
                        <Tooltip title={t("timelineView")}>
                            <IconButton
                                size="small"
                                onClick={() => setShowTimeseries((v) => !v)}
                                sx={{padding: '2px', opacity: showTimeseries ? 1 : 0.3}}
                            >
                                <ShowChart sx={{fontSize: '1rem'}}/>
                            </IconButton>
                        </Tooltip>
                        <Tooltip title={t("distributionView")}>
                            <IconButton
                                size="small"
                                onClick={() => setShowHistogram((v) => !v)}
                                sx={{padding: '2px', opacity: showHistogram ? 1 : 0.3}}
                            >
                                <BarChart sx={{fontSize: '1rem'}}/>
                            </IconButton>
                        </Tooltip>
                    </Stack>
                </Box>

                {showStats && (
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
                            compact={true}
                        />
                    </Paper>
                </Box>
                )}

                <Box sx={{
                    flex: 1,
                    display: 'flex',
                    flexDirection: (showTimeseries && showHistogram) ? 'row' : 'column',
                    gap: 0.25,
                    overflow: 'hidden'
                }}>
                    {showTimeseries && (
                        <Paper
                            elevation={0}
                            sx={{
                                flex: 1,
                                display: 'flex',
                                flexDirection: 'column',
                                border: '1px solid',
                                borderColor: alpha(theme.palette.divider, 0.2),
                                overflow: 'hidden'
                            }}
                        >
                            <FramerateTimeseriesView
                                frontendColor={frontendColor}
                                backendColor={backendColor}
                                title={t("framerateTimeline")}
                            />
                        </Paper>
                    )}

                    {showHistogram && (
                        <Paper
                            elevation={0}
                            sx={{
                                flex: 1,
                                display: 'flex',
                                flexDirection: 'column',
                                border: '1px solid',
                                borderColor: alpha(theme.palette.divider, 0.2),
                                overflow: 'hidden'
                            }}
                        >
                            <FramerateHistogramView
                                frontendColor={frontendColor}
                                backendColor={backendColor}
                                title={t("framerateDistribution")}
                            />
                        </Paper>
                    )}
                </Box>
            </Box>
        </Box>
    )
}

export default FramerateViewerPanel
