import { type FC, type ReactElement, type SetStateAction, useState } from "react";
import { SegmentedControl } from "@/components/primitives/Controls/SegmentedControlComponent.tsx";

export type InfoMode = "Logs" | "Recording info" | "File directory";

export interface BottomPanelProps {
    onInfoModeChange?: (mode: InfoMode) => void;
    logContent?: string;
    recordingInfo?: string;
    fileDirectory?: string;
}

interface SegmentedControlOption {
    label: string;
    value: InfoMode;
}

const DEFAULT_LOG_CONTENT: string = `\\Users\\andre\\freemocap_data\\logs_info_and_settings\\last_successful_calibration.toml.
[2024-01-18T23:14:32.0235][INFO ] [ProcessID: 1192, ThreadID: 22204]
[freemocap.gui.qt.utilities.update_most_recent_recording_toml:update_most_recent_recording_toml():16]:::
Saving most recent recording path C:
\\Users\\andre\\freemocap_data\\recording sessions\\freemocap_sample_data
to toml file:
C:\\Users\\andre\\freemocap_data\\logs_info_and_settings\\most_recent_recording.toml.
[2024-01-18T23:14:32.0251][INFO ] [ProcessID: 1192, ThreadID: 22204]
[freemocap.data_layer.recording_models.recording_info_model:get_number_of_mp4s_in_synched_videos_directory():238]
::: Number of \`.mp4''s in C:
\\Users\\andre\\freemocap_data\\recording_sessions\\freemocap_sample_data\\synchronized_videos:
3.0.`;

export const BottomPanel: FC<BottomPanelProps> = ({
                                                      onInfoModeChange,
                                                      logContent = DEFAULT_LOG_CONTENT,
                                                      recordingInfo = "Recording information will be displayed here...",
                                                      fileDirectory = "File directory information will be displayed here...",
                                                  }): ReactElement => {
    const [infoMode, setInfoMode] = useState<InfoMode>("Logs");

    const segmentedOptions: SegmentedControlOption[] = [
        { label: "Logs", value: "Logs" },
        { label: "Recording info", value: "Recording info" },
        { label: "File directory", value: "File directory" },
    ];

    const handleInfoModeChange = (selected: SetStateAction<string>): void => {
        const newMode = typeof selected === 'function'
            ? selected(infoMode)
            : selected;

        const validatedMode = newMode as InfoMode;
        setInfoMode(validatedMode);
        console.log("User selected info mode:", validatedMode);

        if (onInfoModeChange) {
            onInfoModeChange(validatedMode);
        }
    };

    const renderContent = (): ReactElement => {
        const contentMap: Record<InfoMode, string> = {
            "Logs": logContent,
            "Recording info": recordingInfo,
            "File directory": fileDirectory,
        };

        const content: string = contentMap[infoMode] || "";

        return (
            <p className="text md text-left">
                {content}
            </p>
        );
    };

    const containerClassName: string = "gap-2 overflow-hidden bottom-info-container bg-middark border-mid-black h-100 p-1 border-1 border-black br-2 flex flex-col";
    const headerClassName: string = "info-header-control h-25 bg-middark";
    const contentClassName: string = "overflow-y info-container flex flex-col flex-1 br-2 p-1 gap-1";

    return (
        <div className={containerClassName}>
            <div className={headerClassName}>
                <SegmentedControl
                    options={segmentedOptions}
                    size="sm"
                    value={infoMode}
                    onChange={handleInfoModeChange}
                />
            </div>

            <div className={contentClassName}>
                {renderContent()}
            </div>
        </div>
    );
};
