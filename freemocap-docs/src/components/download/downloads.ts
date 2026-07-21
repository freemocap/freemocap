import type { LinkedIssue } from '@freemocap/skellydocs';
export type { LinkedIssue };

export type OsType = 'windows' | 'macos' | 'linux';
export type ArchType = 'x64' | 'arm64';

export interface DownloadEntry {
  os: OsType;
  arch: ArchType;
  fmt: string;
  recommended: boolean;
  label: string;
  file: string;
  size: string;
}

export interface OsNoteEntry {
  os: OsType;
  arch?: ArchType;
  variant: 'warning' | 'info' | 'tip';
  title: string;
  content: string;
  issues?: LinkedIssue[];
}

export interface GitHubAsset {
  name: string;
  size: number;
  browser_download_url: string;
}

export interface GitHubRelease {
  tag_name: string;
  name: string;
  published_at: string;
  assets: GitHubAsset[];
  prerelease: boolean;
}

export const DEFAULT_VERSION = '2.0.0-alpha.3';
export const REPO = 'freemocap/freemocap';

export function getReleaseBaseUrl(version: string): string {
  return `https://github.com/${REPO}/releases/download/v${version}`;
}

export function buildAppDownloads(version: string): DownloadEntry[] {
  return [
    { os: 'windows', arch: 'x64',   fmt: 'exe',      recommended: true,  label: 'Windows Installer',              file: `freemocap_${version}_windows-x64.exe`,               size: '' },
    { os: 'macos',   arch: 'arm64', fmt: 'dmg',      recommended: true,  label: 'macOS Installer (Apple Silicon)', file: `freemocap_${version}_macos-arm64-apple-silicon.dmg`,  size: '' },
    { os: 'macos',   arch: 'x64',   fmt: 'dmg',      recommended: true,  label: 'macOS Installer (Intel)',         file: `freemocap_${version}_macos-x64-intel.dmg`,            size: '' },
    { os: 'macos',   arch: 'arm64', fmt: 'zip',      recommended: false, label: 'macOS Portable (Apple Silicon)',  file: `freemocap_${version}_macos-arm64-apple-silicon.zip`,  size: '' },
    { os: 'macos',   arch: 'x64',   fmt: 'zip',      recommended: false, label: 'macOS Portable (Intel)',          file: `freemocap_${version}_macos-x64-intel.zip`,            size: '' },
    { os: 'linux',   arch: 'x64',   fmt: 'AppImage', recommended: true,  label: 'Linux AppImage (x64)',            file: `freemocap_${version}_linux-x64.AppImage`,             size: '' },
    { os: 'linux',   arch: 'arm64', fmt: 'AppImage', recommended: true,  label: 'Linux AppImage (ARM64)',          file: `freemocap_${version}_linux-arm64.AppImage`,            size: '' },
    { os: 'linux',   arch: 'x64',   fmt: 'deb',      recommended: false, label: 'Linux .deb (x64)',                file: `freemocap_${version}_linux-x64.deb`,                  size: '' },
    { os: 'linux',   arch: 'arm64', fmt: 'deb',      recommended: false, label: 'Linux .deb (ARM64)',              file: `freemocap_${version}_linux-arm64.deb`,                 size: '' },
  ];
}

export function buildServerDownloads(version: string): DownloadEntry[] {
  return [
    { os: 'windows', arch: 'x64',   fmt: 'exe', recommended: false, label: 'Server \u2014 Windows x64',        file: `freemocap_server_${version}_windows-x64.exe`,           size: '' },
    { os: 'macos',   arch: 'arm64', fmt: 'bin', recommended: false, label: 'Server \u2014 macOS Apple Silicon', file: `freemocap_server_${version}_macos-arm64-apple-silicon`,  size: '' },
    { os: 'macos',   arch: 'x64',   fmt: 'bin', recommended: false, label: 'Server \u2014 macOS Intel',         file: `freemocap_server_${version}_macos-x64-intel`,            size: '' },
    { os: 'linux',   arch: 'x64',   fmt: 'bin', recommended: false, label: 'Server \u2014 Linux x64',           file: `freemocap_server_${version}_linux-x64`,                  size: '' },
    { os: 'linux',   arch: 'arm64', fmt: 'bin', recommended: false, label: 'Server \u2014 Linux ARM64',          file: `freemocap_server_${version}_linux-arm64`,                size: '' },
  ];
}

export function formatBytes(bytes: number): string {
  const mb = bytes / (1024 * 1024);
  return `~${Math.round(mb)} MB`;
}

export function enrichDownloadsWithAssets(
  downloads: DownloadEntry[],
  assets: GitHubAsset[],
): DownloadEntry[] {
  const assetMap = new Map(assets.map(a => [a.name, a]));
  return downloads.map(d => {
    const asset = assetMap.get(d.file);
    return asset ? { ...d, size: formatBytes(asset.size) } : d;
  });
}

/** Check if a release's assets match our expected filename patterns */
export function matchesExpectedPattern(assets: GitHubAsset[], version: string): boolean {
  const expectedFiles = [
    ...buildAppDownloads(version).map(d => d.file),
    ...buildServerDownloads(version).map(d => d.file),
  ];
  const assetNames = new Set(assets.map(a => a.name));
  // Consider it a match if at least 3 of our expected files exist
  const matchCount = expectedFiles.filter(f => assetNames.has(f)).length;
  return matchCount >= 3;
}

export function fileLabel(os: OsType, arch: ArchType): string {
  if (os === 'macos') return arch === 'arm64' ? 'macos-arm64-apple-silicon' : 'macos-x64-intel';
  if (os === 'linux') return arch === 'arm64' ? 'linux-arm64' : 'linux-x64';
  return 'windows-x64';
}

export function formatMeta(d: DownloadEntry): string {
  const parts = [d.fmt.toUpperCase()];
  if (d.os !== 'windows') parts.push(d.arch === 'arm64' ? 'ARM64' : 'x64');
  return parts.join(' \u00B7 ');
}

export const OS_LABELS: Record<string, string> = {
  windows: 'Windows x64',
  macos: 'macOS',
  linux: 'Linux',
  unknown: 'Unknown OS',
};

export function archLabel(arch: ArchType): string {
  return arch === 'arm64' ? 'ARM64 / Apple Silicon' : 'x64 / Intel';
}

export function stripVersionPrefix(tag: string): string {
  return tag.replace(/^v/, '');
}

// Per-OS/arch advisories shown above the download cards for the matching system.
// Add FreeMoCap-specific notes here (platform caveats, known issues, help wanted).
export const OS_NOTES: OsNoteEntry[] = [];

export const OS_PILL_OPTIONS = [
  { os: 'windows' as OsType, arch: 'x64' as ArchType, label: 'Windows' },
  { os: 'macos' as OsType, arch: 'arm64' as ArchType, label: 'Mac (Apple\u00A0Silicon)' },
  { os: 'macos' as OsType, arch: 'x64' as ArchType, label: 'Mac (Intel)' },
  { os: 'linux' as OsType, arch: 'x64' as ArchType, label: 'Linux x64' },
  { os: 'linux' as OsType, arch: 'arm64' as ArchType, label: 'Linux ARM64' },
] as const;
