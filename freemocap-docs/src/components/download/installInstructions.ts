import type { OsType, ArchType } from './downloads';
import { fileLabel } from './downloads';

export interface CodeLine {
  type: 'prompt' | 'comment' | 'text';
  content: string;
  promptChar?: string;
}

export interface InstructionBlock {
  text?: string;
  codeLines?: CodeLine[];
}

export function getAppInstallInstructions(
  os: OsType,
  arch: ArchType,
  version: string,
): InstructionBlock[] {
  if (os === 'windows') {
    return [
      {
        text: 'Download and run the <code>.exe</code> installer. If Windows SmartScreen appears, click <strong>"More info"</strong> \u2192 <strong>"Run anyway"</strong>.',
      },
    ];
  }

  if (os === 'macos') {
    return [
      {
        text: '<strong>.dmg</strong> \u2014 Open the disk image and drag FreeMoCap into Applications. On first launch, right-click the app and select <strong>Open</strong> to bypass Gatekeeper.',
      },
      {
        text: '<strong>.zip</strong> \u2014 Portable version. Unzip and double-click to run without installing.',
      },
    ];
  }

  if (os === 'linux') {
    const label = fileLabel(os, arch);
    const ai = `freemocap_${version}_${label}.AppImage`;
    const deb = `freemocap_${version}_${label}.deb`;

    return [
      {
        text: '<strong>AppImage</strong> \u2014 Portable, works on any distro. Download, make executable, and run. No root needed.',
      },
      {
        codeLines: [
          { type: 'prompt', content: `chmod +x ${ai}`, promptChar: '$' },
          { type: 'prompt', content: `./${ai}`, promptChar: '$' },
        ],
      },
      {
        text: '<strong>.deb</strong> \u2014 For Debian, Ubuntu, Pop!_OS, and similar. Installs system-wide with desktop integration.',
      },
      {
        codeLines: [
          { type: 'prompt', content: `sudo apt install ./${deb}`, promptChar: '$' },
        ],
      },
    ];
  }

  return [];
}

export function getServerInstallInstructions(
  os: OsType,
  arch: ArchType,
  version: string,
): InstructionBlock[] {
  const label = fileLabel(os, arch);
  const srv =
    os === 'windows'
      ? `freemocap_server_${version}_${label}.exe`
      : `freemocap_server_${version}_${label}`;

  if (os === 'windows') {
    return [
      {
        text: 'Download and run from a terminal. The server starts a local API on port <code>53117</code>.',
      },
      {
        codeLines: [
          { type: 'prompt', content: `.\\${srv}`, promptChar: '>' },
        ],
      },
    ];
  }

  if (os === 'macos') {
    return [
      { text: 'Download, make executable, and run from Terminal.' },
      {
        codeLines: [
          { type: 'prompt', content: `chmod +x ${srv}`, promptChar: '$' },
          { type: 'prompt', content: `xattr -cr ${srv}`, promptChar: '$' },
          { type: 'prompt', content: `./${srv}`, promptChar: '$' },
        ],
      },
      {
        text: 'The <code>xattr</code> command clears the macOS quarantine flag so Gatekeeper won\u2019t block it.',
      },
    ];
  }

  if (os === 'linux') {
    return [
      {
        text: 'Download, make executable, and run. Ideal for headless rigs, Raspberry Pis, or remote capture machines.',
      },
      {
        codeLines: [
          { type: 'prompt', content: `chmod +x ${srv}`, promptChar: '$' },
          { type: 'prompt', content: `./${srv}`, promptChar: '$' },
          { type: 'text', content: '' },
          { type: 'comment', content: '# Or run in background (survives terminal close)' },
          { type: 'prompt', content: `nohup ./${srv} &`, promptChar: '$' },
        ],
      },
    ];
  }

  return [];
}

export function getTerminalInstallBlocks(
  os: OsType,
  arch: ArchType,
  version: string,
  baseUrl: string,
): InstructionBlock[] {
  if (os !== 'linux' && os !== 'macos') return [];

  const label = fileLabel(os, arch);
  const blocks: InstructionBlock[] = [];

  if (os === 'linux') {
    const ai = `freemocap_${version}_${label}.AppImage`;
    const deb = `freemocap_${version}_${label}.deb`;
    const srv = `freemocap_server_${version}_${label}`;

    blocks.push({
      codeLines: [
        { type: 'comment', content: '# App Installer \u2014 AppImage (any distro, no root)' },
        { type: 'prompt', content: `curl -fSL -o freemocap.AppImage "${baseUrl}/${ai}"`, promptChar: '$' },
        { type: 'prompt', content: 'chmod +x freemocap.AppImage', promptChar: '$' },
        { type: 'prompt', content: './freemocap.AppImage', promptChar: '$' },
      ],
    });
    blocks.push({
      codeLines: [
        { type: 'comment', content: '# App Installer \u2014 .deb (Debian/Ubuntu)' },
        { type: 'prompt', content: `curl -fSL -o freemocap.deb "${baseUrl}/${deb}"`, promptChar: '$' },
        { type: 'prompt', content: 'sudo apt install ./freemocap.deb', promptChar: '$' },
      ],
    });
    blocks.push({
      codeLines: [
        { type: 'comment', content: '# Backend Server (headless / Raspberry Pi)' },
        { type: 'prompt', content: `curl -fSL -o freemocap_server "${baseUrl}/${srv}"`, promptChar: '$' },
        { type: 'prompt', content: 'chmod +x freemocap_server', promptChar: '$' },
        { type: 'prompt', content: './freemocap_server', promptChar: '$' },
      ],
    });
  }

  if (os === 'macos') {
    const dmg = `freemocap_${version}_${label}.dmg`;
    const srv = `freemocap_server_${version}_${label}`;

    blocks.push({
      codeLines: [
        { type: 'comment', content: '# App Installer' },
        { type: 'prompt', content: `curl -fSL -o freemocap.dmg "${baseUrl}/${dmg}"`, promptChar: '$' },
        { type: 'prompt', content: 'open freemocap.dmg', promptChar: '$' },
      ],
    });
    blocks.push({
      codeLines: [
        { type: 'comment', content: '# Backend Server' },
        { type: 'prompt', content: `curl -fSL -o freemocap_server "${baseUrl}/${srv}"`, promptChar: '$' },
        { type: 'prompt', content: 'chmod +x freemocap_server && xattr -cr freemocap_server', promptChar: '$' },
        { type: 'prompt', content: './freemocap_server', promptChar: '$' },
      ],
    });
  }

  return blocks;
}

export function getTerminalTipContent(os: OsType): {
  openHow: string;
  promptChar: string;
} {
  if (os === 'windows') {
    return {
      openHow:
        'Press <code>Win + X</code> then choose <strong>Terminal</strong>, or search for <strong>"PowerShell"</strong> in the Start menu.',
      promptChar: '<code>&gt;</code>',
    };
  }
  if (os === 'macos') {
    return {
      openHow:
        'Open <strong>Terminal</strong> from <strong>Applications \u2192 Utilities \u2192 Terminal</strong>, or press <code>Cmd + Space</code> and type <strong>"Terminal"</strong>.',
      promptChar: '<code>$</code>',
    };
  }
  return {
    openHow:
      'Open your terminal emulator. On most desktops, press <code>Ctrl + Alt + T</code> or find <strong>"Terminal"</strong> in your application launcher.',
    promptChar: '<code>$</code>',
  };
}
