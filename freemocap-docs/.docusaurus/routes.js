import React from 'react';
import ComponentCreator from '@docusaurus/ComponentCreator';

export default [
  {
    path: '/freemocap/__docusaurus/debug',
    component: ComponentCreator('/freemocap/__docusaurus/debug', 'c73'),
    exact: true
  },
  {
    path: '/freemocap/__docusaurus/debug/config',
    component: ComponentCreator('/freemocap/__docusaurus/debug/config', 'b8e'),
    exact: true
  },
  {
    path: '/freemocap/__docusaurus/debug/content',
    component: ComponentCreator('/freemocap/__docusaurus/debug/content', 'f01'),
    exact: true
  },
  {
    path: '/freemocap/__docusaurus/debug/globalData',
    component: ComponentCreator('/freemocap/__docusaurus/debug/globalData', '307'),
    exact: true
  },
  {
    path: '/freemocap/__docusaurus/debug/metadata',
    component: ComponentCreator('/freemocap/__docusaurus/debug/metadata', '0dd'),
    exact: true
  },
  {
    path: '/freemocap/__docusaurus/debug/registry',
    component: ComponentCreator('/freemocap/__docusaurus/debug/registry', 'e3d'),
    exact: true
  },
  {
    path: '/freemocap/__docusaurus/debug/routes',
    component: ComponentCreator('/freemocap/__docusaurus/debug/routes', 'f43'),
    exact: true
  },
  {
    path: '/freemocap/blog',
    component: ComponentCreator('/freemocap/blog', '8b3'),
    exact: true
  },
  {
    path: '/freemocap/blog/archive',
    component: ComponentCreator('/freemocap/blog/archive', '16b'),
    exact: true
  },
  {
    path: '/freemocap/blog/tags',
    component: ComponentCreator('/freemocap/blog/tags', 'edc'),
    exact: true
  },
  {
    path: '/freemocap/blog/tags/welcome',
    component: ComponentCreator('/freemocap/blog/tags/welcome', 'a56'),
    exact: true
  },
  {
    path: '/freemocap/blog/welcome',
    component: ComponentCreator('/freemocap/blog/welcome', 'ff2'),
    exact: true
  },
  {
    path: '/freemocap/roadmap',
    component: ComponentCreator('/freemocap/roadmap', '208'),
    exact: true
  },
  {
    path: '/freemocap/docs',
    component: ComponentCreator('/freemocap/docs', '3cf'),
    routes: [
      {
        path: '/freemocap/docs',
        component: ComponentCreator('/freemocap/docs', '458'),
        routes: [
          {
            path: '/freemocap/docs',
            component: ComponentCreator('/freemocap/docs', '177'),
            routes: [
              {
                path: '/freemocap/docs/intro',
                component: ComponentCreator('/freemocap/docs/intro', '1bb'),
                exact: true,
                sidebar: "docsSidebar"
              },
              {
                path: '/freemocap/docs/notes/api-notes',
                component: ComponentCreator('/freemocap/docs/notes/api-notes', '2f4'),
                exact: true,
                sidebar: "docsSidebar"
              }
            ]
          }
        ]
      }
    ]
  },
  {
    path: '/freemocap/',
    component: ComponentCreator('/freemocap/', '8aa'),
    exact: true
  },
  {
    path: '*',
    component: ComponentCreator('*'),
  },
];
