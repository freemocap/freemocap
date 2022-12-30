import {SetupAndPreviewCamera} from "../prod/SetupAndPreviewCamera";
import {Button, Typography} from "@mui/material";
import {Box} from "@mui/system";
import {useWizard, Wizard} from "react-use-wizard";
import axios from "axios";
import {useAsync} from "react-use";
import {useParams} from "react-router";

interface Props {
  webcamIds: string[];
}

export const SessionWizard = (props: Props) => {
  // generate steps within the step wizard
  const {webcamIds} = props
  const { sessionId } = useParams();
  return (
    <Wizard>
      {webcamIds.map(webcamId => {
        return <CamStep webcamId={webcamId} />
      })}
      <IMShowPreviewCamera sessionId={sessionId}/>
    </Wizard>
  )
}

interface CamStepProps {
  webcamId: string
}

export const CamStep = (props: CamStepProps) => {
  const {webcamId} = props
  const {handleStep, previousStep, nextStep, stepCount, isLastStep} = useWizard();

  return (
    <Box>
      <Typography>Step {stepCount}</Typography>
      <Typography>Camera {webcamId}</Typography>
      <SetupAndPreviewCamera webcamId={webcamId} onSubmit={nextStep} />
    </Box>
  )
}

interface PreviewCameraProps {
  sessionId: string | undefined
}

export const IMShowPreviewCamera = (props: PreviewCameraProps) => {
  const {handleStep, previousStep, nextStep, stepCount, isLastStep} = useWizard();
  useAsync(async () => {
    await axios.post('http://localhost:8080/camera/show_cameras', {
      session_id: props.sessionId
    });
  }, []);
  return (
    <Box>
      <Typography>External Windows should pop up showing the images from your webcams all together.</Typography>
      <Typography>If you are ready to record, and the configuration seems correct, please continue.</Typography>
      <Typography>If not, please go to the previous steps and change the configuration</Typography>
      <Button onClick={previousStep}>No, I want to go back</Button>
      <Button onClick={nextStep}>Yes, Im ready to calibrate</Button>
    </Box>
  )
}
