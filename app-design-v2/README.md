# Freemocap Product Design v2

## 📁 Project Structure

```
app-design-v2/
├── public/
│   ├── 3d-asset/
│   │   └── freemocap-skelly.glb
│   ├── images/
│   │   ├── logo_name.svg
│   │   └── splashmodal_art.webp
│   └── vite.svg
└── src/
    ├── App.css
    ├── App.tsx
    ├── electron.d.ts
    ├── index.css
    ├── main.tsx
    ├── vite-env.d.ts
    ├── assets/
    │   ├── react.svg
    │   └── icons/
    ├── components/
    │   ├── composites/
    │   │   └── ConnectionDropdown.tsx
    │   ├── hooks/
    │   │   └── useDraggableTooltips.tsx
    │   ├── modals/
    │   │   ├── CameraSettingsModal.tsx
    │   │   ├── FileDirectorySettingsModal.tsx
    │   │   └── SplashModal.tsx
    │   ├── modes/
    │   │   ├── CaptureLive.tsx
    │   │   └── PostProcess.tsx
    │   ├── panels/
    │   │   ├── HeaderPanel.tsx
    │   │   ├── InfoPanel.tsx
    │   │   └── ModePanel.tsx
    │   ├── ThreeD/
    │   │   ├── CameraLogger.tsx
    │   │   └── ThreeDScene.tsx
    │   ├── tooltips/
    │   │   └── ExcludedCameraTooltip.tsx
    │   └── uicomponents/
    │       ├── ButtonCard.tsx
    │       ├── ButtonSm.tsx
    │       ├── Checkbox.tsx
    │       ├── ConnectionDropdown.tsx
    │       ├── DropdownButton.tsx
    │       ├── IconSegmentedControl.tsx
    │       ├── NameDropdownSelector.tsx
    │       ├── SegmentedControl.tsx
    │       ├── states.ts
    │       ├── SubactionHeader.tsx
    │       ├── TextSelector.tsx
    │       ├── ToggleButtonComponent.tsx
    │       ├── ToggleComponent.tsx
    │       └── ValueSelector.tsx
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
