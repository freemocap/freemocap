import type { SkellyDocsConfig } from '@freemocap/skellydocs';

const config: SkellyDocsConfig = {
  hero: {
    title: 'freemocap',
    accentedSuffix: 'freemocap',
    subtitle: 'Part of the FreeMoCap ecosystem',
    tagline: 'Shared Docusaurus theme, components, and CLI for FreeMoCap docs sites',
    logoSrc: '/freemocap/img/logo.svg',
    parentProject: {
      name: 'FreeMoCap',
      url: 'https://freemocap.org',
    },
    ctaButtons: [
      { label: 'Get Started', to: '/docs/intro', variant: 'primary' },
      { label: 'View on GitHub', to: 'https://github.com/freemocap/freemocap', variant: 'secondary' },
    ],
  },

  features: [
    {
      id: 'theme-components',
      icon: '🧩',
      title: 'Theme Components',
      description: 'Pre-built React components shared across all FreeMoCap docs sites.',
      summary: (
        <>
          IndexPage, RoadmapPage, Tip tooltips, AiGeneratedBanner, LinkedIssues,
          and more — all composable and configurable.
        </>
      ),
      issues: [],
      docPath: 'intro',
    },
    {
      id: 'cli-scaffolder',
      icon: '⚡',
      title: 'CLI Scaffolder',
      description: 'One command to create a fully wired docs site.',
      summary: (
        <>
          Run <code>npx @freemocap/skellydocs init</code> to scaffold a complete
          Docusaurus site with theme, config, and example content.
        </>
      ),
      issues: [],
      docPath: 'intro',
    },
    {
      id: 'design-tokens',
      icon: '🎨',
      title: 'CSS Design Tokens',
      description: 'Consistent theming via --sk-* CSS custom properties.',
      summary: (
        <>
          Override <code>--sk-accent</code> to give each project its own color
          identity while keeping a consistent dark-theme look.
        </>
      ),
      issues: [],
      docPath: 'intro',
    },
  ],
  guarantees: [],
  guaranteeIssues: [],
  guaranteesConfig: {
    title: (
      <>
        Every FreeMoCap docs site gets these{' '}
        <span style={{ color: 'var(--sk-accent)' }}>guarantees</span>:
      </>
    ),
    items: [
      'Consistent dark-theme design across all sub-projects',
      'Zero-config landing page with hero, features, and guarantees',
      'Live GitHub roadmap with filtering, sorting, and caching',
      'Fully composable — use the whole page or pick individual sections',
    ],
    issues: [],
  },


  projectBoardUrl: 'https://github.com/orgs/freemocap/projects/34',
};

export default config;
