import {useFrameCapture} from "../../hooks/use-frame-capture";
import {CaptureType} from "../../services/frame-capture";
import {Box} from "@mui/material";
import React from "react";

// So what do we need?

// We need to know what all the cameras are ahead of time, so that we can tell the UI
// what is possible to connect to.

// SetupAndPreview View will run through that list of available cameras, and display it to the user.

// Finally, We'll include form inputs so that users can select configuration on screen, and submit their results
// for freemocap (api) to save (prolly to disk).

export const SetupAndPreview = () => {
  const [frameCapture, data] = useFrameCapture("0", CaptureType.BoardDetection);
  if (!data) {
    return null;
  }

  return (
    <Box>
      {!frameCapture.isConnectionClosed && <img src={frameCapture.current_data_url} alt={"video capture"} />}
    </Box>
  )
}