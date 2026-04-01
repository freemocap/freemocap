import {exec} from 'child_process';
import fs from 'node:fs';
import path from 'node:path';
import {LifecycleLogger} from "./logger";
import {promisify} from 'util';
import treeKill from "tree-kill";
import {PYTHON_EXECUTABLE_CANDIDATES} from "../app-paths";

const treeKillAsync = promisify(treeKill);
let pythonProcess: ReturnType<typeof exec> | null = null;

export interface ExecutableCandidate {
    name: string;
    path: string;
    description: string;
    isValid?: boolean;
    error?: string;
    resolvedPath?: string; // Add resolved path for deduplication
}

export class PythonServer {
    private static currentExecutablePath: string | null = null;
    private static validatedCandidates: ExecutableCandidate[] = [];

    static async start(exePath: string | null = null) {
        console.log('Starting python server subprocess...');

        try {
            await this.shutdown();

            let executablePath: string;

            if (exePath) {
                // If specific path provided, validate it
                this.validateExecutable(exePath);
                executablePath = exePath;
                console.log(`Using provided executable path: ${executablePath}`);
            } else {
                // Find first valid executable from candidates
                executablePath = await this.findValidExecutablePath();
                console.log(`Using auto-detected executable path: ${executablePath}`);
            }

            this.currentExecutablePath = executablePath;
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

        } catch (error) {
            console.error('Failed to start Python server:', error);
            this.currentExecutablePath = null;
            throw error;
        }
    }

    static async shutdown() {
        if (!pythonProcess || !pythonProcess.pid) {
            console.log('No Python server process to shutdown');
            return;
        }

        console.log(`Shutting down Python server (PID: ${pythonProcess.pid})`);

        try {
            // Kill entire process tree
            await treeKillAsync(pythonProcess.pid);
            console.log('✔ Python server process tree terminated');
        } catch (error) {
            console.error('Error killing process tree:', error);
            // Fallback to direct kill
            try {
                pythonProcess?.kill('SIGKILL');
                console.log('✔ Python server force-killed as fallback');
            } catch (killError) {
                console.error('Failed to force-kill Python server:', killError);
            }
        }

        // Wait a moment for cleanup
        await new Promise(resolve => setTimeout(resolve, 1000));

        if (pythonProcess && !pythonProcess.killed) {
            console.warn('Python server may not have exited cleanly');
        }

        pythonProcess = null;
        this.currentExecutablePath = null;
        console.log('✔ Python server shutdown complete');
    }

    static getCurrentExecutablePath(): string | null {
        return this.currentExecutablePath;
    }

    static async findValidExecutablePath(): Promise<string> {
        console.log('Searching for valid Python server executable...');

        // Validate all candidates if not done yet
        if (this.validatedCandidates.length === 0) {
            await this.validateAllCandidates();
        }

        // Find first valid candidate
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

        // First, validate all candidates
        const allValidatedCandidates = await Promise.all(
            PYTHON_EXECUTABLE_CANDIDATES.map(async (candidate) => {
                const validatedCandidate: ExecutableCandidate = {
                    ...candidate,
                    isValid: false
                };

                try {
                    this.validateExecutable(candidate.path);
                    validatedCandidate.isValid = true;
                    // Store resolved path for deduplication
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

        // Deduplicate by resolved path
        const seenPaths = new Set<string>();
        this.validatedCandidates = allValidatedCandidates.filter(candidate => {
            const pathKey = candidate.resolvedPath || candidate.path;

            // If we've seen this path before, skip it
            if (seenPaths.has(pathKey)) {
                console.log(`  ⚠ Skipping duplicate: ${candidate.name} (same as another candidate)`);
                return false;
            }

            // Add to seen paths
            seenPaths.add(pathKey);
            return true;
        });

        const validCount = this.validatedCandidates.filter(c => c.isValid).length;
        console.log(`Validation complete: ${validCount}/${this.validatedCandidates.length} unique candidates are valid`);

        return this.validatedCandidates;
    }

    static getPythonServerExecutableCandidates(): ExecutableCandidate[] {
        return [...this.validatedCandidates]; // Return copy to prevent mutation
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
        // Check if file exists
        if (!fs.existsSync(exePath)) {
            throw new Error(`Executable not found at: ${exePath}`);
        }

        // Check if it's actually a file (not a directory)
        const stats = fs.statSync(exePath);
        if (!stats.isFile()) {
            throw new Error(`Path is not a file: ${exePath}`);
        }

        // Check if file is executable
        try {
            fs.accessSync(exePath, fs.constants.F_OK | fs.constants.R_OK);

            // On Windows, we mainly check if file exists and is readable
            // On Unix systems, we can check execute permissions
            if (process.platform !== 'win32') {
                fs.accessSync(exePath, fs.constants.X_OK);
            }
        } catch (error) {
            throw new Error(`File is not accessible or executable: ${exePath}`);
        }

        // Additional validation: check file extension on Windows
        if (process.platform === 'win32' && !exePath.toLowerCase().endsWith('.exe')) {
            console.warn(`Warning: Executable doesn't have .exe extension: ${exePath}`);
        }
    }
}