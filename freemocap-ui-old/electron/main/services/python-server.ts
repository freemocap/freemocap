import {exec} from 'child_process';
import fs from 'node:fs';
import path from 'node:path';
import {LifecycleLogger} from "./logger";
import {promisify} from 'util';
import treeKill from "tree-kill";
import {PYTHON_EXECUTABLE_CANDIDATES} from "../app-paths";

const treeKillAsync = promisify(treeKill);
let pythonProcess: ReturnType<typeof exec> | null = null;

const PORT_SENTINEL = "FREEMOCAP_PORT";
const DEFAULT_PORT = 53117;
const PORT_DISCOVERY_TIMEOUT_MS = 30_000;

export interface ExecutableCandidate {
    name: string;
    path: string;
    description: string;
    isValid?: boolean;
    error?: string;
    resolvedPath?: string;
}

export class PythonServer {
    private static currentExecutablePath: string | null = null;
    private static validatedCandidates: ExecutableCandidate[] = [];
    private static discoveredPort: number | null = null;

    /**
     * Start the Python server and wait for it to report which port it bound to.
     * Returns the actual port number.
     */
    static async start(exePath: string | null = null): Promise<number> {
        console.log('Starting python server subprocess...');

        try {
            await this.shutdown();

            let executablePath: string;

            if (exePath) {
                this.validateExecutable(exePath);
                executablePath = exePath;
                console.log(`Using provided executable path: ${executablePath}`);
            } else {
                executablePath = await this.findValidExecutablePath();
                console.log(`Using auto-detected executable path: ${executablePath}`);
            }

            this.currentExecutablePath = executablePath;
            this.discoveredPort = null;
            console.log(`Launching Python server from: ${executablePath}`);
            pythonProcess = exec(`"${executablePath}"`, {
                env: {
                    ...process.env,
                },
                maxBuffer: 1024 * 1024 * 100 // 100MB buffer
            });

            pythonProcess.on('exit', (code) => {
                console.log(`Python server exited (code: ${code})`);
                this.currentExecutablePath = null;
            });

            pythonProcess.on('error', (error) => {
                console.error('Python server process error:', error);
                this.currentExecutablePath = null;
            });

            if (!pythonProcess.pid) {
                throw new Error('Python server failed to start - no process ID');
            }

            LifecycleLogger.logPythonProcess(pythonProcess);
            console.log(`✔ Python server started successfully (PID: ${pythonProcess.pid})`);

            const port = await this.waitForPort(pythonProcess);
            this.discoveredPort = port;
            console.log(`✔ Python server bound to port ${port}`);

            return port;

        } catch (error) {
            console.error('Failed to start Python server:', error);
            this.currentExecutablePath = null;
            throw error;
        }
    }

    /**
     * Read stdout line-by-line until we find the port sentinel or time out.
     */
    private static waitForPort(proc: ReturnType<typeof exec>): Promise<number> {
        return new Promise((resolve, reject) => {
            const timeout = setTimeout(() => {
                reject(new Error(
                    `Python server did not report a port within ${PORT_DISCOVERY_TIMEOUT_MS}ms`
                ));
            }, PORT_DISCOVERY_TIMEOUT_MS);

            const onData = (chunk: Buffer | string): void => {
                const text = chunk.toString();
                for (const line of text.split('\n')) {
                    const trimmed = line.trim();
                    if (trimmed.startsWith(`${PORT_SENTINEL}=`)) {
                        const portStr = trimmed.slice(PORT_SENTINEL.length + 1);
                        const port = parseInt(portStr, 10);
                        if (isNaN(port)) {
                            clearTimeout(timeout);
                            reject(new Error(`Invalid port in sentinel line: ${trimmed}`));
                            return;
                        }
                        clearTimeout(timeout);
                        proc.stdout?.off('data', onData);
                        resolve(port);
                        return;
                    }
                }
            };

            if (!proc.stdout) {
                clearTimeout(timeout);
                reject(new Error('Python process has no stdout stream'));
                return;
            }

            proc.stdout.on('data', onData);

            proc.on('exit', (code) => {
                clearTimeout(timeout);
                reject(new Error(
                    `Python server exited with code ${code} before reporting a port`
                ));
            });
        });
    }

    static async shutdown() {
        if (!pythonProcess || !pythonProcess.pid) {
            console.log('No Python server process to shutdown');
            return;
        }

        console.log(`Shutting down Python server (PID: ${pythonProcess.pid})`);

        try {
            await treeKillAsync(pythonProcess.pid);
            console.log('✔ Python server process tree terminated');
        } catch (error) {
            console.error('Error killing process tree:', error);
            try {
                pythonProcess?.kill('SIGKILL');
                console.log('✔ Python server force-killed as fallback');
            } catch (killError) {
                console.error('Failed to force-kill Python server:', killError);
            }
        }

        await new Promise(resolve => setTimeout(resolve, 1000));

        if (pythonProcess && !pythonProcess.killed) {
            console.warn('Python server may not have exited cleanly');
        }

        pythonProcess = null;
        this.currentExecutablePath = null;
        this.discoveredPort = null;
        console.log('✔ Python server shutdown complete');
    }

    /**
     * Get the port the Python server is currently bound to, or the default if not yet started.
     */
    static getPort(): number {
        return this.discoveredPort ?? DEFAULT_PORT;
    }

    static getCurrentExecutablePath(): string | null {
        return this.currentExecutablePath;
    }

    static async findValidExecutablePath(): Promise<string> {
        console.log('Searching for valid Python server executable...');

        if (this.validatedCandidates.length === 0) {
            await this.validateAllCandidates();
        }

        const validCandidate = this.validatedCandidates.find(candidate => candidate.isValid);

        if (!validCandidate) {
            const errorMessage = 'No valid Python server executable found in any candidate location:\n' +
                this.validatedCandidates.map(c => `  - ${c.name}: ${c.error || 'Unknown error'}`).join('\n');
            throw new Error(errorMessage);
        }

        console.log(`✔ Selected executable: ${validCandidate.name} (${validCandidate.path})`);
        return validCandidate.path;
    }

    static async validateAllCandidates(): Promise<ExecutableCandidate[]> {
        console.log('Validating all executable candidates...');

        const allValidatedCandidates = await Promise.all(
            PYTHON_EXECUTABLE_CANDIDATES.map(async (candidate) => {
                const validatedCandidate: ExecutableCandidate = {
                    ...candidate,
                    isValid: false
                };

                try {
                    this.validateExecutable(candidate.path);
                    validatedCandidate.isValid = true;
                    validatedCandidate.resolvedPath = fs.existsSync(candidate.path)
                        ? path.resolve(candidate.path)
                        : candidate.path;
                    console.log(`  ✔ ${candidate.name}: Valid`);
                } catch (error) {
                    validatedCandidate.error = error instanceof Error ? error.message : 'Unknown validation error';
                    console.log(`  ✗ ${candidate.name}: ${validatedCandidate.error}`);
                }

                return validatedCandidate;
            })
        );

        const seenPaths = new Set<string>();
        this.validatedCandidates = allValidatedCandidates.filter(candidate => {
            const pathKey = candidate.resolvedPath || candidate.path;

            if (seenPaths.has(pathKey)) {
                console.log(`  ⚠ Skipping duplicate: ${candidate.name} (same as another candidate)`);
                return false;
            }

            seenPaths.add(pathKey);
            return true;
        });

        const validCount = this.validatedCandidates.filter(c => c.isValid).length;
        console.log(`Validation complete: ${validCount}/${this.validatedCandidates.length} unique candidates are valid`);

        return this.validatedCandidates;
    }

    static getPythonServerExecutableCandidates(): ExecutableCandidate[] {
        return [...this.validatedCandidates];
    }

    static async refreshCandidates(): Promise<ExecutableCandidate[]> {
        console.log('Refreshing executable candidates validation...');
        this.validatedCandidates = [];
        return await this.validateAllCandidates();
    }

    static isRunning(): boolean {
        return pythonProcess !== null && pythonProcess.pid !== undefined && !pythonProcess.killed;
    }

    static getProcessInfo(): { pid: number | undefined; killed: boolean } | null {
        if (!pythonProcess) return null;

        return {
            pid: pythonProcess.pid,
            killed: pythonProcess.killed || false
        };
    }

    private static validateExecutable(exePath: string): void {
        if (!fs.existsSync(exePath)) {
            throw new Error(`Executable not found at: ${exePath}`);
        }

        const stats = fs.statSync(exePath);
        if (!stats.isFile()) {
            throw new Error(`Path is not a file: ${exePath}`);
        }

        try {
            fs.accessSync(exePath, fs.constants.F_OK | fs.constants.R_OK);

            if (process.platform !== 'win32') {
                fs.accessSync(exePath, fs.constants.X_OK);
            }
        } catch (error) {
            throw new Error(`File is not accessible or executable: ${exePath}`);
        }

        if (process.platform === 'win32' && !exePath.toLowerCase().endsWith('.exe')) {
            console.warn(`Warning: Executable doesn't have .exe extension: ${exePath}`);
        }
    }
}