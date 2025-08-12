// src/components/framerate-viewer/FramerateStatisticsView.tsx
import {
  Box,
  Divider,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tooltip,
  Typography,
} from "@mui/material";
import { alpha, useTheme } from "@mui/material/styles";
import { CurrentFramerate } from "@/store/slices/framerateTrackerSlice";
import { useState } from "react";

type FramerateStatisticsViewProps = {
  frontendFramerate: CurrentFramerate | null;
  backendFramerate: CurrentFramerate | null;
  compact?: boolean;
};

// Format number with fixed precision
const formatNumber = (num: number | null, precision = 3) => {
  return num !== null ? num.toFixed(precision) : "N/A";
};

type ProgressiveTooltipProps = {
  shortInfo: string;
  longInfo: string;
  children: React.ReactElement;
};

// Progressive tooltip component that shows more info on click
export const ProgressiveTooltip = ({
  shortInfo,
  longInfo,
  children,
}: ProgressiveTooltipProps) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const theme = useTheme();

  const handleTooltipClick = (e: React.MouseEvent) => {
    e.preventDefault();
    setIsExpanded(!isExpanded);
  };

  return (
    <Tooltip
      title={
        <Box onClick={handleTooltipClick} sx={{ cursor: "pointer" }}>
          <Typography variant="body2">
            {isExpanded ? longInfo : shortInfo}
          </Typography>
          <Typography
            variant="caption"
            color="text.secondary"
            sx={{ display: "block", mt: 1, textAlign: "center" }}
          >
            {isExpanded ? "Click to show less" : "Click to learn more"}
          </Typography>
        </Box>
      }
      arrow
      placement="top"
      componentsProps={{
        tooltip: {
          sx: {
            backgroundColor: theme.palette.background.paper,
            color: theme.palette.text.primary,
            border: `1px solid ${theme.palette.divider}`,
            boxShadow: theme.shadows[3],
            maxWidth: isExpanded ? 500 : 300,
            p: 1.5,
          },
        },
      }}
    >
      {children}
    </Tooltip>
  );
};

type HeaderCellWithTooltipProps = {
  label: string;
  shortInfo: string;
  longInfo: string;
  style?: object;
  align?: "inherit" | "left" | "center" | "right" | "justify";
};

// Reusable tooltip component for column headers
export const HeaderCellWithTooltip = ({
  label,
  shortInfo,
  longInfo,
  style = {},
  align = "center",
}: HeaderCellWithTooltipProps) => {
  return (
    <ProgressiveTooltip shortInfo={shortInfo} longInfo={longInfo}>
      <TableCell align={align} sx={style}>
        {label}
      </TableCell>
    </ProgressiveTooltip>
  );
};

type FramerateRowProps = {
  framerateData: CurrentFramerate | null;
  colorMap: Record<string, string>;
  getCellStyle: (metricType: string) => object;
  isDarkMode: boolean;
  theme: any;
  shortTooltip: string;
  longTooltip: string;
};

const FramerateRow = ({
  framerateData,
  colorMap,
  getCellStyle,
  isDarkMode,
  theme,
  shortTooltip,
  longTooltip,
}: FramerateRowProps) => {
  const isBackend =
    framerateData?.framerate_source === "Backend" ||
    (!framerateData?.framerate_source && framerateData);

  return (
    <TableRow>
      <ProgressiveTooltip shortInfo={shortTooltip} longInfo={longTooltip}>
        <TableCell
          sx={{
            fontWeight: "bold",
            borderLeft: `3px solid ${colorMap.current}`,
            paddingY: 0.5,
            color: isDarkMode
              ? isBackend
                ? theme.palette.secondary.light
                : theme.palette.primary.light
              : isBackend
              ? theme.palette.secondary.main
              : theme.palette.primary.main,
            cursor: "help",
          }}
        >
          {framerateData?.framerate_source ||
            (isBackend ? "Backend" : "Frontend")}
          <Typography
            variant="caption"
            display="block"
            color="text.secondary"
            sx={{ fontSize: "0.6rem" }}
          >
            {framerateData?.calculation_window_size || 0} samples
          </Typography>
        </TableCell>
      </ProgressiveTooltip>

      <MetricCell
        label="current"
        colorMap={colorMap}
        getCellStyle={getCellStyle}
        primaryValue={framerateData?.mean_frame_duration_ms}
        primarySuffix="ms"
        secondaryValue={framerateData?.mean_frames_per_second}
        secondarySuffix="fps"
      />

      <MetricCell
        label="min"
        colorMap={colorMap}
        getCellStyle={getCellStyle}
        primaryValue={framerateData?.frame_duration_min}
        primarySuffix="ms"
        secondaryValue={
          framerateData?.frame_duration_min &&
          framerateData.frame_duration_min > 0
            ? 1000 / framerateData.frame_duration_min
            : null
        }
        secondarySuffix="fps"
      />

      <MetricCell
        label="max"
        colorMap={colorMap}
        getCellStyle={getCellStyle}
        primaryValue={framerateData?.frame_duration_max}
        primarySuffix="ms"
        secondaryValue={
          framerateData?.frame_duration_max &&
          framerateData.frame_duration_max > 0
            ? 1000 / framerateData.frame_duration_max
            : null
        }
        secondarySuffix="fps"
      />

      <MetricCell
        label="mean"
        colorMap={colorMap}
        getCellStyle={getCellStyle}
        primaryValue={framerateData?.frame_duration_mean}
        primarySuffix="ms"
        secondaryValue={framerateData?.frame_duration_mean && framerateData.frame_duration_mean > 0 
          ? 1000 / framerateData.frame_duration_mean 
          : null}
        secondarySuffix="fps"
      />

      <MetricCell
        label="median"
        colorMap={colorMap}
        getCellStyle={getCellStyle}
        primaryValue={framerateData?.frame_duration_median}
        primarySuffix="ms"
        secondaryValue={framerateData?.frame_duration_median && framerateData.frame_duration_median > 0 
          ? 1000 / framerateData.frame_duration_median 
          : null}
        secondarySuffix="fps"
      />

      <MetricCell
        label="stdDev"
        colorMap={colorMap}
        getCellStyle={getCellStyle}
        primaryValue={framerateData?.frame_duration_stddev}
        primarySuffix="ms"
        secondaryValue={
          framerateData
            ? framerateData.frame_duration_coefficient_of_variation * 100
            : null
        }
        secondarySuffix="CV%"
      />
    </TableRow>
  );
};

type MetricCellProps = {
  label: string;
  colorMap: Record<string, string>;
  getCellStyle: (metricType: string) => object;
  primaryValue: number | null | undefined;
  primarySuffix?: string;
  secondaryValue?: number | null | undefined;
  secondarySuffix?: string;
};

const MetricCell = ({
  label,
  colorMap,
  getCellStyle,
  primaryValue,
  primarySuffix = "",
  secondaryValue,
  secondarySuffix = "",
}: MetricCellProps) => {
  return (
    <TableCell align="center" sx={getCellStyle(label)}>
      <Typography
        fontWeight="bold"
        fontFamily="monospace"
        color={colorMap[label]}
        sx={{ fontSize: "0.7rem", whiteSpace: "nowrap" }}
      >
        {formatNumber(primaryValue ?? null)} {primarySuffix}
      </Typography>
      {secondaryValue !== undefined && (
        <Typography
          variant="caption"
          color={colorMap[label]}
          sx={{ fontSize: "0.6rem", opacity: 0.9, whiteSpace: "nowrap" }}
        >
          {formatNumber(secondaryValue ?? null)} {secondarySuffix}
        </Typography>
      )}
    </TableCell>
  );
};

export default function FramerateStatisticsView({
  frontendFramerate,
  backendFramerate,
  compact = false,
}: FramerateStatisticsViewProps) {
  const theme = useTheme();
  const isDarkMode = theme.palette.mode === "dark";

  // Define color map with high contrast for both light and dark themes
  const colorMap: Record<string, string> = {
    current: isDarkMode
      ? theme.palette.success.light
      : theme.palette.success.main,
    min: isDarkMode ? theme.palette.info.light : theme.palette.info.main,
    max: isDarkMode ? theme.palette.error.light : theme.palette.error.main,
    mean: isDarkMode ? theme.palette.warning.light : theme.palette.warning.main,
    median: isDarkMode
      ? theme.palette.warning.dark
      : theme.palette.warning.dark,
    stdDev: isDarkMode
      ? theme.palette.primary.light
      : theme.palette.primary.main,
    cv: isDarkMode
      ? theme.palette.secondary.light
      : theme.palette.secondary.main,
  };

  // Generate cell style based on metric type
  const getCellStyle = (metricType: string) => {
    return {
      backgroundColor: alpha(
        colorMap[metricType] || theme.palette.grey[500],
        isDarkMode ? 0.2 : 0.1
      ),
      borderBottom: "none",
      padding: "2px 4px",
    };
  };

  // Common header cell styles
  const headerCellStyle = {
    fontWeight: "bold",
    paddingY: 0.5,
  };

  // Tooltips content - short and long versions
  const tooltips = {
    source: {
      short: "Frontend displays frames, Backend captures frames.",
      long: "The backend is the true rate at which frames are pulled/recorded from the camera, while the frontend is the rate at which they are received and displayed. Skellycam prioritizes backend performance for recording quality, so that number should stay more stable. If the frontend framerate diverges from the backend, it indicates your system resources are taxed. Consider using fewer cameras or decreasing framerate/resolution.",
    },
    current: {
      short: "Most recent frame time and corresponding FPS.",
      long: "This shows the most recent measurement of how long it takes to process a single frame (in milliseconds) and the equivalent frames per second (FPS). Lower frame times and higher FPS indicate better performance.",
    },
    min: {
      short: "Fastest frame time (lowest latency) and highest FPS achieved.",
      long: "This represents the minimum time it took to process a single frame during the sampling window. This corresponds to the maximum FPS your system achieved during optimal conditions.",
    },
    max: {
      short: "Slowest frame time (highest latency) and lowest FPS experienced.",
      long: "This represents the maximum time it took to process a single frame during the sampling window. This corresponds to the minimum FPS your system achieved during worst-case conditions. Occasional spikes are normal, but consistently high values may indicate performance issues.",
    },
    mean: {
      short: "Average frame time and FPS across all samples.",
      long: "The arithmetic mean (average) of all frame times measured during the sampling window and the corresponding FPS. This gives a good overall picture of performance but may be skewed by outliers.",
    },
    median: {
      short: "Middle value of all frame times (50th percentile).",
      long: "The median represents the middle value when all frame times are sorted from fastest to slowest. Unlike the mean, the median is not affected by extreme outliers, making it a more stable indicator of typical performance.",
    },
    stdDev: {
      short: "Measures frame time variability. CV% is relative variability.",
      long: "Standard deviation measures the amount of variation in frame times. Lower values indicate more consistent performance. The Coefficient of Variation (CV%) expresses this variability as a percentage of the mean, making it easier to compare stability across different frame rates. Lower CV% indicates more stable performance.",
    },
  };

  return (
    <TableContainer
      component={Paper}
      elevation={0}
      sx={{
        backgroundColor: "transparent",
        border: "none",
        overflowX: "auto",
      }}
    >
      <Table
        size="small"
        padding="none"
        sx={{
          "& .MuiTableCell-root": {
            fontSize: "0.65rem",
            lineHeight: "1.1",
            whiteSpace: "nowrap",
          },
        }}
      >
        <TableHead>
          <TableRow>
            <HeaderCellWithTooltip
              label="Source"
              shortInfo={tooltips.source.short}
              longInfo={tooltips.source.long}
              style={{
                ...headerCellStyle,
                width: "12%",
                color: theme.palette.text.primary,
              }}
              align="left"
            />
            <HeaderCellWithTooltip
              label="Current"
              shortInfo={tooltips.current.short}
              longInfo={tooltips.current.long}
              style={{
                ...headerCellStyle,
                ...getCellStyle("current"),
              }}
            />
            <HeaderCellWithTooltip
              label="Min"
              shortInfo={tooltips.min.short}
              longInfo={tooltips.min.long}
              style={{
                ...headerCellStyle,
                ...getCellStyle("min"),
              }}
            />
            <HeaderCellWithTooltip
              label="Max"
              shortInfo={tooltips.max.short}
              longInfo={tooltips.max.long}
              style={{
                ...headerCellStyle,
                ...getCellStyle("max"),
              }}
            />
            <HeaderCellWithTooltip
              label="Mean"
              shortInfo={tooltips.mean.short}
              longInfo={tooltips.mean.long}
              style={{
                ...headerCellStyle,
                ...getCellStyle("mean"),
              }}
            />
            <HeaderCellWithTooltip
              label="Median"
              shortInfo={tooltips.median.short}
              longInfo={tooltips.median.long}
              style={{
                ...headerCellStyle,
                ...getCellStyle("median"),
              }}
            />
            <HeaderCellWithTooltip
              label="StdDev/CV"
              shortInfo={tooltips.stdDev.short}
              longInfo={tooltips.stdDev.long}
              style={{
                ...headerCellStyle,
                ...getCellStyle("stdDev"),
              }}
            />
          </TableRow>
          {/* Add the divider inside TableHead */}
          <TableRow>
            <TableCell colSpan={7} sx={{ padding: 0 }}>
              <Divider sx={{ borderColor: theme.palette.divider }} />
            </TableCell>
          </TableRow>
        </TableHead>

        <TableBody>
          {/* Frontend Row */}
          <FramerateRow
            framerateData={frontendFramerate}
            colorMap={colorMap}
            getCellStyle={getCellStyle}
            isDarkMode={isDarkMode}
            theme={theme}
            shortTooltip="Displays received frames."
            longTooltip="Frontend represents the UI rendering performance. It shows how quickly your display receives and renders frames. Performance issues here won't affect recording quality but may impact your ability to monitor cameras in real-time."
          />

          {/* Divider between rows - now properly inside TableBody */}
          <TableRow>
            <TableCell colSpan={7} sx={{ padding: 0 }}>
              <Divider sx={{ borderColor: theme.palette.divider }} />
            </TableCell>
          </TableRow>

          {/* Backend Row */}
          <FramerateRow
            framerateData={backendFramerate}
            colorMap={colorMap}
            getCellStyle={getCellStyle}
            isDarkMode={isDarkMode}
            theme={theme}
            shortTooltip="Captures frames from camera."
            longTooltip="Backend represents the camera frame-grabbing performance. This is the true rate at which frames are pulled from the camera and saved during recording. This is the most important metric for recording quality and should remain stable even if frontend performance fluctuates."
          />
        </TableBody>
      </Table>
    </TableContainer>
  );
}
