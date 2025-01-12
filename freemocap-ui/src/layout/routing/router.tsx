import React from 'react';
import {Route, Routes} from "react-router-dom";
import {ConfigView} from "@/views/Config";
import {BrowserCamerasView} from "@/views/BrowserCamerasView";
import {PythonToJsTest} from "@/views/PythonToJsTest";
import {PythonCamerasView} from "@/views/PythonCamerasView";
import {DefaultView} from "@/views/Default";
import WebsocketConnectionStatus from "@/components/ui-components/WebsocketConnectionStatus";
import {Viewport3d} from "@/views/Viewport3d";

export const Router = () => {
    return (
        <Routes>
            <Route path={'/'} element={<Viewport3d />} />
            {/*<Route path={'/default'} element={<DefaultView/>}/>*/}
            <Route path={'/config'} element={<ConfigView/>}/>
            {/*<Route path={'/jontestplayground'} element={<BrowserCamerasView/>}/>*/}
            {/*<Route path={'/pythonToJs'} element={<PythonToJsTest/>}/>*/}
            <Route path={'/show_cameras'} element={<PythonCamerasView/>}/>
            <Route path={'/viewport3d'} element={<Viewport3d />} />
            <Route path={'/websocketConnection'} element={<WebsocketConnectionStatus/>}/>
        </Routes>
    )
}
