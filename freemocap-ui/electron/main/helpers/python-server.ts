import {exec} from 'child_process';
import fs from 'node:fs';
import {LifecycleLogger} from "./logger";
import {APP_PATHS} from "./app-paths";
import {promisify} from 'util';
import treeKill from "tree-kill";
import {app} from "electron";

const treeKillAsync = promisify(treeKill);
let pythonProcess: ReturnType<typeof exec> | null = null;

export class PythonServer {
    static async start(exePath: string | null) {
        console.log('Starting python server subprocess');
        let executablePath = APP_PATHS.PYTHON_SERVER_EXECUTABLE_PATH;
        try {
            await this.shutdown();

            if (exePath) {
                if (!fs.existsSync(exePath)) {
                    throw new Error(`Provided executable path does not exist: ${exePath}`);
                }
                executablePath = exePath;
            }
            this.validateExecutable(executablePath);
        } catch (error) {
            try {
                executablePath = APP_PATHS.PYTHON_SERVER_EXECUTABLE_PATH_WINDOWS_INSTALL
                executablePath = executablePath.replace('~',app.getPath('home'));
                this.validateExecutable(executablePath);
            } catch (error) {
                console.error('Error validating python server executable:', error);
                throw error;
            }
        }
        pythonProcess = exec(`"${executablePath}"`, {
            env: {
                ...process.env,
            },
            maxBuffer: 1024 * 1024 * 100 // 100MB buffer
        });

        pythonProcess.on('exit', (code) => {
            console.log(`Python exited (code: ${code})`);
        });
        if (!pythonProcess.pid) throw new Error('Python server failed to start!');
        LifecycleLogger.logPythonProcess(pythonProcess);

    }

    static async shutdown() {
        if (!pythonProcess || !pythonProcess.pid) return;
        console.log('Sending SIGTERM to python process');

        try {
            // Kill entire process tree
            await treeKillAsync(pythonProcess.pid);
        } catch (error) {
            console.error('Error killing process tree:', error);
            pythonProcess?.kill('SIGKILL'); // Fallback
        }
        if (!pythonProcess.exitCode) {
            console.error('Python server did not exit cleanly');
            treeKill(pythonProcess.pid, 'SIGKILL');
        } else {
            console.log('Python server exited cleanly');
        }

        pythonProcess = null;
    }

    private static validateExecutable(exePath: string) {
        console.log('Validating python server executable...');
        const checkPath = (path: string) => {
            if (!fs.existsSync(path)) throw new Error(`Missing Python server at ${path}`);
            console.log(`✓ Found python server executable at: ${path}`);
            try {
                fs.accessSync(path, fs.constants.X_OK);
                console.log(`✓ Executable check passed for: ${path}`);
            } catch (error) {
                throw new Error(`✗ File not executable: ${path}\n   Details: ${error}`);
            }
        };

        checkPath(exePath);

        console.log(`Using python server executable at ${APP_PATHS.PYTHON_SERVER_EXECUTABLE_PATH}`);

    }
}
