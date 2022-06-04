import {SetupAndPreviewCamera} from "../prod/SetupAndPreviewCamera";
import {Button, Typography} from "@mui/material";
import {Box} from "@mui/system";
import {useWizard, Wizard} from "react-use-wizard";
import axios from "axios";

interface Props {
  webcamIds: string[];
}

export const SessionWizard = (props: Props) => {
  // generate steps within the step wizard
  const {webcamIds} = props

  return (
    <Wizard>
      {webcamIds.map(webcamId => {
        return <CamStep webcamId={webcamId} />
      })}
      {/*<IMShowPreviewCamera />*/}
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
//
// interface PreviewCamera {}
// export const IMShowPreviewCamera = () => {
//   const {handleStep, previousStep, nextStep, stepCount, isLastStep} = useWizard();
//   useAsync(async () => {
//     await axios.post('http://localhost:8080/camera/cv2_imshow_one_camera', {
//       session_id
//     });
//   }, []);
//   return (
//     <Box>
//       <Typography>External Windows should pop up showing the images from your webcams all together.</Typography>
//       <Typography>If you are ready to record, and the configuration seems correct, please continue.</Typography>
//       <Typography>If not, please go to the previous steps and change the configuration</Typography>
//       <Button onClick={previousStep}>No, I want to go back</Button>
//       <Button onClick={nextStep}>Yes, Im ready to record</Button>
//     </Box>
//   )
// }
