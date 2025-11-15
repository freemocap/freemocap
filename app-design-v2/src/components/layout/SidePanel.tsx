import { type FC, type ReactElement, useState, useEffect } from "react";
import { ButtonSm } from "@/components/primitives/Buttons/ButtonSm.tsx";
import { ToggleComponent } from "@/components/primitives/Toggles/ToggleComponent.tsx";

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

interface ToggleConfig {
    text: string;
    className?: string;
    iconClass?: string;
    defaultState?: boolean;
}

export const SidePanel: FC<SidePanelProps> = ({
                                                  onCalibrateClick,
                                                  onRecordClick,
                                                  onSettingsChange,
                                              }): ReactElement => {
    const [skipCalibration, setSkipCalibration] = useState<boolean>(true);
    const [isMultiprocessing, setIsMultiprocessing] = useState<boolean>(true);
    const [maxCoreCount, setMaxCoreCount] = useState<boolean>(false);

    // Effect to manage dependent toggle state
    useEffect((): void => {
        if (!isMultiprocessing) {
            setMaxCoreCount(false);
        }
    }, [isMultiprocessing]);

    // Notify parent of settings changes if callback provided
    useEffect((): void => {
        if (onSettingsChange) {
            const currentSettings: SidePanelSettings = {
                skipCalibration,
                isMultiprocessing,
                maxCoreCount,
            };
            onSettingsChange(currentSettings);
        }
    }, [skipCalibration, isMultiprocessing, maxCoreCount, onSettingsChange]);

    const handleCalibrateClick = (): void => {
        if (onCalibrateClick) {
            onCalibrateClick();
        } else {
            console.log("Calibrate clicked");
            // TODO: Add calibration logic
        }
    };

    const handleRecordClick = (): void => {
        if (onRecordClick) {
            onRecordClick();
        } else {
            console.log("Record clicked");
            // TODO: Add recording logic
        }
    };

    const recordContainerClassName: string = `flex flex-col record-container br-1 p-1 gap-1 bg-middark reveal ${
        skipCalibration ? "" : "disabled"
    }`;

    const maxCoreCountClassName: string = !isMultiprocessing ? "disabled" : "";

    const calibrationToggles: ToggleConfig[] = [
        { text: "Charuco size", className: "", iconClass: "" }
    ];

    const recordingToggles: ToggleConfig[] = [
        { text: "Auto process save", className: "", iconClass: "" },
        { text: "Generate jupyter notebook", className: "", iconClass: "" },
        { text: "Auto open Blender", className: "", iconClass: "", defaultState: true },
    ];

    const propertiesToggle: ToggleConfig[] = [
        { text: "Run 2d image tracking", className: "", iconClass: "" },
        { text: "Yolo crop mode", className: "", iconClass: "", defaultState: true },
    ];

    return (
        <div className="action-container flex-1 overflow-y bg-darkgray br-2 border-mid-black border-1 .bg-darkgray overflow-y min-w-200 max-w-350 flex flex-col gap-1 flex-1 p-1">
            <div className="subaction-container pos-sticky gap-1 z-1 top-0 flex flex-col">
                {/* Calibration Container */}
                <div className="flex flex-col calibrate-container br-1 p-1 gap-1 bg-middark">
                    {calibrationToggles.map((toggle: ToggleConfig, index: number) => (
                        <ToggleComponent
                            key={`calibration-toggle-${index}`}
                            text={toggle.text}
                            className={toggle.className}
                            iconClass={toggle.iconClass}
                        />
                    ))}
                    <ButtonSm
                        iconClass="calibrate-icon"
                        text="Calibrate"
                        buttonType="full-width secondary justify-center"
                        rightSideIcon=""
                        textColor="text-white"
                        onClick={handleCalibrateClick}
                    />
                    <ToggleComponent
                        text="Skip calibration"
                        className=""
                        iconClass=""
                        defaultToggelState={true}
                        isToggled={skipCalibration}
                        onToggle={setSkipCalibration}
                    />
                </div>

                {/* Recording Container */}
                <div className={recordContainerClassName}>
                    {recordingToggles.map((toggle: ToggleConfig, index: number) => (
                        <ToggleComponent
                            key={`recording-toggle-${index}`}
                            text={toggle.text}
                            className={toggle.className}
                            iconClass={toggle.iconClass}
                            defaultToggelState={toggle.defaultState}
                        />
                    ))}
                    <ButtonSm
                        iconClass="record-icon"
                        text="Record"
                        buttonType="full-width primary justify-center"
                        rightSideIcon=""
                        textColor="text-white"
                        onClick={handleRecordClick}
                    />
                    <div className="p-1 g-1">
                        <p className="text bg-md text-left">
                            Camera views may lag at higher settings. Try lowering the
                            resolution/reducing the number of cameras. fix is coming soon.
                        </p>
                    </div>
                </div>
            </div>

            {/* Properties Container */}
            <div className="subaction-container properties-container flex-1 br-1 p-1 gap-1 bg-darkgray">
                {propertiesToggle.map((toggle: ToggleConfig, index: number) => (
                    <ToggleComponent
                        key={`properties-toggle-${index}`}
                        text={toggle.text}
                        className={toggle.className}
                        iconClass={toggle.iconClass}
                        defaultToggelState={toggle.defaultState}
                    />
                ))}

                {/* Parent toggle */}
                <ToggleComponent
                    text="Multiprocessing"
                    defaultToggelState={true}
                    isToggled={isMultiprocessing}
                    onToggle={setIsMultiprocessing}
                />

                {/* Dependent toggle */}
                <ToggleComponent
                    text="Max core count"
                    iconClass="subcat-icon"
                    isToggled={maxCoreCount}
                    onToggle={setMaxCoreCount}
                    disabled={!isMultiprocessing}
                    className={maxCoreCountClassName}
                />
            </div>
        </div>
    );
};
