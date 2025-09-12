import { useState } from 'react'
import reactLogo from './assets/react.svg'
import viteLogo from '/vite.svg'
import './App.css'

function App() {
  return (
    <div className="app-container">
      {/* Top Red Bar */}
      <div className="top-bar"></div>

      {/* Main Content Wrapper */}
      <div className="main-content">
        {/* Blue Header Bar */}
        <div className="header-bar"></div>

        <div className="content-body">
          {/* Left Large Black Panel */}
          <div className="left-panel"></div>

          {/* Middle Section with 2 Black Panels */}
          <div className="middle-section">
            <div className="top-box"></div>
            <div className="bottom-box"></div>
          </div>

          {/* Right Side Two Red Panels */}
          <div className="right-section">
            <div className="right-top"></div>
            <div className="right-bottom"></div>
          </div>
        </div>
      </div>

      {/* Bottom Section */}
      <div className="bottom-section">
        <div className="bottom-inner"></div>
      </div>
    </div>
  );
}

export default App;
