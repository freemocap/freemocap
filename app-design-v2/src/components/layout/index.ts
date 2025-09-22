// components/layout/index.ts

// Export all layout components
export { default as AppLayout } from "./AppLayout.tsx";
export { Header } from "./Header.tsx";
export { MainContentPanel } from "./MainContentPanel.tsx";
export { SidePanel } from "./SidePanel.tsx";
export { BottomPanel } from "./BottomPanel.tsx";

// Export all types
export type {
    // Common Types
    ButtonColor,
    ButtonType,
    IconPosition,

    // Header Types
    HeaderProps,
    HelpMenuItem,

    // MainContentPanel Types
    StreamState,
    AppMode,
    MainContentPanelProps,
    StreamConfig,
    ToggleButtonConfig,

    // SidePanel Types
    SidePanelSettings,
    SidePanelProps,
    ToggleConfig,
    RecordingSettings,
    ProcessingSettings,

    // BottomPanel Types
    InfoMode,
    BottomPanelProps,
    InfoContent,

    // AppLayout Types
    AppLayoutProps,
    ComponentName,
    ComponentState,

    // Shared Component Props
    SegmentedControlOption,
    ButtonProps,
    DropdownButtonProps,

    // Utility Types
    DeepPartial,
    Nullable,
    Optional,

    // Event Handler Types
    VoidHandler,
    StringHandler,
    BooleanHandler,
    SettingsHandler,
    InfoModeHandler,
} from "./layout.types.ts";

// Export constants
export {
    DEFAULT_STREAM_STATE,
    DEFAULT_APP_MODE,
    DEFAULT_INFO_MODE,
    DEFAULT_SIDE_PANEL_SETTINGS,
    DEFAULT_RECORDING_SETTINGS,
    DEFAULT_PROCESSING_SETTINGS,
} from "./layout.types.ts";
