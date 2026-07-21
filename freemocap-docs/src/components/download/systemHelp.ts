export interface HelpSection {
  icon: string;
  title: string;
  content: Array<{
    type: 'paragraph' | 'list';
    text?: string;
    items?: string[];
  }>;
}

export const SYSTEM_HELP_SECTIONS: HelpSection[] = [
  {
    icon: '\uD83C\uDF4E',
    title: 'macOS \u2014 Intel or Apple Silicon?',
    content: [
      {
        type: 'paragraph',
        text: 'Click the Apple menu (\uF8FF) in the top-left corner \u2192 <strong>About This Mac</strong>.',
      },
      {
        type: 'list',
        items: [
          'If <strong>Chip</strong> says <strong>Apple M1, M2, M3, M4</strong> (or similar) \u2192 you\u2019re on <strong>Apple Silicon (ARM64)</strong>',
          'If <strong>Processor</strong> says <strong>Intel Core i5, i7, i9</strong> etc \u2192 you\u2019re on <strong>Intel (x64)</strong>',
        ],
      },
      {
        type: 'paragraph',
        text: 'Or run in Terminal: <code>uname -m</code> \u2014 it prints <code>arm64</code> or <code>x86_64</code>.',
      },
    ],
  },
  {
    icon: '\uD83D\uDC27',
    title: 'Linux \u2014 x64 or ARM64?',
    content: [
      { type: 'paragraph', text: 'Run in a terminal:' },
      { type: 'paragraph', text: '<code>uname -m</code>' },
      {
        type: 'list',
        items: [
          '<code>x86_64</code> \u2192 download the <strong>x64</strong> version',
          '<code>aarch64</code> \u2192 download the <strong>ARM64</strong> version',
        ],
      },
      {
        type: 'paragraph',
        text: 'Common ARM64 devices: Raspberry Pi 3/4/5, NVIDIA Jetson, some cloud VMs (AWS Graviton, Ampere).',
      },
    ],
  },
  {
    icon: '\uD83D\uDC27',
    title: 'Linux \u2014 AppImage or .deb?',
    content: [
      {
        type: 'list',
        items: [
          '<strong>AppImage</strong> \u2014 works on any Linux distro (Ubuntu, Fedora, Arch, etc). Just download and run. No install, no root. Best choice if you\u2019re not sure.',
          '<strong>.deb</strong> \u2014 for Debian-based distros (Ubuntu, Pop!_OS, Linux Mint, Raspberry Pi OS). Integrates with your package manager so it appears in your app launcher and can be cleanly uninstalled.',
        ],
      },
    ],
  },
  {
    icon: '\uD83E\uDE9F',
    title: 'Windows',
    content: [
      {
        type: 'paragraph',
        text: 'FreeMoCap provides a single <strong>x64 (64-bit)</strong> build, which works on virtually all modern Windows PCs \u2014 Intel, AMD, and Snapdragon/ARM laptops. If you have a newer Snapdragon X / Windows on ARM machine, the x64 installer still works via Microsoft\u2019s built-in emulation layer. There\u2019s only one download \u2014 you don\u2019t need to choose.',
      },
    ],
  },
];
