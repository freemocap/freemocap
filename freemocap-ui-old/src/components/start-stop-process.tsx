import {Box, Button} from "@mui/material"
import React, {useEffect, useState} from "react"
import {RecorderManager, StreamByDeviceId} from "../services/recorder";

interface Props {
  streams?: StreamByDeviceId;
}

export const StartStopProcess = (props: Props) => {
  const [manager, setManager] = useState<RecorderManager>();
  useEffect(() => {
    if (!props.streams) { return; }
    const manager = new RecorderManager(props.streams);
    manager.registerDataHandler();
    setManager(manager);
  }, [props.streams]);


  return (
    <Box display={'flex'}>

      <Box mr={2}>
        <Button variant={'contained'} onClick={manager?.start}>Start Capture</Button>
      </Box>

      <Box mr={2}>
        <Button variant={'contained'} onClick={manager?.stop}>Stop Capture</Button>
      </Box>

      <Box mr={2}>
        <Button variant={'contained'} onClick={manager?.process}>Process Recording</Button>
      </Box>
    </Box>

  )
}