# Freemocap Product Design v2

## 📁 Project Structure

```
app-design-v2/
├── public/
│ ├── 3d-asset/
│ │ └── freemocap-skelly.glb
│ ├── images/
│ │ ├── logo_name.svg
│ │ └── splashmodal_art.webp
│ └── vite.svg
└── src/
├── App.css
├── App.tsx
├── electron.d.ts
├── index.css
├── main.tsx
├── vite-env.d.ts
├── assets/
│ ├── react.svg
│ └── icons/
├── components/
│ ├── composites/
│ │ └── ConnectionDropdown.tsx # Composite component for the connection dropdown
│ ├── hooks/
│ │ └── useDraggableTooltips.tsx # Hook for draggable tooltips
│ ├── modals/
│ │ ├── CameraSettingsModal.tsx # Modal for camera settings
│ │ ├── FileDirectorySettingsModal.tsx # Modal for file directory settings
│ │ └── SplashModal.tsx # Splash screen modal
│ ├── modes/
│ │ ├── CaptureLive.tsx # Capture Live mode – allows users to record live motion capture
│ │ └── PostProcess.tsx # Post-Process mode – allows users to import and process recorded videos
│ ├── panels/
│ │ ├── HeaderPanel.tsx # Header panel – includes connection, help, and support options
│ │ ├── InfoPanel.tsx # Info panel – bottom panel in the layout
│ │ └── ModePanel.tsx # Mode panel – toggles between Capture Live and Post-Process modes
│ ├── ThreeD/
│ │ ├── CameraLogger.tsx # 3D camera logger – used for debugging camera positions during design
│ │ └── ThreeDScene.tsx # 3D scene component – loads the Skelly 3D environment for Post-Process mode
│ ├── tooltips/
│ │ └── ExcludedCameraTooltip.tsx # Tooltip for excluded cameras – appears when a camera feed is excluded from recording
│ └── uicomponents/
│ ├── ButtonCard.tsx # Large button component – used in the splash modal
│ ├── ButtonSm.tsx # Small button component – used widely across the app; supports optional icons
│ ├── Checkbox.tsx # Checkbox component
│ ├── ConnectionDropdown.tsx # Connection dropdown – used primarily in the header for WebSocket and Python connections
│ ├── DropdownButton.tsx # Dropdown button component – displays dropdown menus
│ ├── IconSegmentedControl.tsx # Icon segmented control – multi-state icon buttons; ideal for up to 3 states
│ ├── NameDropdownSelector.tsx # Name dropdown selector – used to edit strings such as file names
│ ├── SegmentedControl.tsx # Segmented control – used for mode switching; supports large (main) and small (secondary) variants
│ ├── states.ts # Manages connection dropdown state and props
│ ├── SubactionHeader.tsx # Subaction header – used in advanced settings to visually separate toggle/selector groups
│ ├── TextSelector.tsx # Text selector component
│ ├── ToggleButtonComponent.tsx # Multi-state toggle button – supports states like “Connect / Connecting / Connected”
│ ├── ToggleComponent.tsx # Simple on/off toggle – commonly used in mobile-style UIs
│ └── ValueSelector.tsx # Numeric value selector – used for numeric inputs (percentage, FPS, etc.); supports min/max and button adjustments
```

---

## 🚀 Quick Start

### Get Started
```bash
# Clone the project
git clone https://github.com/PooyaDeperson/Freemocap-Product-Design-v2.git
cd app-design-v2

# Install dependencies
npm install

# Start the service
npm start
```

Visit `http://localhost:5173` to see the face tracking in action!
