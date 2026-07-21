import type { ReactNode } from 'react';
import type { DownloadEntry, OsNoteEntry } from '../downloads';
import type { InstructionBlock } from '../installInstructions';
import DownloadCard from './DownloadCard';
import CollapsibleSection from './CollapsibleSection';
import CodeBlock from './CodeBlock';
import OsNote from './OsNote';
import styles from '../DownloadPage.module.css';

type SectionVariant = 'primary' | 'secondary';

interface DownloadSectionProps {
  icon: string;
  title: string;
  subtitle: ReactNode;
  detailsLabel: string;
  detailsContent: string;
  recommended: DownloadEntry[];
  alternates?: DownloadEntry[];
  installInstructions: InstructionBlock[];
  baseUrl: string;
  variant: SectionVariant;
  noDetectMessage?: string;
  showTerminalTip?: boolean;
  terminalTipContent?: ReactNode;
  notes?: OsNoteEntry[];
}

export default function DownloadSection({
  icon,
  title,
  subtitle,
  detailsLabel,
  detailsContent,
  recommended,
  alternates,
  installInstructions,
  baseUrl,
  variant,
  noDetectMessage,
  showTerminalTip,
  terminalTipContent,
  notes,
}: DownloadSectionProps) {
  const blockClass =
    variant === 'primary' ? styles.sectionBlock : `${styles.sectionBlock} ${styles.sectionBlockSecondary}`;
  const cardVariant = variant === 'primary' ? 'recommended' : 'server-rec';

  return (
    <div className={blockClass}>
      <div className={styles.sectionHeader}>
        <div className={styles.sectionTitle}>
          <span className={styles.sectionTitleIcon}>{icon}</span> {title}
        </div>
        <div className={styles.sectionSubtitle}>{subtitle}</div>
        <CollapsibleSection label={detailsLabel} variant="details">
          <div
            className={styles.sectionDetailsContent}
            dangerouslySetInnerHTML={{ __html: detailsContent }}
          />
        </CollapsibleSection>
      </div>

      {notes && notes.map((note, i) => (
        <OsNote key={i} note={note} />
      ))}

      <div className={styles.downloads}>
        {recommended.length === 0 && noDetectMessage ? (
          <div className={styles.noDetect}>{noDetectMessage}</div>
        ) : (
          recommended.map(d => (
            <DownloadCard
              key={d.file}
              download={d}
              variant={cardVariant}
              baseUrl={baseUrl}
            />
          ))
        )}
      </div>

      {alternates && alternates.length > 0 && (
        <>
          <div className={styles.altFormatLabel}>Also available for your system</div>
          <div className={styles.downloads}>
            {alternates.map(d => (
              <DownloadCard
                key={d.file}
                download={d}
                variant="secondary"
                baseUrl={baseUrl}
              />
            ))}
          </div>
        </>
      )}

      {installInstructions.length > 0 && (
        <CollapsibleSection label="Install instructions" variant="details">
          <div className={styles.sectionDetailsContent}>
            {installInstructions.map((block, i) => {
              if (block.codeLines) {
                return <CodeBlock key={i} lines={block.codeLines} />;
              }
              return (
                <p
                  key={i}
                  dangerouslySetInnerHTML={{ __html: block.text! }}
                />
              );
            })}
            {showTerminalTip && terminalTipContent}
          </div>
        </CollapsibleSection>
      )}
    </div>
  );
}
