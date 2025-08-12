import {createAsyncThunk} from '@reduxjs/toolkit';



export const closeCameras = createAsyncThunk(
    'cameras/close',
    async () => {
        console.log(`Closing cameras...`);
        try {
            const closeCamerasURL = 'http://localhost:8006/skellycam/camera/group/close/all';


            console.log(`Sending close request to ${closeCamerasURL}`);
            const response = await fetch(closeCamerasURL, {
                method: 'DELETE',


            });

            if (response.ok) {
                console.log('Cameras closed successfully');
            } else {
                throw new Error(`Failed to close cameras: ${response.statusText}`);
            }
        } catch (error) {
            console.error('Recording start failed:', error);
            throw error;
        }
    }
);
