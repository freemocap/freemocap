import { createContext, useContext } from "react";

/**
 * Which saved result and sensor group a recording's viewport is showing, plus the
 * actions to change them. Provided by RecordingPlaybackProvider and rendered in the
 * viewport panel; absent (null) for the live stream.
 */
export interface RecordingSelection {
    runIds: readonly number[];
    runId: number | null;
    selectRun: (runId: number) => void;
    groups: readonly string[];
    group: string;
    selectGroup: (group: string) => void;
    /** Units of the landmark data, as declared by the recording (e.g. "mm"). */
    units: string | null;
    reload: () => void;
}

export const RecordingSelectionContext = createContext<RecordingSelection | null>(null);

export function useRecordingSelection(): RecordingSelection | null {
    return useContext(RecordingSelectionContext);
}
