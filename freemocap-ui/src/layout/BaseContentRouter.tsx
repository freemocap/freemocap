import React from 'react';
import {Navigate, Route, Routes} from 'react-router-dom';
import {CamerasPage} from "@/pages/CamerasPage";
import PlaybackPage from "@/pages/PlaybackPage";
import WelcomePage from "@/pages/WelcomePage";
// import { SettingsPage } from "@/pages/SettingsPage";
import {Viewport3dPage} from "@/pages/Viewport3dPage";

export const BaseContentRouter: React.FC = () => {
    return (
        <Routes>
            <Route path="/" element={<WelcomePage />} />
            <Route path="/cameras" element={<CamerasPage/>}/>
            <Route path="/playback" element={<PlaybackPage/>}/>
            <Route path="/viewport3d" element={<Viewport3dPage />} />
            {/*<Route path="/settings" element={<SettingsPage/>}/>*/}
            <Route path="*" element={<Navigate to="/" replace/>}/>
        </Routes>
    );
};
