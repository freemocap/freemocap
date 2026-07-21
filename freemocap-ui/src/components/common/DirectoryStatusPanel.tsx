import React from "react";
import IconButton from "@/components/ui-components/IconButton";

export interface DirectoryStatus {
    exists: boolean;
    hasVideos: boolean;
    hasSynchronizedVideos: boolean;
    errorMessage?: string | null;
    tomlPath?: string | null;
}

export interface DirectoryStatusPanelProps {
    title: string;
    tomlLabel: string;
    directoryInfo: DirectoryStatus | null;
    onRefresh?: () => void;
    refreshDisabled?: boolean;
    isRefreshing?: boolean;
    status?: "ok" | "bad" | "none";
}

const StatusChip: React.FC<{ label: string; ok: boolean }> = ({ label, ok }) => (
    <span className={`tag text sm flex flex-row items-center gap-1 ${ok ? '' : 'text-gray'}`}>
        <span className={`icon icon-size-12 ${ok ? 'upToDate-icon' : 'close-icon'}`} />
        {label}
    </span>
);

export const DirectoryStatusPanel: React.FC<DirectoryStatusPanelProps> = ({
    title,
    tomlLabel,
    directoryInfo,
    onRefresh,
    refreshDisabled = false,
    isRefreshing = false,
    status = "none",
}) => {
    if (!directoryInfo) return null;

    const borderStyle = status === "ok"
        ? '2px solid #00e5ff44'
        : status === "bad"
        ? '2px solid var(--color-danger)'
        : '2px solid var(--color-border-muted)';

    return (
        <div className="p-2 br-1 flex flex-col gap-1" style={{ border: borderStyle }}>
            {/* Header row */}
            <div className="flex flex-row items-center justify-content-space-between">
                <div className="flex flex-row items-center gap-1">
                    <span className="icon icon-size-20" style={{ backgroundImage: 'url("data:image/svg+xml,%3csvg width=\'16\' height=\'16\' viewBox=\'0 0 16 16\' fill=\'none\' xmlns=\'http://www.w3.org/2000/svg\'%3e%3ccircle cx=\'8\' cy=\'8\' r=\'6\' stroke=\'%232ba4ff\' stroke-width=\'1.5\'/%3e%3cpath d=\'M8 7v4M8 5.5v.5\' stroke=\'%232ba4ff\' stroke-width=\'1.5\' stroke-linecap=\'round\'/%3e%3c/svg%3e")' }} />
                    <span className="text sm text-gray">{title}</span>
                </div>
                {onRefresh && (
                    <IconButton
                        icon={isRefreshing ? "loader-icon" : "rotate-icon"}
                        onClick={onRefresh}
                        disabled={refreshDisabled}
                        title="Re-check folder"
                    />
                )}
            </div>

            {/* Status chips */}
            <div className="flex flex-row flex-wrap gap-1">
                <StatusChip label={directoryInfo.exists ? "Directory exists" : "Directory will be created"} ok={directoryInfo.exists} />
                <StatusChip label="Has videos" ok={directoryInfo.hasVideos} />
                <StatusChip label="Has synchronized_videos" ok={directoryInfo.hasSynchronizedVideos} />
                <StatusChip label={tomlLabel} ok={!!directoryInfo.tomlPath} />
            </div>

            {/* TOML path display */}
            {directoryInfo.tomlPath && (
                <div>
                    <p className="text sm text-gray">Found calibration file:</p>
                    <p className="text sm" style={{ fontFamily: 'monospace', color: 'var(--color-success)', wordBreak: 'break-all' }}>
                        {directoryInfo.tomlPath}
                    </p>
                </div>
            )}
        </div>
    );
};
