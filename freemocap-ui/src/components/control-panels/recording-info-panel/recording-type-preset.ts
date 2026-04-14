export type RecordingTypePreset = "none" | "calibration" | "mocap";

export const RECORDING_TYPE_OPTIONS: { value: RecordingTypePreset; label: string }[] = [
    {value: "none", label: "None"},
    {value: "calibration", label: "Cal"},
    {value: "mocap", label: "Mocap"},
];
