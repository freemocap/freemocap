// skellycam-ui/src/layout/BaseContent.tsx
import React from 'react';
import {Navigate, Route, Routes} from 'react-router-dom';
import {CamerasPage} from "@/layout/pages/CamerasPage";
import {Viewport3dPage} from "@/layout/pages/Viewport3dPage";
import VideosPage from "@/layout/pages/VideosPage"
import ErrorBoundary from "@/components/ErrorBoundary";


export const BaseContentRouter: React.FC = () => {
    return (
        <ErrorBoundary>
            <Routes>
                {/*<Route path="/" element={<WelcomePage />} />*/}
                <Route path="/" element={<CamerasPage/>}/>
                <Route path="/viewport3d" element={<Viewport3dPage/>}/>
                <Route path="/videos" element={<VideosPage/>}/>
                <Route path="*" element={<Navigate to="/" replace/>}/>
            </Routes>
        </ErrorBoundary>
    );
};
