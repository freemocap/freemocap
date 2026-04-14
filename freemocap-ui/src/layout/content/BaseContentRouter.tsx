import React from 'react';
import {Navigate, Route, Routes} from 'react-router-dom';
import WelcomePage from "@/pages/WelcomePage";
import {StreamingViewPage} from "@/pages/StreamingViewPage";
import PlaybackPage from "@/pages/PlaybackPage";

export const BaseContentRouter: React.FC = () => {
    return (
        <Routes>
            <Route path="/" element={<Navigate to="/welcome" replace/>}/>
            <Route path="/welcome" element={<WelcomePage/>}/>
            <Route path="/streaming" element={<StreamingViewPage/>}/>
            <Route path="/playback" element={<PlaybackPage/>}/>
            <Route path="*" element={<Navigate to="/welcome" replace/>}/>
        </Routes>
    );
};
