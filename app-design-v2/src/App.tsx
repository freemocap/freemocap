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
          {/* Left + Middle grouped */}
          <div className="main-left">
            <div className="left-panel"></div>
            <div className="middle-section">
              <div className="middle-top"></div>
              <div className="middle-bottom"></div>
            </div>
          </div>

          {/* Right Section */}
          <div className="right-section">
            <div className="right-top"></div>
            <div className="right-bottom"></div>
          </div>
        </div>
      </div>

      {/* Bottom Section */}
      <div className="bottom-section">
        <div className="bottom-top-bar"></div>
        <div className="bottom-inner"></div>
      </div>
    </div>
  );
}

export default App;