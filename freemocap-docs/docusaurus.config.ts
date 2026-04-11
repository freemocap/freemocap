import { themes as prismThemes } from 'prism-react-renderer';
import type { Config } from '@docusaurus/types';

const config: Config = {
  title: 'freemocap',
  tagline: 'Documentation for freemocap',
  favicon: 'img/favicon.ico',

  url: 'https://freemocap.org',
  baseUrl: '/freemocap/',

  organizationName: 'freemocap',
  projectName: 'freemocap',

  onBrokenLinks: 'throw',

  markdown: { mermaid: true },

  themes: ['@docusaurus/theme-mermaid'],

  plugins: [
    // webpack 5 enforces full file extensions on imports from ESM packages.
    // tsup/esbuild strips .js extensions in unbundled output, so we relax
    // that strictness here.
    function skellydocsWebpackFixes() {
      return {
        name: 'skellydocs-webpack-fixes',
        configureWebpack() {
          return {
            // tsup/esbuild strips .js extensions in unbundled output;
            // webpack 5 enforces them on ESM imports, so relax that.
            module: {
              rules: [{ test: /\.m?js$/, resolve: { fullySpecified: false } }],
            },
            // Prevent webpack from reading .docusaurus/ metadata files
            // mid-write during regeneration (causes JSON parse errors on Windows).
            watchOptions: {
              ignored: ['**/.docusaurus/**'],
            },
          };
        },
      };
    },
  ],

  presets: [
    [
      'classic',
      {
        docs: {
          sidebarPath: require.resolve('./sidebars.ts'),
          routeBasePath: 'docs',
          editUrl: 'https://github.com/freemocap/freemocap/tree/main/freemocap-docs/',
        },
        blog: {
          showReadingTime: true,
          feedOptions: { type: ['rss', 'atom'], xslt: true },
          editUrl: 'https://github.com/freemocap/freemocap/tree/main/freemocap-docs/',
          onInlineTags: 'warn',
          onInlineAuthors: 'warn',
          onUntruncatedBlogPosts: 'warn',
        },
        theme: {
          customCss: [require.resolve('@freemocap/skellydocs/css/custom.css')],
        },
      },
    ],
  ],

  themeConfig: {
    image: 'img/og-image.png',
    colorMode: {
      defaultMode: 'dark',
      respectPrefersColorScheme: true,
    },
    navbar: {
      title: 'freemocap',
      logo: {
        alt: 'freemocap Logo',
        src: 'img/logo.svg',
      },
      items: [
        { type: 'docSidebar', sidebarId: 'docsSidebar', position: 'left', label: 'Docs' },
        { to: '/blog', label: 'Blog', position: 'left' },
        { to: '/roadmap', label: 'Roadmap', position: 'left' },
        { href: 'https://github.com/freemocap/freemocap', label: 'Code', position: 'right' },
      ],
    },
    footer: {
      style: 'dark',
      links: [
        {
          title: 'Documentation',
          items: [{ label: 'Getting Started', to: '/docs/intro' }],
        },
        {
          title: 'Community',
          items: [
            { label: 'Discord', href: 'https://discord.gg/freemocap' },
            { label: 'Source Code', href: 'https://github.com/freemocap/freemocap' },
            { label: 'FreeMoCap', href: 'https://freemocap.org' },
          ],
        },
        {
          title: 'More',
          items: [
            { label: 'Blog', to: '/blog' },
            { label: 'Website', href: 'https://freemocap.org/' },
          ],
        },
      ],
      copyright: `Copyright © ${new Date().getFullYear()} FreeMoCap Foundation. Built with <a href="https://github.com/freemocap/skellydocs" target="_blank" rel="noopener noreferrer">SkellyDocs</a>.`,
    },
    prism: {
      theme: prismThemes.github,
      darkTheme: prismThemes.dracula,
      additionalLanguages: ['bash', 'json', 'python', 'typescript'],
    },
    mermaid: {
      theme: { light: 'neutral', dark: 'dark' },
    },
  },
};

export default config;
