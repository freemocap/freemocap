import React from 'react';
import {Navigate, Route, Routes} from 'react-router-dom';
import {CamerasPage} from "@/pages/CamerasPage";
import PlaybackPage from "@/pages/PlaybackPage";

export const BaseContentRouter: React.FC = () => {
    return (
        <Routes>
            <Route path="/cameras" element={<CamerasPage/>}/>
            <Route path="/playback" element={<PlaybackPage/>}/>
            <Route path="*" element={<Navigate to="/cameras" replace/>}/>
        </Routes>
    );
};
