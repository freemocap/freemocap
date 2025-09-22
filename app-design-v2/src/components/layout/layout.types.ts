// types/layout.types.ts

import { type ReactElement, type MouseEvent } from "react";

// ========================================
// Common Types
// ========================================

export type ButtonColor = "text-white" | "text-gray";
export type ButtonType = "primary" | "secondary" | "full-width" | "full-width primary" | "full-width secondary" | "full-width primary justify-center" | "full-width secondary justify-center";
export type IconPosition = "dropdown" | "externallink" | "";

// ========================================
// Header Types
// ========================================

export interface HeaderProps {
    onSupportClick?: () => void;
    onHelpItemClick?: (item: string) => void;
}

export interface HelpMenuItem {
    key: string;
    text: string;
    iconClass: string;
    rightSideIcon?: IconPosition;
}

// ========================================
// MainContentPanel Types
// ========================================

export type StreamState = "disconnected" | "connecting" | "connected";
export type AppMode = "Capture Live" | "Post-process";

export interface MainContentPanelProps {
    onModeChange?: (mode: string) => void;
    onStreamStateChange?: (state: string) => void;
}

export interface StreamConfig {
    text: string;
    iconClass: string;
    rightSideIcon: string;
    extraClasses: string;
}

export interface ToggleButtonConfig {
    state: StreamState;
    connectConfig: StreamConfig;
    connectingConfig: StreamConfig;
    connectedConfig: StreamConfig;
    textColor: ButtonColor;
    onConnect: () => void;
    onDisconnect: () => void;
}

// ========================================
// SidePanel Types
// ========================================

export interface SidePanelSettings {
    skipCalibration: boolean;
    isMultiprocessing: boolean;
    maxCoreCount: boolean;
}

export interface SidePanelProps {
    onCalibrateClick?: () => void;
    onRecordClick?: () => void;
    onSettingsChange?: (settings: SidePanelSettings) => void;
}

export interface ToggleConfig {
    text: string;
    className?: string;
    iconClass?: string;
    defaultState?: boolean;
    isToggled?: boolean;
    onToggle?: (value: boolean) => void;
    disabled?: boolean;
}

export interface RecordingSettings {
    autoProcessSave: boolean;
    generateJupyterNotebook: boolean;
    autoOpenBlender: boolean;
}

export interface ProcessingSettings {
    run2DImageTracking: boolean;
    multiprocessing: boolean;
    maxCoreCount: boolean;
    yoloCropMode: boolean;
}

// ========================================
// BottomPanel Types
// ========================================

export type InfoMode = "Logs" | "Recording info" | "File directory";

export interface BottomPanelProps {
    onInfoModeChange?: (mode: InfoMode) => void;
    logContent?: string;
    recordingInfo?: string;
    fileDirectory?: string;
}

export interface InfoContent {
    logs: string;
    recordingInfo: string;
    fileDirectory: string;
}

// ========================================
// AppLayout Types
// ========================================

export interface AppLayoutProps {
    initialShowSplash?: boolean;
    onGlobalStateChange?: (componentName: ComponentName, state: ComponentState) => void;
}

export type ComponentName = "Header" | "MainContentPanel" | "SidePanel" | "BottomPanel";

export type ComponentState =
    | { mode: AppMode }
    | { streamState: StreamState }
    | SidePanelSettings
    | { infoMode: InfoMode };

// ========================================
// Shared Component Props
// ========================================

export interface SegmentedControlOption<T = string> {
    label: string;
    value: T;
}

export interface ButtonProps {
    text: string;
    iconClass?: string;
    buttonType?: ButtonType;
    rightSideIcon?: IconPosition;
    textColor?: ButtonColor;
    onClick?: (event: MouseEvent<HTMLButtonElement>) => void;
    disabled?: boolean;
}

export interface DropdownButtonProps {
    containerClassName?: string;
    buttonProps: ButtonProps;
    dropdownItems: ReactElement[];
}

// ========================================
// Utility Types
// ========================================

export type DeepPartial<T> = {
    [P in keyof T]?: T[P] extends object ? DeepPartial<T[P]> : T[P];
};

export type Nullable<T> = T | null;
export type Optional<T> = T | undefined;

// ========================================
// Event Handler Types
// ========================================

export type VoidHandler = () => void;
export type StringHandler = (value: string) => void;
export type BooleanHandler = (value: boolean) => void;
export type SettingsHandler = (settings: SidePanelSettings) => void;
export type InfoModeHandler = (mode: InfoMode) => void;

// ========================================
// Constants
// ========================================

export const DEFAULT_STREAM_STATE: StreamState = "disconnected";
export const DEFAULT_APP_MODE: AppMode = "Capture Live";
export const DEFAULT_INFO_MODE: InfoMode = "Logs";

export const DEFAULT_SIDE_PANEL_SETTINGS: SidePanelSettings = {
    skipCalibration: true,
    isMultiprocessing: true,
    maxCoreCount: false,
};

export const DEFAULT_RECORDING_SETTINGS: RecordingSettings = {
    autoProcessSave: false,
    generateJupyterNotebook: false,
    autoOpenBlender: true,
};

export const DEFAULT_PROCESSING_SETTINGS: ProcessingSettings = {
    run2DImageTracking: false,
    multiprocessing: true,
    maxCoreCount: false,
    yoloCropMode: true,
};
