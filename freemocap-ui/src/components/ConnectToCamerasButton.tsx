import React from 'react';
import { Button } from '@mui/material';
import axios from 'axios';

export const ConnectToCamerasButton = () => {
    const handleDetectCameras = async () => {
        try {
            const response = await axios.get('http://localhost:8005/skellycam/cameras/connect/detect');
            console.log('Response:', response.data);
        } catch (error) {
            console.error('Error detecting cameras:', error);
        }
    };

    return (
        <Button variant="contained" onClick={handleDetectCameras}>
            Detect/Connect to Cameras
        </Button>
    );
};
