import { exec } from 'node:child_process';
import { promisify } from 'node:util';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';

const execAsync = promisify(exec);

// ── Types ──

export type DependencyStatus = 'installed' | 'missing' | 'outdated' | 'checking' | 'installing' | 'error';

export interface DependencyInfo {
    id: string;
    name: string;
    description: string;
    required: boolean;
    status: DependencyStatus;
    version: string | null;
    installedPath: string | null;
    error: string | null;
}

// ── Constants ──

const UV_INSTALL_URL_WINDOWS = 'https://astral.sh/uv/install.ps1';
const UV_INSTALL_URL_UNIX = 'https://astral.sh/uv/install.sh';

// ── Helpers ──

async function commandExists(command: string): Promise<{ exists: boolean; output: string }> {
    try {
        const { stdout } = await execAsync(
            process.platform === 'win32'
                ? `where ${command}`
                : `which ${command}`,
            { timeout: 10000 },
        );
        return { exists: true, output: stdout.trim() };
    } catch {
        return { exists: false, output: '' };
    }
}

async function getCommandVersion(command: string, versionFlag: string = '--version'): Promise<string | null> {
    try {
        const { stdout } = await execAsync(`${command} ${versionFlag}`, { timeout: 15000 });
        return stdout.trim().split('\n')[0];
    } catch {
        return null;
    }
}

// ── Blender Detection ──

async function detectBlender(): Promise<DependencyInfo> {
    const info: DependencyInfo = {
        id: 'blender',
        name: 'Blender',
        description: '3D creation suite — used for viewing and animating motion capture data.',
        required: false,
        status: 'checking',
        version: null,
        installedPath: null,
        error: null,
    };

    // Check PATH
    const { exists, output } = await commandExists('blender');
    if (exists) {
        info.installedPath = output.split('\n')[0].trim();
        info.version = await getCommandVersion('blender');
        info.status = 'installed';
        return info;
    }

    // Check common install locations
    const candidates: string[] = [];
    switch (process.platform) {
        case 'win32':
            // Common Windows paths
            const programFiles = process.env['ProgramFiles'] || 'C:\\Program Files';
            try {
                const blenderDir = path.join(programFiles, 'Blender Foundation');
                if (fs.existsSync(blenderDir)) {
                    const versions = fs.readdirSync(blenderDir).sort().reverse();
                    for (const ver of versions) {
                        candidates.push(path.join(blenderDir, ver, 'blender.exe'));
                    }
                }
            } catch { /* dir doesn't exist */ }
            break;
        case 'darwin':
            candidates.push('/Applications/Blender.app/Contents/MacOS/Blender');
            candidates.push('/Applications/Blender.app/Contents/MacOS/blender');
            break;
        case 'linux':
            candidates.push('/usr/bin/blender');
            candidates.push('/snap/bin/blender');
            candidates.push('/var/lib/flatpak/exports/bin/org.blender.Blender');
            break;
    }

    for (const candidate of candidates) {
        if (fs.existsSync(candidate)) {
            info.installedPath = candidate;
            try {
                const { stdout } = await execAsync(`"${candidate}" --version`, { timeout: 15000 });
                info.version = stdout.trim().split('\n')[0];
            } catch { /* version check failed but binary exists */ }
            info.status = 'installed';
            return info;
        }
    }

    info.status = 'missing';
    return info;
}

// ── uv Detection ──

async function detectUv(): Promise<DependencyInfo> {
    const info: DependencyInfo = {
        id: 'uv',
        name: 'uv',
        description: 'Fast Python package manager — useful for development and managing additional processing tools.',
        required: false,
        status: 'checking',
        version: null,
        installedPath: null,
        error: null,
    };

    const { exists, output } = await commandExists('uv');
    if (exists) {
        info.installedPath = output.split('\n')[0].trim();
        info.version = await getCommandVersion('uv');
        info.status = 'installed';
        return info;
    }

    // Check common uv install locations
    const home = os.homedir();
    const candidates: string[] = [];
    switch (process.platform) {
        case 'win32':
            candidates.push(path.join(home, '.local', 'bin', 'uv.exe'));
            candidates.push(path.join(home, '.cargo', 'bin', 'uv.exe'));
            break;
        case 'darwin':
        case 'linux':
            candidates.push(path.join(home, '.local', 'bin', 'uv'));
            candidates.push(path.join(home, '.cargo', 'bin', 'uv'));
            break;
    }

    for (const candidate of candidates) {
        if (fs.existsSync(candidate)) {
            info.installedPath = candidate;
            try {
                const { stdout } = await execAsync(`"${candidate}" --version`, { timeout: 10000 });
                info.version = stdout.trim();
            } catch { /* binary found but version check failed */ }
            info.status = 'installed';
            return info;
        }
    }

    info.status = 'missing';
    return info;
}

// ── FreeMoCap Server Executable Detection ──

async function detectFreemocapServer(): Promise<DependencyInfo> {
    const info: DependencyInfo = {
        id: 'freemocap-server',
        name: 'FreeMoCap Server',
        description: 'Bundled Python server that handles cameras, processing, and WebSocket communication.',
        required: true,
        status: 'checking',
        version: null,
        installedPath: null,
        error: null,
    };

    // Use the PythonServer candidate validation to find the exe
    try {
        const { PythonServer } = await import('./python-server');
        const candidates = await PythonServer.validateAllCandidates();
        const validCandidate = candidates.find(c => c.isValid);

        if (validCandidate) {
            info.status = 'installed';
            info.installedPath = validCandidate.path;
            info.version = validCandidate.name;
        } else {
            info.status = 'missing';
            info.error = 'No valid freemocap_server executable found. Reinstall the application or build the server.';
        }
    } catch (err) {
        info.status = 'error';
        info.error = `Detection failed: ${err instanceof Error ? err.message : String(err)}`;
    }

    return info;
}

// ── CUDA Detection ──

async function detectCuda(): Promise<DependencyInfo> {
    const info: DependencyInfo = {
        id: 'cuda',
        name: 'NVIDIA CUDA',
        description: 'GPU acceleration for pose estimation — dramatically speeds up processing.',
        required: false,
        status: 'checking',
        version: null,
        installedPath: null,
        error: null,
    };

    try {
        const { stdout } = await execAsync('nvidia-smi', { timeout: 10000 });
        // Parse CUDA version from nvidia-smi output
        const cudaMatch = stdout.match(/CUDA Version:\s*([\d.]+)/);
        if (cudaMatch) {
            info.version = `CUDA ${cudaMatch[1]}`;
            info.status = 'installed';
        } else {
            // nvidia-smi works but CUDA version not found — driver exists, CUDA toolkit may not
            const driverMatch = stdout.match(/Driver Version:\s*([\d.]+)/);
            info.version = driverMatch ? `Driver ${driverMatch[1]}` : 'Driver detected';
            info.status = 'installed';
        }
    } catch {
        info.status = 'missing';
    }

    return info;
}

// ── Installation ──

async function installBlender(): Promise<void> {
    switch (process.platform) {
        case 'win32': {
            // Try winget first
            const { exists: hasWinget } = await commandExists('winget');
            if (hasWinget) {
                const { stderr } = await execAsync(
                    'winget install BlenderFoundation.Blender --silent --accept-package-agreements --accept-source-agreements',
                    { timeout: 600000 }, // 10 min timeout
                );
                if (stderr && stderr.includes('error')) {
                    throw new Error(`winget install failed: ${stderr}`);
                }
                return;
            }
            throw new Error(
                'winget is not available. Please install Blender manually from https://www.blender.org/download/',
            );
        }
        case 'darwin': {
            const { exists: hasBrew } = await commandExists('brew');
            if (hasBrew) {
                await execAsync('brew install --cask blender', { timeout: 600000 });
                return;
            }
            throw new Error(
                'Homebrew is not available. Please install Blender manually from https://www.blender.org/download/',
            );
        }
        case 'linux': {
            // Try flatpak, then snap
            const { exists: hasFlatpak } = await commandExists('flatpak');
            if (hasFlatpak) {
                await execAsync(
                    'flatpak install -y flathub org.blender.Blender',
                    { timeout: 600000 },
                );
                return;
            }
            const { exists: hasSnap } = await commandExists('snap');
            if (hasSnap) {
                await execAsync('sudo snap install blender --classic', { timeout: 600000 });
                return;
            }
            throw new Error(
                'Neither flatpak nor snap is available. Please install Blender using your package manager.',
            );
        }
        default:
            throw new Error(`Unsupported platform: ${process.platform}`);
    }
}

async function installUv(): Promise<void> {
    switch (process.platform) {
        case 'win32':
            await execAsync(
                `powershell -ExecutionPolicy ByPass -c "irm ${UV_INSTALL_URL_WINDOWS} | iex"`,
                { timeout: 120000 },
            );
            break;
        case 'darwin':
        case 'linux':
            await execAsync(
                `curl -LsSf ${UV_INSTALL_URL_UNIX} | sh`,
                { timeout: 120000 },
            );
            break;
        default:
            throw new Error(`Unsupported platform: ${process.platform}`);
    }
}

// ── Public API ──

export class DependencyManager {
    static async detectAll(): Promise<DependencyInfo[]> {
        const results = await Promise.all([
            detectFreemocapServer(),
            detectUv(),
            detectCuda(),
            detectBlender(),
        ]);
        return results;
    }

    static async detect(dependencyId: string): Promise<DependencyInfo> {
        switch (dependencyId) {
            case 'freemocap-server':
                return detectFreemocapServer();
            case 'uv':
                return detectUv();
            case 'blender':
                return detectBlender();
            case 'cuda':
                return detectCuda();
            default:
                throw new Error(`Unknown dependency: ${dependencyId}`);
        }
    }

    static async install(dependencyId: string): Promise<DependencyInfo> {
        switch (dependencyId) {
            case 'blender':
                await installBlender();
                return detectBlender();

            case 'uv':
                await installUv();
                return detectUv();

            case 'freemocap-server':
                throw new Error(
                    'The FreeMoCap server executable is bundled with the application. ' +
                    'Reinstall the app to restore it.',
                );

            case 'cuda':
                throw new Error(
                    'CUDA cannot be installed automatically. ' +
                    'Please install the NVIDIA CUDA Toolkit from https://developer.nvidia.com/cuda-downloads',
                );

            default:
                throw new Error(`Unknown dependency: ${dependencyId}`);
        }
    }
}