import os from 'node:os';
import fs from 'node:fs';
import path from 'node:path';
import {exec, execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {app} from 'electron';

const execFileAsync = promisify(execFile);
const execAsync = promisify(exec);

// ── Types ──

export interface CpuInfo {
    model: string;
    cores: number;
    threads: number;
    speedMhz: number;
}

export interface RamInfo {
    totalGb: number;
    availableGb: number;
}

export interface GpuInfo {
    name: string;
    vendor: string;
    vramMb: number | null;
    cudaAvailable: boolean;
    cudaVersion: string | null;
}

export interface DiskInfo {
    /** The drive/mount where freemocap data lives */
    path: string;
    totalGb: number;
    freeGb: number;
}

export interface OsInfo {
    platform: string;
    release: string;
    arch: string;
    hostname: string;
}

export type PerformanceTier = 'basic' | 'standard' | 'advanced' | 'pro';

export interface PerformanceRecommendation {
    tier: PerformanceTier;
    label: string;
    description: string;
    maxCameras: number;
    maxResolution: string;
    realtimeTracking: boolean;
    warnings: string[];
}

export interface SystemScanResult {
    cpu: CpuInfo;
    ram: RamInfo;
    gpus: GpuInfo[];
    disk: DiskInfo;
    os: OsInfo;
    recommendation: PerformanceRecommendation;
    scannedAt: string;
}

// ── Scanners ──

function scanCpu(): CpuInfo {
    const cpus = os.cpus();
    if (cpus.length === 0) {
        throw new Error('Failed to detect CPU info');
    }
    return {
        model: cpus[0].model.trim(),
        cores: new Set(cpus.map((_, i) => Math.floor(i / 2))).size || cpus.length,
        threads: cpus.length,
        speedMhz: cpus[0].speed,
    };
}

function scanRam(): RamInfo {
    const totalBytes = os.totalmem();
    const freeBytes = os.freemem();
    return {
        totalGb: Math.round((totalBytes / (1024 ** 3)) * 10) / 10,
        availableGb: Math.round((freeBytes / (1024 ** 3)) * 10) / 10,
    };
}

async function scanGpusWindows(): Promise<GpuInfo[]> {
    const gpus: GpuInfo[] = [];

    // Try WMIC first for all GPUs
    try {
        const { stdout } = await execAsync(
            'wmic path win32_videocontroller get Name,AdapterRAM,DriverVersion /format:csv',
            { timeout: 10000 },
        );
        const lines = stdout.trim().split('\n').filter(l => l.trim().length > 0);
        // First line is header: Node,AdapterRAM,DriverVersion,Name
        for (let i = 1; i < lines.length; i++) {
            const parts = lines[i].split(',');
            if (parts.length < 4) continue;
            const adapterRam = parseInt(parts[1], 10);
            const name = parts[3]?.trim() || 'Unknown GPU';
            const isNvidia = name.toLowerCase().includes('nvidia');
            const isAmd = name.toLowerCase().includes('amd') || name.toLowerCase().includes('radeon');
            gpus.push({
                name,
                vendor: isNvidia ? 'NVIDIA' : isAmd ? 'AMD' : 'Other',
                vramMb: isNaN(adapterRam) ? null : Math.round(adapterRam / (1024 * 1024)),
                cudaAvailable: false, // Filled in below
                cudaVersion: null,
            });
        }
    } catch {
        // WMIC not available or failed
    }

    // Try nvidia-smi for CUDA info
    try {
        const { stdout } = await execAsync(
            'nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader,nounits',
            { timeout: 10000 },
        );
        const lines = stdout.trim().split('\n');
        for (const line of lines) {
            const [name, vramMb, driverVersion] = line.split(',').map(s => s.trim());
            // Try to find matching GPU from WMIC and enrich it
            const existing = gpus.find(g => g.vendor === 'NVIDIA');
            if (existing) {
                existing.cudaAvailable = true;
                existing.cudaVersion = driverVersion || null;
                if (vramMb) {
                    existing.vramMb = parseInt(vramMb, 10);
                }
            } else {
                gpus.push({
                    name: name || 'NVIDIA GPU',
                    vendor: 'NVIDIA',
                    vramMb: vramMb ? parseInt(vramMb, 10) : null,
                    cudaAvailable: true,
                    cudaVersion: driverVersion || null,
                });
            }
        }
    } catch {
        // nvidia-smi not available — no CUDA
    }

    return gpus;
}

async function scanGpusMac(): Promise<GpuInfo[]> {
    const gpus: GpuInfo[] = [];
    try {
        const { stdout } = await execAsync(
            'system_profiler SPDisplaysDataType',
            { timeout: 10000 },
        );
        // Parse the output for chipset/VRAM info
        const chipsetMatch = stdout.match(/Chipset Model:\s*(.+)/g);
        const vramMatch = stdout.match(/VRAM.*?:\s*(\d+)\s*(MB|GB)/gi);
        if (chipsetMatch) {
            for (let i = 0; i < chipsetMatch.length; i++) {
                const name = chipsetMatch[i].replace('Chipset Model:', '').trim();
                let vramMb: number | null = null;
                if (vramMatch && vramMatch[i]) {
                    const m = vramMatch[i].match(/(\d+)\s*(MB|GB)/i);
                    if (m) {
                        vramMb = parseInt(m[1], 10);
                        if (m[2].toUpperCase() === 'GB') vramMb *= 1024;
                    }
                }
                const isApple = name.toLowerCase().includes('apple');
                gpus.push({
                    name,
                    vendor: isApple ? 'Apple' : 'Other',
                    vramMb,
                    cudaAvailable: false,
                    cudaVersion: null,
                });
            }
        }
    } catch {
        // system_profiler failed
    }
    return gpus;
}

async function scanGpusLinux(): Promise<GpuInfo[]> {
    const gpus: GpuInfo[] = [];

    // lspci for GPU detection
    try {
        const { stdout } = await execAsync(
            'lspci | grep -iE "vga|3d|display"',
            { timeout: 10000 },
        );
        for (const line of stdout.trim().split('\n')) {
            if (!line.trim()) continue;
            const name = line.replace(/^.*:\s*/, '').trim();
            const isNvidia = name.toLowerCase().includes('nvidia');
            const isAmd = name.toLowerCase().includes('amd') || name.toLowerCase().includes('radeon');
            gpus.push({
                name,
                vendor: isNvidia ? 'NVIDIA' : isAmd ? 'AMD' : 'Other',
                vramMb: null,
                cudaAvailable: false,
                cudaVersion: null,
            });
        }
    } catch {
        // lspci not available
    }

    // nvidia-smi for CUDA
    try {
        const { stdout } = await execAsync(
            'nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader,nounits',
            { timeout: 10000 },
        );
        const lines = stdout.trim().split('\n');
        for (const line of lines) {
            const [name, vramMb, driverVersion] = line.split(',').map(s => s.trim());
            const existing = gpus.find(g => g.vendor === 'NVIDIA');
            if (existing) {
                existing.cudaAvailable = true;
                existing.cudaVersion = driverVersion || null;
                if (vramMb) existing.vramMb = parseInt(vramMb, 10);
            } else {
                gpus.push({
                    name: name || 'NVIDIA GPU',
                    vendor: 'NVIDIA',
                    vramMb: vramMb ? parseInt(vramMb, 10) : null,
                    cudaAvailable: true,
                    cudaVersion: driverVersion || null,
                });
            }
        }
    } catch {
        // no nvidia-smi
    }

    return gpus;
}

async function scanGpus(): Promise<GpuInfo[]> {
    switch (process.platform) {
        case 'win32': return scanGpusWindows();
        case 'darwin': return scanGpusMac();
        case 'linux': return scanGpusLinux();
        default: return [];
    }
}

async function scanDisk(): Promise<DiskInfo> {
    const dataDir = path.join(app.getPath('home'), 'freemocap_data');
    // Use the drive/mount that the data directory lives on
    const targetPath = fs.existsSync(dataDir) ? dataDir : app.getPath('home');

    try {
        const stats = fs.statfsSync(targetPath);
        const blockSize = stats.bsize;
        const totalGb = Math.round((stats.blocks * blockSize) / (1024 ** 3) * 10) / 10;
        const freeGb = Math.round((stats.bavail * blockSize) / (1024 ** 3) * 10) / 10;
        return { path: targetPath, totalGb, freeGb };
    } catch {
        // statfsSync not available (very old Node) — return unknowns
        return { path: targetPath, totalGb: 0, freeGb: 0 };
    }
}

function scanOs(): OsInfo {
    return {
        platform: process.platform,
        release: os.release(),
        arch: os.arch(),
        hostname: os.hostname(),
    };
}

// ── Performance Recommendation ──

function computeRecommendation(
    cpu: CpuInfo,
    ram: RamInfo,
    gpus: GpuInfo[],
    disk: DiskInfo,
): PerformanceRecommendation {
    const warnings: string[] = [];
    const bestGpu = gpus.reduce<GpuInfo | null>((best, gpu) => {
        if (!best) return gpu;
        if (gpu.cudaAvailable && !best.cudaAvailable) return gpu;
        if ((gpu.vramMb ?? 0) > (best.vramMb ?? 0)) return gpu;
        return best;
    }, null);

    const hasCuda = bestGpu?.cudaAvailable ?? false;
    const vramMb = bestGpu?.vramMb ?? 0;

    // Disk warnings
    if (disk.freeGb > 0 && disk.freeGb < 20) {
        warnings.push(`Low disk space: ${disk.freeGb} GB free. Recordings can use 1-5 GB each.`);
    }

    // RAM warnings
    if (ram.totalGb < 8) {
        warnings.push('Less than 8 GB RAM — performance may be limited even with few cameras.');
    }

    // GPU warnings
    if (gpus.length === 0) {
        warnings.push('No dedicated GPU detected. Real-time pose tracking will not be available.');
    } else if (!hasCuda) {
        warnings.push('No NVIDIA GPU with CUDA detected. Mediapipe GPU acceleration will be unavailable.');
    }

    // Tier computation
    let tier: PerformanceTier;
    let label: string;
    let description: string;
    let maxCameras: number;
    let maxResolution: string;
    let realtimeTracking: boolean;

    if (cpu.threads >= 12 && ram.totalGb >= 32 && hasCuda && vramMb >= 8000) {
        tier = 'pro';
        label = 'Pro';
        description = 'Excellent system. Handles large multi-camera setups with real-time tracking and post-processing.';
        maxCameras = 8;
        maxResolution = '1080p';
        realtimeTracking = true;
    } else if (cpu.threads >= 8 && ram.totalGb >= 16 && hasCuda && vramMb >= 4000) {
        tier = 'advanced';
        label = 'Advanced';
        description = 'Strong system. Supports several cameras with real-time tracking.';
        maxCameras = 5;
        maxResolution = '1080p';
        realtimeTracking = true;
    } else if (cpu.threads >= 4 && ram.totalGb >= 12) {
        tier = 'standard';
        label = 'Standard';
        description = 'Good for multi-camera recording with offline processing.';
        maxCameras = 3;
        maxResolution = '720p';
        realtimeTracking = false;
        if (!hasCuda) {
            warnings.push('Pose estimation will run on CPU — processing will be slower but functional.');
        }
    } else {
        tier = 'basic';
        label = 'Basic';
        description = 'Can record from one or two cameras. Processing will be slow.';
        maxCameras = 2;
        maxResolution = '720p';
        realtimeTracking = false;
    }

    return { tier, label, description, maxCameras, maxResolution, realtimeTracking, warnings };
}

// ── Public API ──

export class SystemScanner {
    static async scan(): Promise<SystemScanResult> {
        const [cpu, ram, gpus, disk] = await Promise.all([
            scanCpu(),
            scanRam(),
            scanGpus(),
            scanDisk(),
        ]);
        const osInfo = scanOs();
        const recommendation = computeRecommendation(cpu, ram, gpus, disk);

        return {
            cpu,
            ram,
            gpus,
            disk,
            os: osInfo,
            recommendation,
            scannedAt: new Date().toISOString(),
        };
    }
}
