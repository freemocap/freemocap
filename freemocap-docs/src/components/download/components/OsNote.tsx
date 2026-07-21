import { LinkedIssues } from '@freemocap/skellydocs';
import type { OsNoteEntry } from '../data/downloads';
import styles from '../DownloadPage.module.css';

const VARIANT_ICONS: Record<OsNoteEntry['variant'], string> = {
  warning: '\u26A0\uFE0F',
  info: '\u2139\uFE0F',
  tip: '\uD83D\uDCA1',
};

interface OsNoteProps {
  note: OsNoteEntry;
}

export default function OsNote({ note }: OsNoteProps) {
  const variantClass =
    note.variant === 'warning'
      ? styles.osNoteWarning
      : note.variant === 'info'
        ? styles.osNoteInfo
        : styles.osNoteTip;

  return (
    <div className={`${styles.osNote} ${variantClass}`}>
      <span className={styles.osNoteIcon}>{VARIANT_ICONS[note.variant]}</span>
      <div className={styles.osNoteContent}>
        <div className={styles.osNoteTitle}>{note.title}</div>
        <p dangerouslySetInnerHTML={{ __html: note.content }} />
        {note.issues && note.issues.length > 0 && (
          <LinkedIssues items={note.issues} defaultOpen />
        )}
      </div>
    </div>
  );
}
