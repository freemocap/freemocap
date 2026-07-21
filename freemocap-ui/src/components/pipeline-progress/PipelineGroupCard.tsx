import { useNavigate } from "react-router-dom";
import { useAppDispatch } from "@/store/hooks";
import { activeRecordingSet } from "@/store/slices/active-recording/active-recording-slice";
import { useElectronIPC } from "@/services";
import {
  PipelineGroup,
  PipelinePhase,
  PipelineProgress,
  PHASE_LABELS,
  PIPELINE_TYPE_CONFIG,
} from "@/store/slices/pipelines";
import { stopPipeline } from "@/store/slices/pipelines/pipelines-thunks";
import IconButton from "@/components/ui-components/IconButton";

function formatTimeAgo(timestamp: number): string {
  const seconds = Math.floor((Date.now() - timestamp) / 1000);
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h ago`;
}

function SubProgressBar({
  pipeline,
  label,
  isAggregator = false,
}: {
  pipeline: PipelineProgress;
  label: string;
  isAggregator?: boolean;
}) {
  const isFailed = pipeline.phase === PipelinePhase.FAILED;
  const isComplete = pipeline.phase === PipelinePhase.COMPLETE;
  const isTerminal = isComplete || isFailed;
  const isIndeterminate =
    isAggregator && !isTerminal && pipeline.phase !== PipelinePhase.SETTING_UP;

  const rightText =
    isTerminal && pipeline.completedAt
      ? formatTimeAgo(pipeline.completedAt)
      : isIndeterminate
        ? pipeline.detail || PHASE_LABELS[pipeline.phase]
        : `${pipeline.progress}%`;

  const progressColor = isFailed
    ? "var(--color-error)"
    : isComplete
      ? "var(--color-success)"
      : "var(--color-info)";

  return (
    <div className="mb-1 flex flex-col gap-1" style={{ opacity: isTerminal ? 1 : 1 }}>
      <div className="flex flex-row justify-content-space-between items-center pipeline-group-card__label-row">
        <p className="text md  flex-1 mr-1 m-0 truncate">{label}</p>
        <p className="text md  flex-shrink-0 m-0 truncate pipeline-group-card__max-width">
          {rightText}
        </p>
      </div>
      <div className="sub-progress-track">
        {!isIndeterminate && (
          <div
            className="update-progress-fill h-full sub-progress-fill"
            style={{
              width: `${pipeline.progress}%`,
              backgroundColor: progressColor,
            }}
          />
        )}
        {isIndeterminate && (
          <div
            className="h-full sub-progress-indeterminate"
            style={{ backgroundColor: progressColor }}
          />
        )}
      </div>
      {isFailed && pipeline.detail && (
        <p
          title={pipeline.detail}
          className="text md text-error block m-0 truncate pipeline-group-card__error-text"
        >
          {pipeline.detail}
        </p>
      )}
    </div>
  );
}

export default function PipelineGroupCard({
  group,
  onDismiss,
}: {
  group: PipelineGroup;
  onDismiss?: () => void;
}) {
  const dispatch = useAppDispatch();
  const navigate = useNavigate();
  const { api } = useElectronIPC();

  const overallProgress =
    group.aggregator?.progress ??
    (group.videoNodes.length > 0
      ? Math.round(
          group.videoNodes.reduce((sum, n) => sum + n.progress, 0) /
            group.videoNodes.length,
        )
      : 0);

  const borderColor = group.isFailed
    ? "var(--color-error)"
    : group.isComplete
      ? "var(--color-success)"
      : "var(--color-border-secondary)";
  const typeConfig = group.pipelineType
    ? PIPELINE_TYPE_CONFIG[group.pipelineType]
    : null;
  const fullPath = group.recordingPath || undefined;
  const recordingName = group.recordingName;
  const pipelineId = group.basePipelineId;

  const handleOpenFolder = async () => {
    if (!fullPath) return;
    try {
      await api?.fileSystem.openFolder.mutate({ path: fullPath });
    } catch (err) {
      console.error("Failed to open recording folder:", err);
    }
  };

  const handleLoadPlayback = () => {
    if (!group.recordingName) return;
    dispatch(
      activeRecordingSet({
        recordingName: group.recordingName,
        origin: "browsed",
      }),
    );
    navigate("/playback");
  };

  const borderClass = group.isFailed
    ? "pipeline-group-card__border-failed"
    : group.isComplete
      ? "pipeline-group-card__border-complete"
      : "pipeline-group-card__border-running";

  const opacityClass = group.isActive ? "" : "pipeline-group-card__inactive";

  return (
    <div
      className={`progress-container flex flex-col gap-2 text-white br-2 m-1 bg-dark pipeline-group-card ${borderClass} ${opacityClass}`.trim()}
    >
      <div className="flex flex-row items-center mb-1">
        {typeConfig && (
          <div
            className="flex-shrink-0 br-1 pipeline-group-card__type-badge"
            style={{
              backgroundColor: typeConfig.color + "22",
              border: `1px solid ${typeConfig.color}66`,
            }}
          >
            <p
              className="flex flex-col gap-2 text md m-0 pipeline-group-card__type-badge-text"
              style={{ color: typeConfig.color }}
            >
              {typeConfig.label}
            </p>
          </div>
        )}
        <p className="text md flex-1 flex min-w-0 m-0 truncate">
          <span className="">Pipeline: </span>
          <span className="pipeline-group-card__bold">{pipelineId}</span>
        </p>

        
        <div className="flex flex-row gap-2 items-center">
            <p className="text bg text-white flex-shrink-0 m-0 mr-2">
          {overallProgress}%
                </p>
            <IconButton
              title="Open folder"
              icon="subfolder-icon"
              className="icon-size-25 p-01"
              onClick={handleOpenFolder}
              disabled={!fullPath}
              tooltip={true}
              tooltipText="Open folder"
            />
            <IconButton
              title="Load in playback"
              icon="play-icon"
              className="icon-size-25 p-01"
              onClick={handleLoadPlayback}
              tooltip={true}
              tooltipText="Load in playback"
            />
            {group.isActive && (
              <IconButton
                title="Stop pipeline"
                icon="stop-alert-icon"
                className="icon-size-25 p-01"
                onClick={() => dispatch(stopPipeline(group.basePipelineId))}
                style={{ color: "var(--color-error)" }}
                tooltip={true}
                tooltipText="Stop pipeline"
              />
            )}
            {onDismiss && (
              <IconButton
                icon="close-icon"
                className="icon-size-25 p-01"
                onClick={onDismiss}
                tooltip={true}
                tooltipText="Dismiss"
              />
            )}
        </div>
      </div>
      <div title={fullPath}>
        <p className="text md flex-1 min-w-0 m-0 truncate">
          <span className="">Recording: </span>
          <span className="pipeline-group-card__bold">{recordingName}</span>
        </p>
      </div>
      {group.videoNodes.length > 0 && (
        <div
          className={`flex flex-col gap-2 pl-2 pipeline-group-card__border-left ${group.aggregator ? "pipeline-group-card__border-left-aggregator" : "pipeline-group-card__border-left-no-aggregator"}`}
        >
          {group.videoNodes.map((node) => {
            const cameraId = node.pipelineId.includes(":")
              ? node.pipelineId.split(":").slice(1).join(":")
              : node.pipelineId;
            return (
              <SubProgressBar
                key={node.pipelineId}
                pipeline={node}
                label={`Camera: ${cameraId}`}
              />
            );
          })}
        </div>
      )}

      {group.aggregator && (
        <div className="flex flex-col gap-2 p-2 br-2 bg-darkgray ">
          <SubProgressBar
            pipeline={group.aggregator}
            isAggregator={true}
            label={
              group.aggregator.phase === PipelinePhase.COMPLETE
                ? "Aggregation complete"
                : group.aggregator.phase === PipelinePhase.FAILED
                  ? "Aggregation failed"
                  : group.videoNodes.length > 0
                    ? `Aggregating ${group.videoNodes.length} camera${group.videoNodes.length !== 1 ? "s" : ""}`
                    : PHASE_LABELS[group.aggregator.phase]
            }
          />
        </div>
      )}
    </div>
  );
}
