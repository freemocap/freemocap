import {Box} from "@mui/material";
import React from "react";
import {useAsync} from "react-use";
import axios from "axios";
import {SetupAndPreviewCamera} from "./SetupAndPreviewCamera";

// So what do we need?

// We need to know what all the cameras are ahead of time, so that we can tell the UI
// what is possible to connect to.

// SetupAndPreview View will run through that list of available cameras, and display it to the user.

// Finally, We'll include form inputs so that users can select configuration on screen, and submit their results
// for freemocap (api) to save (prolly to disk).


export const SetupAndPreviewView = () => {
  const response = useAsync(async () => {
    const response = await axios.get('http://localhost:8080/camera/detect');
    const port_numbers = response.data.cameras_found_list.map(x => x.webcam_id);
    return <SetupAndPreviewCamera camId={port_numbers[0]} />
    // return port_numbers.map(x => {
    //   return <SetupAndPreviewCamera camId={x} />
    // })
  }, []);

  if (response.loading) {
    return null;
  }
  const r = response.value;
  return (
    <Box>
      {r}
    </Box>
  )
}