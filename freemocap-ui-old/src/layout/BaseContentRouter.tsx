import React from 'react';
import {Navigate, Route, Routes} from 'react-router-dom';
import {CamerasPage} from '@/pages/CamerasPage';
import VideosPage from '@/pages/VideosPage';
import WelcomePage from '@/pages/WelcomePage';
import {Viewport3dPage} from '@/pages/Viewport3dPage';
import {SettingsPage} from "@/pages/SettingsPage";

export const BaseContentRouter: React.FC = () => {
    return (
        <Routes>
            <Route path="/" element={<WelcomePage />} />
            <Route path="/cameras" element={<CamerasPage />} />
            <Route path="/videos" element={<VideosPage />} />
            <Route path="/viewport3d" element={<Viewport3dPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
    );
};
