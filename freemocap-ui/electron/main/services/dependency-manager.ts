import { exec } from 'node:child_process';
import { promisify } from 'node:util';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { app } from 'electron';

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

export interface PythonEnvStatus {
    envExists: boolean;
    envPath: string;
    packages: { name: string; version: string }[];
    missingPackages: string[];
}

export interface InstallProgress {
    dependencyId: string;
    stage: string;
    percent: number | null;
}

// ── Constants ──

const FREEMOCAP_ENV_DIR = path.join(app.getPath('home'), '.freemocap', 'python-env');
const UV_INSTALL_URL_WINDOWS = 'https://astral.sh/uv/install.ps1';
const UV_INSTALL_URL_UNIX = 'https://astral.sh/uv/install.sh';

const REQUIRED_PYTHON_PACKAGES = [
    'skellycam',
    'skellytracker',
    'skellyforge',
    'aniposelib',
    'mediapipe',
];

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
        description: 'Fast Python package manager — used to manage the FreeMoCap processing environment.',
        required: true,
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

// ── Python Environment Detection ──

async function detectPythonEnv(): Promise<DependencyInfo> {
    const info: DependencyInfo = {
        id: 'python-env',
        name: 'Processing Environment',
        description: 'Managed Python environment with pose estimation and motion capture processing libraries.',
        required: true,
        status: 'checking',
        version: null,
        installedPath: null,
        error: null,
    };

    info.installedPath = FREEMOCAP_ENV_DIR;

    // Check if the venv exists
    const pythonBin = process.platform === 'win32'
        ? path.join(FREEMOCAP_ENV_DIR, 'Scripts', 'python.exe')
        : path.join(FREEMOCAP_ENV_DIR, 'bin', 'python');

    if (!fs.existsSync(pythonBin)) {
        info.status = 'missing';
        return info;
    }

    // Check Python version
    try {
        const { stdout } = await execAsync(`"${pythonBin}" --version`, { timeout: 10000 });
        info.version = stdout.trim();
    } catch {
        info.status = 'error';
        info.error = 'Python environment exists but the interpreter is broken.';
        return info;
    }

    // Check if required packages are installed
    try {
        const pipBin = process.platform === 'win32'
            ? path.join(FREEMOCAP_ENV_DIR, 'Scripts', 'pip.exe')
            : path.join(FREEMOCAP_ENV_DIR, 'bin', 'pip');

        const { stdout } = await execAsync(`"${pipBin}" list --format=json`, { timeout: 30000 });
        const installed = JSON.parse(stdout) as { name: string; version: string }[];
        const installedNames = new Set(installed.map(p => p.name.toLowerCase()));

        const missing = REQUIRED_PYTHON_PACKAGES.filter(
            pkg => !installedNames.has(pkg.toLowerCase()),
        );

        if (missing.length > 0) {
            info.status = 'outdated';
            info.error = `Missing packages: ${missing.join(', ')}`;
        } else {
            info.status = 'installed';
        }
    } catch (err) {
        info.status = 'error';
        info.error = `Failed to check packages: ${err instanceof Error ? err.message : String(err)}`;
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

async function resolveUvPath(): Promise<string> {
    const { exists, output } = await commandExists('uv');
    if (exists) return output.split('\n')[0].trim();

    // Check common locations
    const home = os.homedir();
    const candidates = process.platform === 'win32'
        ? [
            path.join(home, '.local', 'bin', 'uv.exe'),
            path.join(home, '.cargo', 'bin', 'uv.exe'),
        ]
        : [
            path.join(home, '.local', 'bin', 'uv'),
            path.join(home, '.cargo', 'bin', 'uv'),
        ];

    for (const candidate of candidates) {
        if (fs.existsSync(candidate)) return candidate;
    }

    throw new Error('uv is not installed. Install it first.');
}

async function createPythonEnv(): Promise<void> {
    const uv = await resolveUvPath();

    // Create the venv
    console.log(`Creating Python environment at ${FREEMOCAP_ENV_DIR}...`);
    fs.mkdirSync(path.dirname(FREEMOCAP_ENV_DIR), { recursive: true });
    await execAsync(`"${uv}" venv "${FREEMOCAP_ENV_DIR}" --python 3.11`, { timeout: 120000 });

    // Install packages
    console.log('Installing processing packages...');
    await execAsync(
        `"${uv}" pip install --python "${FREEMOCAP_ENV_DIR}" skellytracker[all] skellyforge aniposelib skellycam freemocap`,
        { timeout: 1800000 }, // 30 min — mediapipe + torch are huge
    );
}

async function updatePythonEnv(): Promise<void> {
    const uv = await resolveUvPath();

    console.log('Updating processing packages...');
    await execAsync(
        `"${uv}" pip install --python "${FREEMOCAP_ENV_DIR}" --upgrade skellytracker[all] skellyforge aniposelib skellycam freemocap`,
        { timeout: 1800000 },
    );
}

// ── Public API ──

export class DependencyManager {
    static async detectAll(): Promise<DependencyInfo[]> {
        const results = await Promise.all([
            detectUv(),
            detectPythonEnv(),
            detectCuda(),
            detectBlender(),
        ]);
        return results;
    }

    static async detect(dependencyId: string): Promise<DependencyInfo> {
        switch (dependencyId) {
            case 'blender': return detectBlender();
            case 'uv': return detectUv();
            case 'python-env': return detectPythonEnv();
            case 'cuda': return detectCuda();
            default: throw new Error(`Unknown dependency: ${dependencyId}`);
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

            case 'python-env': {
                const envInfo = await detectPythonEnv();
                if (envInfo.status === 'missing') {
                    await createPythonEnv();
                } else if (envInfo.status === 'outdated') {
                    await updatePythonEnv();
                }
                return detectPythonEnv();
            }

            case 'cuda':
                throw new Error(
                    'CUDA cannot be installed automatically. ' +
                    'Please install the NVIDIA CUDA Toolkit from https://developer.nvidia.com/cuda-downloads',
                );

            default:
                throw new Error(`Unknown dependency: ${dependencyId}`);
        }
    }

    static getPythonEnvPath(): string {
        return FREEMOCAP_ENV_DIR;
    }

    static async getPythonEnvStatus(): Promise<PythonEnvStatus> {
        const pythonBin = process.platform === 'win32'
            ? path.join(FREEMOCAP_ENV_DIR, 'Scripts', 'python.exe')
            : path.join(FREEMOCAP_ENV_DIR, 'bin', 'python');

        const envExists = fs.existsSync(pythonBin);

        if (!envExists) {
            return {
                envExists: false,
                envPath: FREEMOCAP_ENV_DIR,
                packages: [],
                missingPackages: [...REQUIRED_PYTHON_PACKAGES],
            };
        }

        let packages: { name: string; version: string }[] = [];
        try {
            const pipBin = process.platform === 'win32'
                ? path.join(FREEMOCAP_ENV_DIR, 'Scripts', 'pip.exe')
                : path.join(FREEMOCAP_ENV_DIR, 'bin', 'pip');
            const { stdout } = await execAsync(`"${pipBin}" list --format=json`, { timeout: 30000 });
            packages = JSON.parse(stdout);
        } catch { /* pip list failed */ }

        const installedNames = new Set(packages.map(p => p.name.toLowerCase()));
        const missingPackages = REQUIRED_PYTHON_PACKAGES.filter(
            pkg => !installedNames.has(pkg.toLowerCase()),
        );

        return {
            envExists,
            envPath: FREEMOCAP_ENV_DIR,
            packages,
            missingPackages,
        };
    }
}
