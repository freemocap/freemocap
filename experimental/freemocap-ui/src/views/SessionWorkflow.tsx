import React from 'react';
import {IconButton} from "@mui/material";
import {Box} from "@mui/system";
import AddRoundedIcon from '@mui/icons-material/AddRounded';
import {useNavigate} from "react-router";
import axios from "axios";

interface SessionResponse {
  session_id: string
  session_path: string
}

export const SessionWorkflow = () => {
  const navigate = useNavigate();
  const [IconButtonContainer] = [Box];

  const createSession = async () => {
    const response = await axios.post('http://localhost:8080/session/create/', {})
    const sessionResponse = response.data as SessionResponse;
    return sessionResponse;
  }
  return (
    <Box>
      <IconButtonContainer
        sx={{
          cursor: 'pointer'
        }}
        display={'flex'} flexDirection={'row'} alignItems={'center'} onClick={async () => {
        const sessionResponse = await createSession();
        const sessionId = sessionResponse.session_id;
        navigate(`/session/setup_and_preview/${sessionId}`)
      }}>
        <IconButton>
          <AddRoundedIcon />
        </IconButton>
        Create New Session
      </IconButtonContainer>

    </Box>
  )
}