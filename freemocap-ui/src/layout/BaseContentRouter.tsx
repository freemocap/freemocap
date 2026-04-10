import React from 'react';
import {Navigate, Route, Routes} from 'react-router-dom';
import {ViewportPage} from "@/pages/ViewportPage";
import PlaybackPage from "@/pages/PlaybackPage";
import WelcomePage from "@/pages/WelcomePage";

export const BaseContentRouter: React.FC = () => {
    return (
        <Routes>
            <Route path="/" element={<WelcomePage />} />
            <Route path="/playback" element={<PlaybackPage/>}/>
            <Route path="/viewport" element={<ViewportPage />} />
            <Route path="*" element={<Navigate to="/" replace/>}/>
        </Routes>
    );
};
