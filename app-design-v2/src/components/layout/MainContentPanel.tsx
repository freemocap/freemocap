import { type FC, type ReactElement, type SetStateAction, useState } from "react";
import { SegmentedControl } from "@/components/primitives/Controls/SegmentedControlComponent.tsx";
import {ConnectionToggleButton} from "@/components/features/ConnectionDropdown/ConnectionToggleButton.tsx";

export interface MainContentPanelProps {
    onModeChange?: (mode: string) => void;
    onStreamStateChange?: (state: string) => void;
}

export type AppMode = "Capture Live" | "Post-process";

interface SegmentedControlOption {
    label: string;
    value: string;
}

export const MainContentPanel: FC<MainContentPanelProps> = ({
                                                                onModeChange,
                                                            }): ReactElement => {
    const [mode, setMode] = useState<AppMode>("Capture Live");

    const modeOptions: SegmentedControlOption[] = [
        { label: "Capture Live", value: "Capture Live" },
        { label: "Post-process", value: "Post-process" },
    ];

    const handleModeChange = (selected: SetStateAction<string>): void => {
        const newMode = typeof selected === 'function'
            ? selected(mode)
            : selected;

        setMode(newMode as AppMode);
        console.log("User selected mode:", newMode);

        if (onModeChange) {
            onModeChange(newMode);
        }
    };



    const renderVideoTiles = (): ReactElement[] => {
        const tileCount: number = 6;
        return Array.from({ length: tileCount }, (_, index: number) => (
            <div
                key={`video-tile-${index}`}
                className="video-tile size-1 bg-middark br-2 empty"
            />
        ));
    };

    return (
        <div className="mode-container flex-5 br-2 bg-darkgray border-mid-black border-1 .bg-darkgray overflow-hidden flex flex-col flex-1 gap-1 p-1">
            <div className="flex flex-row header-tool-bar br-2 gap-4">
                <SegmentedControl
                    options={modeOptions}
                    size="md"
                    value={mode}
                    onChange={handleModeChange}
                />
                <div className="active-tools-header br-1-1 gap-1 p-1 flex">
                    <ConnectionToggleButton/>
                </div>
            </div>

            <div className="visualize-container overflow-y flex gap-2 flex-3 flex-start">
                <div className="video-container flex flex-row flex-wrap gap-2 flex-1 flex-start">
                    {renderVideoTiles()}
                </div>
            </div>
        </div>
    );
};
