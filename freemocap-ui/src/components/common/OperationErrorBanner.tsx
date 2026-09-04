import React from "react";
import { useAppDispatch, useAppSelector } from "@/store";
import IconButton from "@/components/ui-components/IconButton";
import { selectRecordingError, recordingErrorCleared } from "@/store/slices/recording/recording-slice";
import { selectCalibrationError, calibrationErrorCleared } from "@/store/slices/calibration/calibration-slice";
import { selectMocapError, mocapErrorCleared } from "@/store/slices/mocap/mocap-slice";
import { selectPipelineError, pipelineErrorCleared } from "@/store/slices/realtime";

/**
 * Single place where a failed operation request surfaces to the user.
 *
 * The UI never blocks a well-formed request on its own guess of server state — it
 * forms the request, sends it, and shows whatever the server says here. Each slice
 * records the failure of its last operation in `error`; this banner renders every
 * one that is set and lets the user dismiss it.
 */
export const OperationErrorBanner: React.FC = () => {
  const dispatch = useAppDispatch();

  const entries = [
    { label: "Recording", error: useAppSelector(selectRecordingError), clear: recordingErrorCleared },
    { label: "Calibration", error: useAppSelector(selectCalibrationError), clear: calibrationErrorCleared },
    { label: "Motion capture", error: useAppSelector(selectMocapError), clear: mocapErrorCleared },
    { label: "Realtime pipeline", error: useAppSelector(selectPipelineError), clear: pipelineErrorCleared },
  ].filter((e): e is typeof e & { error: string } => Boolean(e.error));

  if (entries.length === 0) return null;

  return (
    <div className="operation-error-banner flex flex-col gap-1 w-full" role="alert">
      {entries.map(({ label, error, clear }) => (
        <div key={label} className="toast-notification error">
          <div className="flex flex-row items-center justify-content-space-between gap-1">
            <p className="text sm">
              <span className="text-bold">{label}:</span> {error}
            </p>
            <IconButton
              icon="clear-icon"
              iconSize="icon-size-12"
              onClick={() => dispatch(clear())}
              title="Dismiss"
            />
          </div>
        </div>
      ))}
    </div>
  );
};

export default OperationErrorBanner;
