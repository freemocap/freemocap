import React from 'react';
import {Route, Routes} from "react-router-dom";
import {WebcamStreamCapture} from "../../views/Capture";
import {ConfigView} from "../../views/Config";
import {SetupAndPreviewView} from "../../views/prod/SetupAndPreviewView";
import {SessionWorkflow} from "../../views/SessionWorkflow";


export const Router = () => {
  return (
    <Routes>
      <Route path={'/'} element={<React.Fragment />} />
      <Route path={'/session'} element={<SessionWorkflow />} />
      <Route path={'/session/setup_and_preview/:sessionId'} element={<SetupAndPreviewView />} />
      <Route path={'/show_cameras'} element={<WebcamStreamCapture />} />
      <Route path={'/config'} element={<ConfigView />} />
    </Routes>
  )
}