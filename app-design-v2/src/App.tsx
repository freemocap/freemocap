import {Provider} from 'react-redux';
import AppLayout from "./components/layout/AppLayout.tsx";
import {store} from "./store";
<<<<<<< HEAD
import { useState, useEffect } from "react";
import reactLogo from "./assets/react.svg";
import viteLogo from "/vite.svg";
import React from "react";
import "./App.css";
import { ButtonSm, DropdownButton } from "./components/primitives/Buttons/ButtonSm";
// import { DropdownButton } from "./components/composites/DropdownButton";
import SplashModal from "./components/SplashModal"; // imported modal
import {
  SegmentedControl,
  // ToggleComponent,
  // DropdownButton,
  ToggleButtonComponent,
  ConnectionDropdown,
  StandaloneToggleExample,
} from "./components/uicomponents";
=======
>>>>>>> parent of dc3ba20b (bringing back the original codebase)

function App() {
    return (
        <Provider store={store}>
            <AppLayout />
        </Provider>
    );
}

export default App;
