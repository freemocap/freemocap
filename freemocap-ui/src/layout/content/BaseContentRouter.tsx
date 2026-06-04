import React from 'react';
import {Navigate, Route, Routes} from 'react-router-dom';
import {StreamingViewPage} from "@/pages/StreamingViewPage";
import PlaybackPage from "@/pages/PlaybackPage";
import BrowserPage from "@/pages/BrowserPage";
import ActiveRecordingPage from "@/pages/ActiveRecordingPage";

export const BaseContentRouter: React.FC = () => {
    return (
        <Routes>
            <Route path="/" element={<Navigate to="/streaming" replace/>}/>
            <Route path="/streaming" element={<StreamingViewPage/>}/>
            <Route path="/browse" element={<BrowserPage/>}/>
            <Route path="/playback" element={<PlaybackPage/>}/>
            <Route path="/active-recording" element={<ActiveRecordingPage/>}/>
            <Route path="*" element={<Navigate to="/streaming" replace/>}/>
        </Routes>
    );
};
