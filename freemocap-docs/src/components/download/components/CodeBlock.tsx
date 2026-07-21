import { useState, useCallback } from 'react';
import type { CodeLine } from '../data/installInstructions';
import styles from '../DownloadPage.module.css';

interface CodeBlockProps {
  lines: CodeLine[];
}

export default function CodeBlock({ lines }: CodeBlockProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(() => {
    const commands = lines
      .filter(l => l.type === 'prompt')
      .map(l => l.content)
      .join('\n');
    navigator.clipboard.writeText(commands).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }, [lines]);

  return (
    <div className={styles.codeBlock}>
      <button
        className={`${styles.copyBtn} ${copied ? styles.copyBtnCopied : ''}`}
        onClick={handleCopy}
      >
        {copied ? 'Copied!' : 'Copy'}
      </button>
      {lines.map((line, i) => {
        if (line.type === 'comment') {
          return (
            <span key={i}>
              <span className={styles.comment}>{line.content}</span>
              {'\n'}
            </span>
          );
        }
        if (line.type === 'prompt') {
          return (
            <span key={i}>
              <span className={styles.prompt}>{line.promptChar || '$'}</span>
              {' '}
              {line.content}
              {'\n'}
            </span>
          );
        }
        // text (empty line / spacer)
        return <span key={i}>{line.content}{'\n'}</span>;
      })}
    </div>
  );
}
