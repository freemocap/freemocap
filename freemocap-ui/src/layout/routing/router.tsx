import React from 'react';
import {Route, Routes} from "react-router-dom";
import {ConfigView} from "@/views/Config";
import {BrowserCamerasView} from "@/views/BrowserCamerasView";
import {PythonToJsTest} from "@/views/PythonToJsTest";
import {PythonCamerasView} from "@/views/PythonCamerasView";
import {DefaultView} from "@/views/Default";
import WebsocketConnection from "@/views/WebsocketConnection";

export const Router = () => {
    return (
        <Routes>
            <Route path={'/'} element={<React.Fragment/>}/>
            <Route path={'/default'} element={<DefaultView/>}/>
            <Route path={'/config'} element={<ConfigView/>}/>
            <Route path={'/jontestplayground'} element={<BrowserCamerasView/>}/>
            <Route path={'/pythonToJs'} element={<PythonToJsTest/>}/>
            <Route path={'/show_cameras'} element={<PythonCamerasView/>}/>
            <Route path={'/websocketConnection'} element={<WebsocketConnection/>}/>
        </Routes>
    )
}
