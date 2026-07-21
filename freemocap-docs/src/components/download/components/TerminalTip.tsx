import type { OsType } from '../downloads';
import { getTerminalTipContent } from '../installInstructions';
import CollapsibleSection from './CollapsibleSection';
import styles from '../DownloadPage.module.css';

interface TerminalTipProps {
  os: OsType;
}

export default function TerminalTip({ os }: TerminalTipProps) {
  const { openHow, promptChar } = getTerminalTipContent(os);

  return (
    <CollapsibleSection label="New to the terminal?" variant="terminal-tip">
      <div className={styles.terminalTipContent}>
        <p dangerouslySetInnerHTML={{ __html: openHow }} />
        <p>
          The{' '}
          <span dangerouslySetInnerHTML={{ __html: promptChar }} />{' '}
          symbol shown before each command is the <strong>prompt</strong> &mdash;
          it means &ldquo;type here.&rdquo; Don&rsquo;t type it yourself; just
          type the text that comes after it, then press <strong>Enter</strong>.
        </p>
        <p>
          The <strong>Copy</strong> button in the top-right of each code block
          copies only the commands (without the prompt), ready to paste.
        </p>
      </div>
    </CollapsibleSection>
  );
}
