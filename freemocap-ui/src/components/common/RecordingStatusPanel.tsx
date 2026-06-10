import React, { useState } from "react";
import { RecordingStatus } from "@/types/recording-status";

interface RecordingStatusPanelProps {
    status: RecordingStatus | null;
    isLoading?: boolean;
    error?: string | null;
    onRefresh?: () => void;
    defaultExpanded?: boolean;
    activeCalibrationTomlPath?: string | null;
    folderExists?: boolean;
    recordingFolderPath?: string | null;
}

const humanizeBytes = (bytes: number | null): string => {
    if (bytes == null) return "—";
    if (bytes < 1024) return `${bytes} B`;
    const units = ["KB", "MB", "GB", "TB"];
    let value = bytes / 1024;
    let i = 0;
    while (value >= 1024 && i < units.length - 1) { value /= 1024; i++; }
    return `${value.toFixed(value >= 10 ? 0 : 1)} ${units[i]}`;
};

const formatTimestamp = (iso: string | null): string => {
    if (!iso) return "";
    try {
        const d = new Date(iso);
        if (Number.isNaN(d.getTime())) return iso;
        return d.toLocaleString();
    } catch { return iso; }
};

const StageRow: React.FC<{ name: string; complete: boolean; present: number; total: number; children?: React.ReactNode }> = ({
    name, complete, present, total, children
}) => {
    const [open, setOpen] = useState(false);
    const label = total > 1 ? `${name} (${present}/${total})` : name;
    return (
        <div className="border-1 border-mid-black br-1 mb-1">
            <div
                className="flex flex-row items-center gap-1 p-1"
                
                onClick={() => setOpen(v => !v)}
            >
                <span className={`icon icon-size-20 ${complete ? 'upToDate-icon' : 'close-icon'}`} />
                <span className="text sm text-white flex-1">{label}</span>
                <span className="icon icon-size-20 collapse-icon" style={{ transform: open ? 'rotate(0deg)' : 'rotate(-90deg)' }} />
            </div>
            {open && children && (
                <div className="p-1 pt-0">{children}</div>
            )}
        </div>
    );
};

export const RecordingStatusPanel: React.FC<RecordingStatusPanelProps> = ({
    status,
    isLoading = false,
    error = null,
    onRefresh,
    defaultExpanded = false,
    activeCalibrationTomlPath = null,
    folderExists = true,
    recordingFolderPath = null,
}) => {
    const [expanded, setExpanded] = useState(defaultExpanded);

    const stagesComplete = status ? status.stages.filter((s) => s.complete).length : 0;
    const stagesTotal = status ? status.stages.length : 0;
    const allStagesComplete = stagesTotal > 0 && stagesComplete === stagesTotal;
    const hasBlend = !!status?.has_blend_file;
    const exportReady = !!status?.blender_export_ready;

    const summaryLabel = !folderExists
        ? "Folder not created yet"
        : status
            ? allStagesComplete && hasBlend
                ? "Fully processed"
                : exportReady && !hasBlend
                    ? "Ready for Blender"
                    : `${stagesComplete}/${stagesTotal} stages complete`
            : isLoading ? "Checking…"
            : error ? "Status unavailable"
            : "No status";

    const summaryColor = !folderExists ? 'text-warning'
        : (allStagesComplete && hasBlend) ? 'text-white'
        : 'text-gray';

    return (
        <div className="br-1 border-1 border-mid-black overflow-hidden">
            <div
                className="flex flex-row items-center gap-1 p-1"
               
                onClick={() => setExpanded(v => !v)}
            >
                <span className="icon info-icon icon-size-20" style={{ backgroundImage: 'url("data:image/svg+xml,%3csvg width=\'16\' height=\'16\' viewBox=\'0 0 16 16\' fill=\'none\' xmlns=\'http://www.w3.org/2000/svg\'%3e%3ccircle cx=\'8\' cy=\'8\' r=\'6\' stroke=\'%232ba4ff\' stroke-width=\'1.5\'/%3e%3cpath d=\'M8 7v4M8 5.5v.5\' stroke=\'%232ba4ff\' stroke-width=\'1.5\' stroke-linecap=\'round\'/%3e%3c/svg%3e")' }} />
                <span className="text sm text-gray flex-1">Recording folder</span>
                <span className={`tag text sm ${summaryColor}`}>{summaryLabel}</span>
                {onRefresh && (
                    <button
                        className="button icon-button br-1"
                        onClick={(e) => { e.stopPropagation(); onRefresh(); }}
                        disabled={isLoading}
                        title="Re-check folder"
                    >
                        {isLoading
                            ? <span className="icon loader-icon icon-size-20" />
                            : <span className="icon rotate-icon icon-size-20" />
                        }
                    </button>
                )}
                <span className="icon icon-size-20 collapse-icon" style={{ transform: expanded ? 'rotate(0deg)' : 'rotate(-90deg)' }} />
            </div>

            {expanded && (
                <div className="flex flex-col gap-1 p-2">
                    {error && (
                        <div className="toast-notification error">
                            <p className="text sm">{error}</p>
                        </div>
                    )}

                    {!folderExists && (
                        <div className="toast-notification">
                            <p className="text sm text-warning">Recording folder does not exist yet. It will be created when you start recording.</p>
                            {recordingFolderPath && (
                                <p className="text sm text-gray mt-1" style={{ fontFamily: 'monospace', wordBreak: 'break-all' }}>
                                    {recordingFolderPath}
                                </p>
                            )}
                        </div>
                    )}

                    {activeCalibrationTomlPath && (
                        <div>
                            <p className="text sm text-gray">Active calibration TOML:</p>
                            <p className="text sm" style={{ fontFamily: 'monospace', color: 'var(--color-success)', wordBreak: 'break-all' }}>
                                {activeCalibrationTomlPath}
                            </p>
                        </div>
                    )}

                    {!status && !isLoading && !error && (
                        <p className="text sm text-gray">No status loaded.</p>
                    )}

                    {status && (
                        <div>
                            {status.stages.map((stage) => (
                                <StageRow
                                    key={stage.name}
                                    name={stage.name}
                                    complete={stage.complete}
                                    present={stage.present_count}
                                    total={stage.total_count}
                                >
                                    {stage.files.length === 0 ? (
                                        <p className="text sm text-gray">No files found.</p>
                                    ) : (
                                        <div className="flex flex-col gap-1">
                                            {stage.files.map((f) => (
                                                <div
                                                    key={f.path ?? f.name}
                                                    className="flex flex-row items-center gap-1"
                                                    style={{ fontFamily: 'monospace' }}
                                                >
                                                    <span className={`icon icon-size-12 ${f.exists ? 'upToDate-icon' : 'close-icon'}`} />
                                                    <span className={`text sm flex-1 ${f.exists ? 'text-white' : 'text-gray'}`} style={{ wordBreak: 'break-all' }}>
                                                        {f.name}
                                                    </span>
                                                    {f.exists && (
                                                        <>
                                                            <span className="text sm text-gray">{humanizeBytes(f.size_bytes)}</span>
                                                            <span className="text sm text-gray">{formatTimestamp(f.modified_timestamp)}</span>
                                                        </>
                                                    )}
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </StageRow>
                            ))}
                        </div>
                    )}
                </div>
            )}
        </div>
    );
};
