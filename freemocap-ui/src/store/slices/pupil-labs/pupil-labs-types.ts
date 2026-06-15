/** State shape for the Pupil Labs Redux slice. */
export interface PupilLabsState {
    isConnected: boolean;
    isConnecting: boolean;
    isDisconnecting: boolean;
    isRecording: boolean;
    error: string | null;
}
