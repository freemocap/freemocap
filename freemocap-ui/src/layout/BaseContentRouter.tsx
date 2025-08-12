// skellycam-ui/src/layout/BaseContent.tsx
import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import WelcomePage from "@/layout/pages/WelcomePage";
import {CamerasPage} from "@/layout/pages/CamerasPage";
import VideosPage from "@/layout/pages/VideosPage";

export const BaseContentRouter: React.FC = () => {
    return (
        <Routes>
            {/*<Route path="/" element={<WelcomePage />} />*/}
            <Route path="/" element={<CamerasPage />} />
            <Route path="/videos" element={<VideosPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
    );
};
