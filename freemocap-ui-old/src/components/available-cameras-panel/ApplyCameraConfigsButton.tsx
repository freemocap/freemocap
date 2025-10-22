import React from 'react';
import { IconButton, Tooltip } from '@mui/material';
import SystemUpdateAltIcon from '@mui/icons-material/SystemUpdateAlt';
import { useAppDispatch } from '@/store/AppStateStore';
import { updateCameraConfigsThunk } from "@/store/thunks/update-camera-configs-thunk";

export const ApplyCameraConfigsButton: React.FC = () => {
    const dispatch = useAppDispatch();

    return (
        <Tooltip title="Apply camera configurations" arrow>
        <IconButton
            color="inherit"
      onClick={() => dispatch(updateCameraConfigsThunk())}
        >
      <SystemUpdateAltIcon />
        </IconButton>
        </Tooltip>
    );
};
