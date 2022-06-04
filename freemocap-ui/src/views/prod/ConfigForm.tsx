import {Typography, TextField, Button} from "@mui/material"
import {Box} from "@mui/system";
import {default as NumberFormat} from 'react-number-format';

const ExposureNumberField = () => {
  // TODO: -13 -> -1 (inclusive)
  return (
    <NumberFormat customInput={TextField} />
  );
}

export const ConfigForm = () => {
  return (
    <Box>

      <Box>
        <Typography>Exposure</Typography>
        <ExposureNumberField />
      </Box>

      <Box>
        <Typography>Resolution Width</Typography>
        <NumberFormat customInput={TextField} />

        <Typography>Resolution Height</Typography>
        <NumberFormat customInput={TextField} />
      </Box>

      <Box>
        <Typography>Image Rotation Degree</Typography>
        <NumberFormat customInput={TextField} />
      </Box>

      <Button>Save Camera Settings</Button>
    </Box>
  )
}