import path from "node:path";
import {fileURLToPath} from "node:url";
import {app} from "electron";

export const __dirname = path.dirname(fileURLToPath(import.meta.url));


// Function to get the correct resources path based on environment
const getResourcesPath = () => {
    if (app.isPackaged) {
        const resourcesPath = path.join(process.resourcesPath, "app.asar.unpacked")
        console.log(`App is packaged. resourcesPath: ${resourcesPath}`);
        return resourcesPath;
    } else {
        const resourcesPath = path.join(__dirname, "../../");
        console.log(`App is in development. resourcesPath: ${resourcesPath}`);
        return resourcesPath;
    }

};

// Python server executable candidates in order of preference
export const PYTHON_EXECUTABLE_CANDIDATES = [
    {
        name: 'development',
        path: path.join(getResourcesPath(), '../dist/freemocap_server.exe'),
        description: 'Development build executable'
    },
    {
        name: 'installed',
        path: path.join(getResourcesPath(), 'freemocap_server.exe'),
        description: 'Executable in the installation folder'
    },

    {
        name: 'portable',
        path: path.join(process.cwd(), 'freemocap_server.exe'),
        description: 'Portable executable in current directory'
    },
    {
        name: 'system-path',
        path: 'freemocap_server.exe', // Will be found via PATH
        description: 'Executable available in system PATH'
    }
];

export const APP_PATHS = {
    PRELOAD: path.join(__dirname, "../preload/index.mjs"),
    RENDERER_HTML: path.join(__dirname, "../../dist/index.html"),
    FREEMOCAP_ICON_PATH: path.resolve(
        __dirname,
        "../../../shared/logo/freemocap-logo.ico"
    ),
        FREEMOCAP_LOGO_PNG_RESOURCES_PATH: path.join(getResourcesPath(), 'dist/freemocap-logo.png'),
    FREEMOCAP_LOGO_PNG_SHARED_PATH:path.resolve(
        __dirname,
        "../../../shared/logo/freemocap-logo.png"
    ),

};


console.log(`APP_PATHS: ${JSON.stringify(APP_PATHS, null, 2)}`);
