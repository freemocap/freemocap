import React, {useState} from "react";
import {useTranslation} from "react-i18next";

import {CameraConfigTreeSection} from "./CameraConfigTreeSection";
import {ROTATION_DEGREE_LABELS, RotationValue, useAppDispatch} from "@/store";
import {cameraRealtimeToggled, cameraSelectionToggled} from "@/store/slices/cameras/cameras-slice";
import {Camera} from "@/store/slices/cameras/cameras-types";

interface CameraTreeItemProps {
    camera: Camera;
    isExpanded?: boolean;
}

const getConfigSummary = (config: any): string[] => {
    const summary: string[] = [];

    if (!config) return summary;

    if (config.resolution?.width && config.resolution?.height) {
        summary.push(`${config.resolution.width}×${config.resolution.height}`);
    }

    if (config.framerate) {
        summary.push(`${parseFloat(config.framerate).toFixed(2)}fps`);
    }

    if (config.exposure !== undefined && config.exposure_mode === 'MANUAL') {
        summary.push(`E:${config.exposure}`);
    }

    if (config.pixel_format && config.pixel_format !== 'RGB') {
        summary.push(config.pixel_format);
    }

    if (config.rotation) {
        summary.push(ROTATION_DEGREE_LABELS[config.rotation as RotationValue]);
    }

    if (config.capture_fourcc) {
        summary.push(config.capture_fourcc);
    }

    return summary.filter(item => item);
};

const getStatusColor = (connectionStatus: string): string => {
    switch (connectionStatus) {
        case "connected":
            return 'var(--color-success)';
        case "available":
            return 'var(--color-info)';
        case "error":
            return 'var(--color-danger)';
        default:
            return 'var(--color-text-muted)';
    }
};

export const CameraTreeItem: React.FC<CameraTreeItemProps> = ({camera, isExpanded = false}) => {
    const dispatch = useAppDispatch();
    const {t} = useTranslation();
    const [expanded, setExpanded] = useState(isExpanded);

    const statusLabelMap: Record<string, string> = {
        connected: t('connected'),
        available: t('available'),
        error: t('errorsDetected'),
    };

    const handleToggleSelection = (e: React.MouseEvent): void => {
        e.stopPropagation();
        dispatch(cameraSelectionToggled(camera.id));
    };

    const handleToggleRealtime = (e: React.MouseEvent): void => {
        e.stopPropagation();
        dispatch(cameraRealtimeToggled(camera.id));
    };

    const configSummary = getConfigSummary(camera.desiredConfig);
    const showConfigSummary = !expanded && configSummary.length > 0;

    return (
        <div>
            <div
                className="flex flex-row items-center gap-1 p-1"
                style={{minHeight: 32, paddingRight: 8, cursor: 'pointer', userSelect: 'none'}}
                onClick={() => setExpanded((prev) => !prev)}
            >
                <span
                    className={`icon icon-size-20 ${expanded ? 'collapse-icon' : 'expand-icon'}`}
                    style={{transform: expanded ? 'rotate(0deg)' : 'rotate(-90deg)', flexShrink: 0}}
                />

                <button
                    className="button icon-button br-1"
                    onClick={handleToggleSelection}
                    title={camera.selected ? "In camera group" : "Not in camera group"}
                    style={{marginRight: 2, flexShrink: 0}}
                >
                    {camera.selected
                        ? <span className="icon check-circle-icon icon-size-20" style={{color: 'var(--color-info)'}} />
                        : <span className="icon radio-unchecked-icon icon-size-20" style={{color: 'var(--color-text-muted)'}} />
                    }
                </button>

                <button
                    className="button icon-button br-1"
                    onClick={handleToggleRealtime}
                    disabled={!camera.selected}
                    title={camera.realtimeEnabled ? "In realtime pipeline" : "Not in realtime pipeline"}
                    style={{marginRight: 4, flexShrink: 0}}
                >
                    {camera.realtimeEnabled
                        ? <span className="icon videocam-icon icon-size-20" style={{color: 'var(--color-info)'}} />
                        : <span className="icon videocam-outlined-icon icon-size-20" style={{color: 'var(--color-text-muted)'}} />
                    }
                </button>

                <div className="flex flex-row items-center flex-1 gap-1" style={{minWidth: 0}}>
                    <div style={{flexShrink: 0, overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: 200}}>
                        <span style={{fontSize: '0.75rem', color: 'var(--color-text-primary)', display: 'block', whiteSpace: 'nowrap'}}>
                            Camera {camera.index}
                        </span>
                        <span style={{fontSize: '0.6rem', color: 'var(--color-text-muted)', display: 'block', whiteSpace: 'nowrap'}}>
                            {camera.name} (id: {camera.id})
                        </span>
                    </div>

                    {showConfigSummary && (
                        <div className="flex flex-row items-center gap-1" style={{flexGrow: 1, minWidth: 0, overflow: 'hidden'}}>
                            <span className="icon settings-icon icon-size-12" style={{color: 'var(--color-text-muted)', flexShrink: 0}} />
                            <div className="flex flex-row gap-1" style={{flexWrap: 'wrap', overflow: 'hidden'}}>
                                {configSummary.slice(0, 5).map((item, index) => (
                                    <span
                                        key={index}
                                        className="tag text sm"
                                        style={{
                                            height: 10,
                                            fontSize: 8,
                                            padding: '0 6px',
                                            borderColor: 'var(--color-border-secondary)',
                                            color: 'var(--color-text-muted)',
                                        }}
                                    >
                                        {item}
                                    </span>
                                ))}
                            </div>
                        </div>
                    )}
                </div>

                <span
                    className="tag text sm"
                    style={{
                        marginLeft: 4,
                        flexShrink: 0,
                        backgroundColor: getStatusColor(camera.connectionStatus),
                        color: '#fff',
                        fontSize: 10,
                        height: 20,
                    }}
                >
                    {statusLabelMap[camera.connectionStatus] ?? camera.connectionStatus.toUpperCase()}
                </span>
            </div>

            {expanded && (
                <div style={{paddingLeft: 8}}>
                    <CameraConfigTreeSection camera={camera} />
                </div>
            )}
        </div>
    );
};
