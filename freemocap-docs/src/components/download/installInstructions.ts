import type { OsType, ArchType, VariantType } from './downloads';
import { downloadUrl, fileLabel } from './downloads';

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
  variant: VariantType | undefined,
  version: string,
): InstructionBlock[] {
  if (os === 'windows') {
    return [
      {
        text: 'Download and run the <code>.exe</code> installer. If Windows SmartScreen appears, click <strong>"More info"</strong> → <strong>"Run anyway"</strong>.',
      },
    ];
  }

  if (os === 'macos') {
    return [
      {
        text: '<strong>.dmg</strong> — Open the disk image and drag FreeMoCap into Applications. On first launch, right-click the app and select <strong>Open</strong> to bypass Gatekeeper.',
      },
      {
        text: '<strong>.zip</strong> — Portable version. Unzip and double-click to run without installing.',
      },
    ];
  }

  if (os === 'linux') {
    const label = fileLabel(os, arch, variant);
    const ai = `freemocap_${version}_${label}.AppImage`;
    const deb = `freemocap_${version}_${label}.deb`;

    return [
      {
        text: '<strong>AppImage</strong> — Portable, works on any distro. Download, make executable, and run. No root needed.',
      },
      {
        codeLines: [
          { type: 'prompt', content: `chmod +x ${ai}`, promptChar: '$' },
          { type: 'prompt', content: `./${ai}`, promptChar: '$' },
        ],
      },
      {
        text: '<strong>.deb</strong> — For Debian, Ubuntu, Pop!_OS, and similar. Installs system-wide with desktop integration.',
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
  variant: VariantType | undefined,
  version: string,
): InstructionBlock[] {
  const label = fileLabel(os, arch, variant);
  const zip = `freemocap_server_${version}_${label}.zip`;
  const bin = os === 'windows' ? 'freemocap_server.exe' : 'freemocap_server';

  if (os === 'windows') {
    return [
      {
        text: 'Download the <code>.zip</code>, extract it, then run the server from inside the extracted folder — it needs its bundled support files alongside it. Starts a local API on port <code>53117</code>.',
      },
      {
        codeLines: [
          { type: 'prompt', content: `Expand-Archive ${zip} -DestinationPath freemocap_server`, promptChar: '>' },
          { type: 'prompt', content: 'cd freemocap_server', promptChar: '>' },
          { type: 'prompt', content: `.\\${bin}`, promptChar: '>' },
        ],
      },
    ];
  }

  if (os === 'macos') {
    return [
      { text: 'Download the <code>.zip</code>, extract it, then make the binary executable and run it from Terminal — it needs its bundled support files alongside it.' },
      {
        codeLines: [
          { type: 'prompt', content: `unzip ${zip} -d freemocap_server`, promptChar: '$' },
          { type: 'prompt', content: 'cd freemocap_server', promptChar: '$' },
          { type: 'prompt', content: `chmod +x ${bin}`, promptChar: '$' },
          { type: 'prompt', content: `xattr -cr ${bin}`, promptChar: '$' },
          { type: 'prompt', content: `./${bin}`, promptChar: '$' },
        ],
      },
      {
        text: 'The <code>xattr</code> command clears the macOS quarantine flag so Gatekeeper won’t block it.',
      },
    ];
  }

  if (os === 'linux') {
    return [
      {
        text: 'Download the <code>.zip</code>, extract it, then make the binary executable and run it — it needs its bundled support files alongside it. Ideal for headless rigs and remote capture machines.',
      },
      {
        codeLines: [
          { type: 'prompt', content: `unzip ${zip} -d freemocap_server`, promptChar: '$' },
          { type: 'prompt', content: 'cd freemocap_server', promptChar: '$' },
          { type: 'prompt', content: `chmod +x ${bin}`, promptChar: '$' },
          { type: 'prompt', content: `./${bin}`, promptChar: '$' },
          { type: 'text', content: '' },
          { type: 'comment', content: '# Or run in background (survives terminal close)' },
          { type: 'prompt', content: `nohup ./${bin} &`, promptChar: '$' },
        ],
      },
    ];
  }

  return [];
}

export function getTerminalInstallBlocks(
  os: OsType,
  arch: ArchType,
  variant: VariantType | undefined,
  version: string,
): InstructionBlock[] {
  if (os !== 'linux' && os !== 'macos') return [];

  const label = fileLabel(os, arch, variant);
  const srvZip = `freemocap_server_${version}_${label}.zip`;
  const blocks: InstructionBlock[] = [];

  if (os === 'linux') {
    const ai = `freemocap_${version}_${label}.AppImage`;
    const deb = `freemocap_${version}_${label}.deb`;

    blocks.push({
      codeLines: [
        { type: 'comment', content: '# App Installer — AppImage (any distro, no root)' },
        { type: 'prompt', content: `curl -fSL -o freemocap.AppImage "${downloadUrl(ai, os, version, variant)}"`, promptChar: '$' },
        { type: 'prompt', content: 'chmod +x freemocap.AppImage', promptChar: '$' },
        { type: 'prompt', content: './freemocap.AppImage', promptChar: '$' },
      ],
    });
    blocks.push({
      codeLines: [
        { type: 'comment', content: '# App Installer — .deb (Debian/Ubuntu)' },
        { type: 'prompt', content: `curl -fSL -o freemocap.deb "${downloadUrl(deb, os, version, variant)}"`, promptChar: '$' },
        { type: 'prompt', content: 'sudo apt install ./freemocap.deb', promptChar: '$' },
      ],
    });
    blocks.push({
      codeLines: [
        { type: 'comment', content: '# Backend Server (headless / remote capture)' },
        { type: 'prompt', content: `curl -fSL -o freemocap_server.zip "${downloadUrl(srvZip, os, version, variant)}"`, promptChar: '$' },
        { type: 'prompt', content: 'unzip freemocap_server.zip -d freemocap_server && cd freemocap_server', promptChar: '$' },
        { type: 'prompt', content: 'chmod +x freemocap_server', promptChar: '$' },
        { type: 'prompt', content: './freemocap_server', promptChar: '$' },
      ],
    });
  }

  if (os === 'macos') {
    const dmg = `freemocap_${version}_${label}.dmg`;

    blocks.push({
      codeLines: [
        { type: 'comment', content: '# App Installer' },
        { type: 'prompt', content: `curl -fSL -o freemocap.dmg "${downloadUrl(dmg, os, version, variant)}"`, promptChar: '$' },
        { type: 'prompt', content: 'open freemocap.dmg', promptChar: '$' },
      ],
    });
    blocks.push({
      codeLines: [
        { type: 'comment', content: '# Backend Server' },
        { type: 'prompt', content: `curl -fSL -o freemocap_server.zip "${downloadUrl(srvZip, os, version, variant)}"`, promptChar: '$' },
        { type: 'prompt', content: 'unzip freemocap_server.zip -d freemocap_server && cd freemocap_server', promptChar: '$' },
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
        'Open <strong>Terminal</strong> from <strong>Applications → Utilities → Terminal</strong>, or press <code>Cmd + Space</code> and type <strong>"Terminal"</strong>.',
      promptChar: '<code>$</code>',
    };
  }
  return {
    openHow:
      'Open your terminal emulator. On most desktops, press <code>Ctrl + Alt + T</code> or find <strong>"Terminal"</strong> in your application launcher.',
    promptChar: '<code>$</code>',
  };
}
