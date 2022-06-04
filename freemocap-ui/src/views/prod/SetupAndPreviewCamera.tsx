import {useFrameCapture} from "../../hooks/use-frame-capture";
import {CaptureType} from "../../services/frame-capture";
import {Box, Button} from "@mui/material";
import React from "react";
import {ConfigForm} from "./ConfigForm";

// So what do we need?

// We need to know what all the cameras are ahead of time, so that we can tell the UI
// what is possible to connect to.

// SetupAndPreview View will run through that list of available cameras, and display it to the user.

// Finally, We'll include form inputs so that users can select configuration on screen, and submit their results
// for freemocap (api) to save (prolly to disk).

interface Props {
  camId: string
}

export const SetupAndPreviewCamera = (props: Props) => {
  const { camId } = props;
  const [frameCapture, data] = useFrameCapture(camId, CaptureType.Preview);
  if (!data) {
    return null;
  }

  return (
    <Box>
      <Box display={'flex'} flexDirection={'column'} width={400}>
        <Button>Preview in CV2</Button>
        {!frameCapture.isConnectionClosed && <img src={frameCapture.current_data_url} alt={"video capture"} />}
      </Box>
      <ConfigForm />
    </Box>
  )
}