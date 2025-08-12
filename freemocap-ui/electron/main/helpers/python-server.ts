import {exec} from 'child_process';
import fs from 'node:fs';
import {LifecycleLogger} from "./logger";
import {APP_PATHS} from "./app-paths";
import {promisify} from 'util';
import treeKill from "tree-kill";

const treeKillAsync = promisify(treeKill);
let pythonProcess: ReturnType<typeof exec> | null = null;

export class PythonServer {
    static async start() {
        console.log('Starting python server subprocess');
        this.validateExecutable();

        pythonProcess = exec(`"${APP_PATHS.PYTHON_SERVER_EXECUTABLE_PATH}"`, {
            env: {
                ...process.env,
                PYTHONIOENCODING: 'utf-8',
                PYTHONUTF8: '1'
            },
            maxBuffer: 1024 * 1024
        });

        pythonProcess.stdout?.on('data', (data) =>
            console.log(`[Python] ${data}`));

        pythonProcess.stderr?.on('data', (data) =>
            console.error(`[Python Error] ${data}`));

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

    private static validateExecutable() {
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

        try {
            checkPath(APP_PATHS.PYTHON_SERVER_EXECUTABLE_PATH);
        } catch {
            checkPath(APP_PATHS.PYTHON_SERVER_EXECUTABLE_DEV);
            APP_PATHS.PYTHON_SERVER_EXECUTABLE_PATH = APP_PATHS.PYTHON_SERVER_EXECUTABLE_DEV;
        }
        console.log(`Using python server executable at ${APP_PATHS.PYTHON_SERVER_EXECUTABLE_PATH}`);

    }
}
