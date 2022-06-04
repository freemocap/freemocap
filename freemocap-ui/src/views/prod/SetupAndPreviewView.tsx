import {Box} from "@mui/material";
import React, {useState} from "react";
import {useAsync} from "react-use";
import axios from "axios";
import {SessionWizard} from "../sessionWizard/SessionWizard";

export const SetupAndPreviewView = () => {
  const [webcamIds, setWebcamIds] = useState();

  useAsync(async () => {
    const response = await axios.get('http://localhost:8080/camera/detect');
    const webcamIds = response.data.cameras_found_list.map(x => x.webcam_id);
    setWebcamIds(webcamIds)
  }, [])

  if (!webcamIds) {
    // Small loading indicator
    return null;
  }

  return (
    <Box>
      <SessionWizard webcamIds={webcamIds} />
    </Box>
  )
}