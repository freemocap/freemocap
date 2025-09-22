import path from "node:path";
import {fileURLToPath} from "node:url";

export const __dirname = path.dirname(fileURLToPath(import.meta.url));

export const APP_PATHS = {
    PRELOAD: path.join(__dirname, '../preload/index.mjs'),
    RENDERER_HTML: path.join(__dirname, '../../dist/index.html'),
    PYTHON_SERVER_EXECUTABLE_PATH: path.resolve(process.resourcesPath, 'app.asar.unpacked/freemocap_server.exe'),
        PYTHON_SERVER_EXECUTABLE_PATH_WINDOWS_INSTALL: "~/AppData/Local/Programs/freemocap/resources/app.asar.unpacked/freemocap_server.exe",

    PYTHON_SERVER_EXECUTABLE_DEV: path.resolve(__dirname, '../../freemocap_server.exe'),
    FREEMOCAP_ICON_PATH: path.resolve(__dirname, '../../../shared/logo/freemocap_skelly_logo.ico'),
    FREEMOCAP_PNG_PATH: path.resolve(__dirname, '../../../shared/logo/freemocap-skelly-logo-black-border-transparent-bkgd.png'),



};
