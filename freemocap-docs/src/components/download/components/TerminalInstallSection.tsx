import type { OsType, ArchType, VariantType } from '../downloads';
import { getTerminalInstallBlocks } from '../installInstructions';
import CollapsibleSection from './CollapsibleSection';
import CodeBlock from './CodeBlock';
import TerminalTip from './TerminalTip';
import styles from '../DownloadPage.module.css';

interface TerminalInstallSectionProps {
  os: OsType | 'unknown';
  arch: ArchType;
  variant?: VariantType;
  version: string;
  baseUrl: string;
}

export default function TerminalInstallSection({
  os,
  arch,
  variant,
  version,
  baseUrl,
}: TerminalInstallSectionProps) {
  if (os === 'windows' || os === 'unknown') return null;

  const blocks = getTerminalInstallBlocks(os, arch, variant, version, baseUrl);
  if (blocks.length === 0) return null;

  return (
    <div>
      <CollapsibleSection label="Install from terminal" variant="toggle">
        <div className={styles.sectionLabel} style={{ marginTop: 8 }}>
          One-liner install from terminal
        </div>
        <p className={styles.installHint}>
          Download and run directly using <code>curl</code>. These pull from the
          GitHub Release.
        </p>
        {blocks.map((block, i) =>
          block.codeLines ? <CodeBlock key={i} lines={block.codeLines} /> : null,
        )}
        <TerminalTip os={os} />
      </CollapsibleSection>
    </div>
  );
}
