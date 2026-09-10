// AI-generated: 2026-09-10. Human review pending.
import type {ComponentProps, ReactElement} from 'react';
import Content from '@theme-original/DocItem/Content';
import {useDoc} from '@docusaurus/plugin-content-docs/client';
import {AiGeneratedBanner} from '@freemocap/skellydocs';
import styles from './styles.module.css';

export default function DocContent(props: ComponentProps<typeof Content>): ReactElement {
  const doc = useDoc();
  const frontMatter = doc.frontMatter as typeof doc.frontMatter & Record<string, unknown>;
  const status = frontMatter.plan_status;
  if (status === undefined) return <Content {...props} />;
  if (status !== 'ongoing' && status !== 'archived') {
    throw new Error(`Invalid plan_status: ${String(status)}`);
  }
  const archived = status === 'archived';
  return <>
    <aside className={styles.notice} aria-label={archived ? 'Archived work plan' : 'Ongoing work plan'}>
      <strong className={styles.heading}>{archived ? 'ARCHIVED WORK PLAN' : 'ONGOING WORK PLAN'}</strong>
      <p>{archived
        ? 'Historical material retained for reference. It does not describe the current implementation or an active commitment.'
        : 'Working notes and proposals. They may be incomplete, inaccurate, superseded, or abandoned. They are not current implementation documentation.'}</p>
      <dl className={styles.metadata}>
        <div><dt>Generated</dt><dd>{String(frontMatter.plan_generated ?? 'Not recorded')}</dd></div>
        <div><dt>Migrated into docs</dt><dd>{String(frontMatter.plan_migrated ?? 'Not applicable')}</dd></div>
        <div><dt>Implementation audit</dt><dd>{String(frontMatter.plan_audited ?? 'Not yet audited')}</dd></div>
      </dl>
    </aside>
    <AiGeneratedBanner generationType="ai-generated" humanCurated={false}
      generatedAt={typeof frontMatter.plan_generated === 'string' ? frontMatter.plan_generated : undefined}
      humanNotes="AI-assisted work material. Migration does not establish original authorship, verify technical claims, or constitute human review." />
    <Content {...props} />
  </>;
}
