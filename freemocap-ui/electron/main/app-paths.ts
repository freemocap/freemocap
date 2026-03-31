import path from "node:path";
import os from "node:os";
import {fileURLToPath} from "node:url";
import {app} from "electron";

export const __dirname = path.dirname(fileURLToPath(import.meta.url));

const APP_NAME = 'freemocap';
const SERVER_EXE_NAME = process.platform === 'win32' ? 'freemocap_server.exe' : 'freemocap_server';

// Function to get the correct resources path based on environment
const getResourcesPath = () => {
    if (app.isPackaged) {
        const resourcesPath = path.join(process.resourcesPath, "app.asar.unpacked");
        console.log(`App is packaged. resourcesPath: ${resourcesPath}`);
        return resourcesPath;
    } else {
        const resourcesPath = path.join(__dirname, "../../");
        console.log(`App is in development. resourcesPath: ${resourcesPath}`);
        return resourcesPath;
    }
};

// Platform-specific default install path where electron-builder puts the app
const getDefaultInstallUnpackedPath = (): string => {
    const home = os.homedir();
    switch (process.platform) {
        case 'win32':
            // NSIS per-user install: %LOCALAPPDATA%\Programs\{name}\resources\app.asar.unpacked
            return path.join(home, 'AppData', 'Local', 'Programs', APP_NAME, 'resources', 'app.asar.unpacked');
        case 'darwin':
            // macOS .app bundle: /Applications/{name}.app/Contents/Resources/app.asar.unpacked
            return path.join('/Applications', `${APP_NAME}.app`, 'Contents', 'Resources', 'app.asar.unpacked');
        case 'linux':
            // Linux default: /opt/{name}/resources/app.asar.unpacked
            return path.join('/opt', APP_NAME, 'resources', 'app.asar.unpacked');
        default:
            return path.join(home, APP_NAME, 'resources', 'app.asar.unpacked');
    }
};

// Python server executable candidates in order of preference
export const PYTHON_EXECUTABLE_CANDIDATES = [
    {
        name: 'bundled',
        path: path.join(getResourcesPath(), SERVER_EXE_NAME),
        description: 'Executable bundled with the running app (asar-unpacked)'
    },
    {
        name: 'default-install',
        path: path.join(getDefaultInstallUnpackedPath(), SERVER_EXE_NAME),
        description: 'Executable in the platform default install location'
    },
    {
        name: 'development',
        path: path.join(getResourcesPath(), '..', 'dist', SERVER_EXE_NAME),
        description: 'Development build executable (../dist/)'
    },
    {
        name: 'portable',
        path: path.join(process.cwd(), SERVER_EXE_NAME),
        description: 'Portable executable in the current working directory'
    },
    {
        name: 'system-path',
        path: SERVER_EXE_NAME, // Resolved via PATH
        description: 'Executable available in system PATH'
    }
];

export const APP_PATHS = {
    PRELOAD: path.join(__dirname, "../preload/index.mjs"),
    RENDERER_HTML: path.join(__dirname, "../../dist/index.html"),
    FREEMOCAP_ICON_PATH: path.resolve(
        __dirname,
        "../../../shared/freemocap-logo/freemocap-favicon.ico"
    ),
    SKELLYCAM_LOGO_PNG_RESOURCES_PATH: path.join(getResourcesPath(), 'dist/freemocap-logo.png'),
    SKELLYCAM_LOGO_PNG_SHARED_PATH:path.resolve(
        __dirname,
        "../../../shared/freemocap-logo/freemocap-logo.png"
    ),

};


console.log(`APP_PATHS: ${JSON.stringify(APP_PATHS, null, 2)}`);
