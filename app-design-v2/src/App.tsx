import { Provider } from "react-redux";
import { store } from "./store";
import React, { useState } from "react";
import "./App.css";

import Header from "./components/panels/HeaderPanel";
import SplashModal from "./components/SplashModal";
import InfoPanel from "./components/panels/InfoPanel";
import ModePanel from "./components/panels/ModePanel";

function App() {
  const [showSplash, setShowSplash] = useState(true);

  return (
    <div className="app-content bg-middark flex flex-col p-1 gap-1 h-full overflow-hidden">
      {/* splash modal */}
      {showSplash && <SplashModal onClose={() => setShowSplash(false)} />}

      {/* top-header */}
      <Header />

      {/* main-container moved to ModePanel */}
      <ModePanel />

      {/* bottom info-container */}
      <InfoPanel />
    </div>
  );
}

export default App;
