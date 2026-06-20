/**
 * RecordingBrowser — lists available recording sessions from the server,
 * with search filtering, multi-field sorting, and rich per-recording metadata.
 */
import React, { useCallback, useEffect, useMemo, useState } from "react";
import clsx from "clsx";
import { useTranslation } from "react-i18next";
import { useElectronIPC } from "@/services";
import { RecordingStatusPanel } from "@/components/common/RecordingStatusPanel";
import { useRecordingStatus } from "@/hooks/useRecordingStatus";
import { useAppDispatch, useAppSelector } from "@/store";
import {
  activeRecordingSet,
  selectActiveRecordingBaseDirectory,
  splitParentAndName,
} from "@/store/slices/active-recording/active-recording-slice";
import {
  detectLayoutPreset,
  listDetectedLegacyMarkers,
} from "@/store/slices/active-recording/recording-structure";
import {
  fetchAllRecordings,
  type RecordingListEntry,
} from "@/store/slices/recording-status/recording-status-thunks";
import {
  selectRecordingsList,
  selectRecordingsFetchedAt,
  selectRecordingsIsLoading,
} from "@/store/slices/recording-status/recording-status-slice";
import { serverUrls } from "@/constants/server-urls";
import ButtonSm from "@/components/ui-components/ButtonSm";
import SubactionHeader from "@/components/ui-components/SubactionHeader";
import IconButton from "@/components/ui-components/IconButton";

export type RecordingEntry = RecordingListEntry;

export interface LoadedVideo {
  videoId: string;
  filename: string;
  streamUrl: string;
  sizeBytes: number;
}

interface RecordingBrowserProps {
  onRecordingLoaded: (
    videos: LoadedVideo[],
    recordingPath: string,
    recordingFps?: number,
    sources?: Record<
      string,
      {
        available: boolean;
        valid: boolean;
        video_count: number;
        videos: LoadedVideo[];
      }
    >,
    preferred?: string,
  ) => void;
  activeRecordingPath?: string | null;
}

type SortField = "date" | "name" | "size" | "cameras" | "frames" | "duration";
type SortDirection = "asc" | "desc";

function formatBytes(bytes: number): string {
  if (bytes <= 0) return "0 B";
  const k = 1024;
  const units = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${(bytes / Math.pow(k, i)).toFixed(i > 1 ? 1 : 0)} ${units[i]}`;
}

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  if (m >= 60) {
    const h = Math.floor(m / 60);
    const rm = m % 60;
    return `${h}h ${rm}m ${s}s`;
  }
  return `${m}m ${s}s`;
}

function parseTimestampFromName(name: string): Date | null {
  const fullMatch = name.match(
    /(\d{4})-(\d{2})-(\d{2})[T_](\d{2})[_:\-](\d{2})[_:\-](\d{2})/,
  );
  if (fullMatch) {
    const [, y, mo, d, h, mi, s] = fullMatch;
    return new Date(+y, +mo - 1, +d, +h, +mi, +s);
  }
  const dateMatch = name.match(/(\d{4})-(\d{2})-(\d{2})/);
  if (dateMatch) {
    const [, y, mo, d] = dateMatch;
    return new Date(+y, +mo - 1, +d);
  }
  return null;
}

function formatRelativeTime(date: Date): string {
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return "just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDays = Math.floor(diffHr / 24);
  if (diffDays < 7) return `${diffDays}d ago`;
  if (diffDays < 30) return `${Math.floor(diffDays / 7)}w ago`;
  return date.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: date.getFullYear() !== now.getFullYear() ? "numeric" : undefined,
  });
}

function getSortValue(rec: RecordingEntry, field: SortField): number | string {
  switch (field) {
    case "date": {
      const d = parseTimestampFromName(rec.name);
      return d ? d.getTime() : 0;
    }
    case "name":
      return rec.name.toLowerCase();
    case "size":
      return rec.total_size_bytes ?? 0;
    case "cameras":
      return rec.video_count;
    case "frames":
      return rec.total_frames ?? 0;
    case "duration":
      return rec.duration_seconds ?? 0;
  }
}

function compareRecordings(
  a: RecordingEntry,
  b: RecordingEntry,
  field: SortField,
  direction: SortDirection,
): number {
  const va = getSortValue(a, field);
  const vb = getSortValue(b, field);
  let cmp: number;
  if (typeof va === "string" && typeof vb === "string") {
    cmp = va.localeCompare(vb);
  } else {
    cmp = (va as number) - (vb as number);
  }
  return direction === "desc" ? -cmp : cmp;
}

const SORT_OPTIONS: { value: SortField; labelKey: string }[] = [
  { value: "date", labelKey: "date" },
  { value: "name", labelKey: "name" },
  { value: "size", labelKey: "size" },
  { value: "cameras", labelKey: "cameras" },
  { value: "frames", labelKey: "frames" },
  { value: "duration", labelKey: "duration" },
];

export const RecordingBrowser: React.FC<RecordingBrowserProps> = ({
  onRecordingLoaded,
  activeRecordingPath,
}) => {
  const { t } = useTranslation();
  const dispatch = useAppDispatch();
  const { api, isElectron } = useElectronIPC();

  const recordings = useAppSelector(selectRecordingsList);
  const recordingsFetchedAt = useAppSelector(selectRecordingsFetchedAt);
  const isLoadingList = useAppSelector(selectRecordingsIsLoading);
  const baseDirectory = useAppSelector(selectActiveRecordingBaseDirectory);

  const [isLoadingRecording, setIsLoadingRecording] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loadingPath, setLoadingPath] = useState<string | null>(null);

  const [manualPath, setManualPath] = useState(baseDirectory);
  const [filterText, setFilterText] = useState("");
  const [showFilter, setShowFilter] = useState(false);
  const [sortField, setSortField] = useState<SortField>("date");
  const [sortDir, setSortDir] = useState<SortDirection>("desc");
  const [selectedPath, setSelectedPath] = useState<string | null>(null);

  const fetchRecordings = useCallback(
    async (force = false) => {
      const MAX_CACHE_AGE_MS = 30_000;
      if (
        !force &&
        recordingsFetchedAt &&
        Date.now() - recordingsFetchedAt < MAX_CACHE_AGE_MS
      ) {
        return;
      }
      try {
        await dispatch(fetchAllRecordings()).unwrap();
      } catch (e) {
        setError(e instanceof Error ? e.message : t("failedToFetch"));
      }
    },
    [dispatch, recordingsFetchedAt],
  );

  useEffect(() => {
    if (recordings.length === 0) {
      fetchRecordings();
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const filteredSorted = useMemo(() => {
    let result = recordings;
    if (filterText.trim()) {
      const q = filterText.trim().toLowerCase();
      result = result.filter((r) => r.name.toLowerCase().includes(q));
    }
    return [...result].sort((a, b) =>
      compareRecordings(a, b, sortField, sortDir),
    );
  }, [recordings, filterText, sortField, sortDir]);

  const loadRecording = useCallback(
    async (recordingPath: string) => {
      setSelectedPath(recordingPath);
      setIsLoadingRecording(true);
      setLoadingPath(recordingPath);
      setError(null);

      try {
        const rec = recordings.find((r) => r.path === recordingPath);
        const recName = rec
          ? rec.name
          : recordingPath.split(/[\\/]/).pop() || recordingPath;
        const parsed = rec?.path ? splitParentAndName(rec.path) : null;
        const parentDir = parsed?.baseDirectory;

        const videosUrl = serverUrls.endpoints.playbackVideos(recName);
        const url = parentDir
          ? `${videosUrl}?recording_parent_directory=${encodeURIComponent(parentDir)}`
          : videosUrl;

        const response = await fetch(url);

        if (!response.ok) {
          const detail = await response
            .json()
            .catch(() => ({ detail: response.statusText }));
          throw new Error(detail.detail || response.statusText);
        }

        const data = await response.json();
        const baseUrl = serverUrls.getHttpUrl();

        let videos: LoadedVideo[];
        let sources:
          | Record<
              string,
              {
                available: boolean;
                valid: boolean;
                video_count: number;
                videos: LoadedVideo[];
              }
            >
          | undefined;
        let preferred: string | undefined;

        if (data.sources) {
          sources = {};
          for (const [key, src] of Object.entries(data.sources) as [
            string,
            any,
          ][]) {
            sources[key] = {
              available: src.available,
              valid: src.valid,
              video_count: src.video_count,
              videos: (src.videos || []).map((v: any) => ({
                videoId: v.video_id,
                filename: v.filename,
                streamUrl: `${baseUrl}${v.stream_url}`,
                sizeBytes: v.size_bytes,
              })),
            };
          }
          const resolvedPreferred: string =
            data.preferred_source || "synchronized";
          preferred = resolvedPreferred;
          videos = sources[resolvedPreferred]?.videos ?? [];
        } else {
          videos = data.map(
            (v: {
              video_id: string;
              filename: string;
              stream_url: string;
              size_bytes: number;
            }) => ({
              videoId: v.video_id,
              filename: v.filename,
              streamUrl: `${baseUrl}${v.stream_url}`,
              sizeBytes: v.size_bytes,
            }),
          );
        }

        const recFps = rec?.fps ?? undefined;

        const layoutPreset = rec?.layout_validation
          ? detectLayoutPreset(rec.layout_validation)
          : undefined;
        dispatch(
          activeRecordingSet({
            recordingName: parsed?.recordingName ?? recName,
            baseDirectory: parsed?.baseDirectory,
            origin: "browsed",
            layoutPreset,
          }),
        );

        onRecordingLoaded(videos, recName, recFps, sources, preferred);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load recording");
      } finally {
        setIsLoadingRecording(false);
        setLoadingPath(null);
      }
    },
    [onRecordingLoaded, recordings, dispatch],
  );

  const handleBrowseDirectory = useCallback(async () => {
    if (!isElectron || !api) return;
    const result: string | null = await api.fileSystem.selectDirectory.mutate();
    if (!result) return;
    const trimmed = result.trim().replace(/[\\/]+$/, "");
    setManualPath(trimmed);
    loadRecording(trimmed);
  }, [api, isElectron, loadRecording]);

  const toggleSortDir = () => {
    setSortDir((d) => (d === "desc" ? "asc" : "desc"));
  };

  return (
    <div className="playback-file-directory-inner-content flex playback-page-content pos-rel flex flex-col h-full overflow-hidden">
      {/* Folder selector */}
      <div className="load-group bg-middark br-1 p-1 flex flex-start flex-wrap gap-1 items-center">
        {/* <div className="flex flex-col flex-start items-center w-full gap-2"> */}
          <div className="recording-list-header flex gap-1 flex-row flex-wrap justify-content-space-between w-full">
              <div className="folder-directory-title-group flex flex-row gap-1">

              <SubactionHeader text="Folder Directory" />
              <div className="n-list-counter flex items-center flex-row">
                {recordings.length > 0 && (
                  <p className="tag camera-status-badge">
                    {filterText
                      ? `${filteredSorted.length} / ${recordings.length}`
                      : recordings.length}
                  </p>
                )}
                <SubactionHeader text={t("recordings")} />
              </div>
            </div>
            <div className="folder-directory-tool-bar flex flex-row gap-1 items-center">
              <IconButton
                title={showFilter ? t("hideFilter") : t("filter")}
                icon={showFilter ? "filter-active-icon" : "filter-icon"}
                className="icon-size-25"
                tooltip={true}
                tooltipText={showFilter ? t("hideFilter") : t("filter")}
                tooltipPosition="pos-bottom"
                onClick={() => {
                  if (showFilter) {
                    setFilterText("");
                    setShowFilter(false);
                  } else {
                    setShowFilter(true);
                  }
                }}
                style={{
                  backgroundColor: showFilter
                    ? "var(--color-info)"
                    : "transparent",
                }}
              />

              <IconButton
                title={t("sortBy", { direction: t(sortDir === "desc" ? "descending" : "ascending") })}
                icon={sortDir === "desc" ? "sort-icon" : "sortup-icon"}
                className="icon-size-25"
                tooltip={true}
                tooltipText={t("sortBy", { direction: t(sortDir === "desc" ? "descending" : "ascending") })}
                tooltipPosition="pos-bottom"
                onClick={toggleSortDir}
              />

              <select
                className="sort-select input-field"
                value={sortField}
                onChange={(e) => setSortField(e.target.value as SortField)}
                style={{ width: "63px", minWidth: "63px", maxWidth: "63px" }}
              >
                {SORT_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {t(opt.labelKey)}
                  </option>
                ))}
              </select>
              
            </div>
          </div>
          <div className="folder-path-selection-group flex gap-1 flex-row flex-nowrap items-center flex-row justify-content-space-between w-full">
            <ButtonSm
              iconClass="subfolder-icon"
              text={manualPath || "Select recording folder"}
              onClick={handleBrowseDirectory}
              title="Click to select recording folder"
              disabled={!isElectron}
              className="select-path bg-middark min-w-0 border-1 w-full border-mid-black"
              textClass="text-gray text-nowrap text md text-align-left flex flex-end"
            />
            <IconButton
                title={t("refresh")}
                icon="rotate-icon"
                className="icon-size-25"
                tooltip={true}
                tooltipText={t("refresh")}
                tooltipPosition="pos-bottom-right"
                onClick={() => fetchRecordings(true)}
                disabled={isLoadingList}
              />
          </div>
        </div>
      {/* </div> */}

      {error && (
        <p className="pl-2 flex flex-row text md tagtext-error">{error}</p>
      )}

      {/* Header + list wrapper */}
      <div className="flex flex-col flex-1 overflow-hidden bg-middark br-1 p-1 gap-1">
        {/* Header bar */}
        <div className="pb-1 recording-group flex flex-row flex-wrap flex-start items-center gap-1 justify-content-space-between">
          {showFilter && (
            <div className="flex flex-row input-with-string flex-1">
              <input
                className="input-field"
                placeholder={t("filter")}
                value={filterText}
                onChange={(e) => setFilterText(e.target.value)}
                autoFocus
              />
            </div>
          )}
        </div>

        {/* List */}
        {isLoadingList ? (
          <div className="flex items-center justify-center py-4">
            <span className="icon loader-icon icon-size-20" />
          </div>
        ) : filteredSorted.length === 0 ? (
          <div className="recording-warning-container flex flex-col flex-wrap p-6 m-4 text-center gap-1 items-center justify-center br-2">
            <span className="icon warning-icon icon-size-32" />
            <p className="text md text-white text-center">
              {recordings.length === 0
                ? t("noRecordingsFound")
                : "No recordings match your filter."}
            </p>
          </div>
        ) : (
          <div className="recording-list flex flex-col flex-1 overflow-y">
            {filteredSorted.map((rec) => (
              <RecordingRow
                key={rec.path}
                rec={rec}
                isLoading={loadingPath === rec.path}
                isAnyLoading={isLoadingRecording}
                isActive={selectedPath === rec.path}
                onClick={() => loadRecording(rec.path)}
                recordingsRootPath={
                  rec.path.slice(
                    0,
                    Math.max(
                      rec.path.lastIndexOf("/"),
                      rec.path.lastIndexOf("\\"),
                    ),
                  ) || null
                }
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

interface RecordingRowProps {
  rec: RecordingEntry;
  isLoading: boolean;
  isAnyLoading: boolean;
  isActive: boolean;
  onClick: () => void;
  recordingsRootPath: string | null;
}

const RecordingRow: React.FC<RecordingRowProps> = React.memo(
  ({ rec, isLoading, isAnyLoading, isActive, onClick, recordingsRootPath }) => {
    const parsedDate = parseTimestampFromName(rec.name);
    const { t } = useTranslation();
    const [expanded, setExpanded] = useState(false);

    const {
      status: detailedStatus,
      isLoading: statusLoading,
      error: statusError,
      refresh: refreshStatus,
    } = useRecordingStatus(expanded ? rec.name : null, {
      autoFetch: expanded,
      recordingParentDirectory: recordingsRootPath,
    });

    const summary = rec.status_summary;
    const ready = summary?.blender_export_ready ?? false;
    const stagesComplete = summary?.stages_complete ?? 0;
    const stagesTotal = summary?.stages_total ?? 0;

    const layoutPreset = rec.layout_validation
      ? detectLayoutPreset(rec.layout_validation)
      : "canonical";
    const isLegacyLayout = layoutPreset === "legacy_v1";
    const legacyMarkers = rec.layout_validation
      ? listDetectedLegacyMarkers(rec.layout_validation)
      : [];

    const toggleExpand = (e: React.MouseEvent): void => {
      e.stopPropagation();
      setExpanded((v) => !v);
    };

    return (
      <div
        className={clsx(
          "br-1 button quaternary flex text-white flex-col flex-start",
          isAnyLoading && !isLoading && "recording-row-disabled",
        )}
        style={
          isActive
            ? {
                backgroundColor: "var(--color-bg-primary)",
              }
            : undefined
        }
      >
        <div className="flex flex-row items-center w-full justify-content-space-between pos-rel">
          <button
            className={clsx(
              "flex flex-row br-1 flex-1 gap-1 p-2 items-center gap-1 text-left",
            )}
            onClick={onClick}
            disabled={isAnyLoading}
            style={{
              opacity: isAnyLoading && !isLoading ? 0.8 : 1,
            }}
          >
            <div className="flex flex-col flex-1">
              <div className="title-group flex flex-row mr-18 items-center gap-1 mb-1 justify-content-space-between flex-wrap">
                <div className="title flex flex-row items-center">

                  <p
                    className="text md text-white recording-name m-0 text-nowrap flex flex-row"
                    style={{
                      fontWeight: 600,
                      color: isActive ? "var(--color-info)" : undefined,
                    }}
                  >
                    {rec.name}
                  </p>
                </div>
                              <div className="title-info-group flex flex-row items-center gap-1">
                {summary && (
                  <span
                    title={
                      ready
                        ? "All pipeline stages complete — ready for Blender"
                        : `${stagesComplete}/${stagesTotal} pipeline stages complete`
                    }
                    className="stage-group text-nowrap text md mr-2 text-gray"
                    style={{
                      color: ready
                        ? "var(--color-success)"
                        : "var(--log-trace)",
                    }}
                  >
                    {ready
                      ? "Blender ready"
                      : `${stagesComplete}/${stagesTotal} stages`}
                  </span>
                )}
                {parsedDate && (
                  <span
                    title={parsedDate.toLocaleString()}
                    className="flex flex-row text-nowrap time-group text md text-gray"
                  >
                    {formatRelativeTime(parsedDate)}
                  </span>
                )}
              </div>
                {/* Commented out: loaded in playback badge
                {isActive && (
                  <span className="tag text sm">
                    loaded in playback
                  </span>
                )} */}
                {isLegacyLayout && (
                  <span
                    className="tag text sm"
                    title={`Legacy folder layout (legacy_v1)${legacyMarkers.length > 0 ? ": " + legacyMarkers.join(", ") : ""}`}
                    style={{
                      fontSize: "0.65rem",
                      backgroundColor: "rgba(255,167,38,0.18)",
                      color: "#ffb74d",
                      border: "1px solid rgba(255,167,38,0.5)",
                    }}
                  >
                    Legacy
                  </span>
                )}
              </div>
              <div className="flex flex-row items-center gap-1 data-group-container flex-wrap">
                <div className="flex flex-row items-center gap-1 data-group-1">
                  <span className="text flex flex-row text-nowrap md text-gray tag" title="Camera streams">
                    {`${rec.video_count} cam${rec.video_count !== 1 ? "s" : ""}`}
                  </span>
                  {rec.total_size_bytes != null && rec.total_size_bytes > 0 && (
                    <span
                      className="text md text-gray text-nowrap tag"
                      title="Total size on disk"
                    >
                      {formatBytes(rec.total_size_bytes)}
                    </span>
                  )}
                  {rec.duration_seconds != null && rec.duration_seconds > 0 && (
                    <span
                      className="text md text-gray text-nowrap tag"
                      title="Recording duration"
                    >
                      {formatDuration(rec.duration_seconds)}
                    </span>
                  )}
                </div>
                <div className="flex flex-row items-center gap-1 data-group-2">
                
                
                
                  {rec.total_frames != null && rec.total_frames > 0 && (
                    <span
                      title={t("frameCountPerCamera")}
                      className="text-nowrap tag camera-config-chip text-gray"
                    >
                      {`${rec.total_frames.toLocaleString()} frames`}
                    </span>
                  )}
                  {rec.fps != null && rec.fps > 0 && (
                    <span
                      className="text-nowrap text md tag camera-config-chip tag text-gray"
                      title={t("recordingCaptureFps")}
                    >
                      {`${rec.fps} fps`}
                    </span>
                  )}
                </div>
                            </div>
                            <div className="load-container pos-abs" style={{ minWidth: 36 }}>
                {isLoading ? (
                  <span
                    className="icon loader-icon icon-size-16"
                    style={{ color: "var(--color-info)" }}
                  />
                ) : (
                  <span
                    className="icon load-icon icon-size-16"
                    style={{ color: "var(--color-info)" }}
                  />
                )}
                            </div>
              </div>
          </button>

          <IconButton
            title={expanded ? "Hide folder detail" : "Show folder detail"}
            icon="arrowdown-icon"
            className="pos-abs top-2 right-2 icon-size-25 br-100"
            onClick={toggleExpand}
            style={{
              transform: expanded ? "rotate(180deg)" : "rotate(0deg)",
              transition: "transform 0.2s ease",
              alignSelf: "center",
            }}
          />
        </div>

        {expanded && (
          <div className="px-2 pb-2 w-full">
            <RecordingStatusPanel
              status={detailedStatus}
              isLoading={statusLoading}
              error={statusError}
              onRefresh={refreshStatus}
            />
          </div>
        )}
      </div>
    );
  },
);

RecordingRow.displayName = "RecordingRow";
