import React from 'react';
import {Navigate, Route, Routes} from 'react-router-dom';
import WelcomePage from "@/pages/WelcomePage";

export const BaseContentRouter: React.FC = () => {
    return (
        <Routes>
            <Route path="/" element={<WelcomePage/>}/>
            {/* /streaming and /playback are handled by PageTabButtons (keep-mounted tabs) */}
            <Route path="/streaming" element={null}/>
            <Route path="/playback" element={null}/>
            <Route path="*" element={<Navigate to="/" replace/>}/>
        </Routes>
    );
};
