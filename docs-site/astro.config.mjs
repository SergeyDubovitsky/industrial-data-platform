import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';

export default defineConfig({
  integrations: [
    starlight({
      title: 'Industrial Data Platform Docs',
      description:
        'Internal architecture, contract, and agent documentation for the Industrial Data Platform.',
      lastUpdated: true,
      tableOfContents: { minHeadingLevel: 2, maxHeadingLevel: 3 },
      sidebar: [
        { label: 'Start Here', slug: 'index' },
        {
          label: 'Architecture',
          items: [{ slug: 'architecture' }],
        },
        {
          label: 'Contracts',
          items: [{ slug: 'contracts' }],
        },
        {
          label: 'Agent Workflow',
          items: [{ slug: 'agents' }],
        },
        {
          label: 'Decisions',
          items: [{ slug: 'decisions' }],
        },
        {
          label: 'LikeC4',
          items: [{ slug: 'likec4' }],
        },
      ],
    }),
  ],
});
