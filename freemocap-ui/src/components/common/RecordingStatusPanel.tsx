import React, { useState } from "react";
import { RecordingStatus } from "@/types/recording-status";
import IconButton from "@/components/ui-components/IconButton";

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
                <span className={`icon icon-size-20 ${complete ? 'upToDate-icon' : 'warning-icon'}`} />
                <span className="text md text-white flex-1">{label}</span>
                <span className="icon icon-size-20 arrowdown-icon" style={{ transform: open ? 'rotate(180deg)' : 'rotate(0deg)' }} />
            </div>
            {open && children && (
                <div className="px-2 pb-2">{children}</div>
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
                className="flex flex-row items-center gap-1 pl-2 p-2"
               
                onClick={() => setExpanded(v => !v)}
            >
                <span className="icon explainer-icon icon-size-20"/>
                <span className="text md text-gray flex-1">Recording folder</span>
                <span className={`tag text md ${summaryColor}`}>{summaryLabel}</span>
                {onRefresh && (
                    <IconButton
                        icon={isLoading ? "loader-icon" : "rotate-icon"}
                        onClick={(e) => { e.stopPropagation(); onRefresh(); }}
                        disabled={isLoading}
                        
                        tooltip={true}
                        tooltipPosition="pos-bottom-right"
                        tooltipText="Re-check folder"
                        
                    />
                )}
                <span className="icon icon-size-20 arrowdown-icon" style={{ transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)' }} />
            </div>

            {expanded && (
                <div className="flex flex-col gap-1 p-2">
                    {error && (
                        <div className="toast-notification error">
                            <p className="text md">{error}</p>
                        </div>
                    )}

                    {!folderExists && (
                        <div className="toast-notification">
                            <p className="text md text-warning">Recording folder does not exist yet. It will be created when you start recording.</p>
                            {recordingFolderPath && (
                                <p className="text md text-gray mt-1" style={{ fontFamily: 'monospace', wordBreak: 'break-all' }}>
                                    {recordingFolderPath}
                                </p>
                            )}
                        </div>
                    )}

                    {activeCalibrationTomlPath && (
                        <div>
                            <p className="text md text-gray">Active calibration TOML:</p>
                            <p className="text md" style={{ fontFamily: 'monospace', color: 'var(--color-success)', wordBreak: 'break-all' }}>
                                {activeCalibrationTomlPath}
                            </p>
                        </div>
                    )}

                    {!status && !isLoading && !error && (
                        <p className="text md text-gray">No status loaded.</p>
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
                                        <p className="text md text-gray">No files found.</p>
                                    ) : (
                                        <div className="flex flex-col gap-1">
                                            {stage.files.map((f) => (
                                                <div
                                                    key={f.path ?? f.name}
                                                    className="flex flex-row flex-wrap items-center gap-1"
                                                    style={{ fontFamily: 'monospace' }}
                                                >
                                                   <div className="flex flex-row gap-1">
                                                        <span className={`icon icon-size-12 ${f.exists ? 'upToDate-icon' : 'close-icon'}`} />
                                                        <span className={`text md flex-1 ${f.exists ? 'text-white' : 'text-gray'}`} style={{ wordBreak: 'break-all' }}>
                                                            {f.name}
                                                        </span>
                                                    </div>
                                                    {f.exists && (
                                                        <>
                                                             <div className="flex flex-row gap-1">
                                                                <span className="text md text-gray tag">{humanizeBytes(f.size_bytes)}</span>
                                                                <span className="text md text-gray tag">{formatTimestamp(f.modified_timestamp)}</span>
                                                            </div>
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
