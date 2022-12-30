import {useFrameCapture} from "../../hooks/use-frame-capture";
import {CaptureType} from "../../services/frame-capture";
import {Box, Button} from "@mui/material";
import React from "react";
import {ConfigForm} from "./ConfigForm";

interface Props {
  webcamId: string;
  onSubmit: () => void;
}

export const SetupAndPreviewCamera = (props: Props) => {
  const { webcamId, onSubmit } = props;
  const [frameCapture, data] = useFrameCapture(webcamId, CaptureType.Preview);
  if (!data) {
    return null;
  }

  return (
    <Box>
      <Box display={'flex'} flexDirection={'column'} width={400}>
        <Button>Preview in CV2</Button>
        {!frameCapture.isConnectionClosed && <img src={data} alt={"video start"} />}
      </Box>
      <ConfigForm onSubmit={onSubmit}/>
    </Box>
  )
}