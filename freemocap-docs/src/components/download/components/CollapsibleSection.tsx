import { useState, type ReactNode } from 'react';
import styles from '../DownloadPage.module.css';

type CollapsibleVariant = 'toggle' | 'details' | 'help' | 'terminal-tip';

interface CollapsibleSectionProps {
  label: string;
  children: ReactNode;
  defaultOpen?: boolean;
  variant?: CollapsibleVariant;
}

const TOGGLE_CLASS: Record<CollapsibleVariant, string> = {
  toggle: styles.toggleBtn,
  details: styles.sectionDetailsToggle,
  help: styles.systemHelpToggle,
  'terminal-tip': styles.terminalTipToggle,
};

const ARROW_SIZE: Record<CollapsibleVariant, string> = {
  toggle: styles.arrowMedium,
  details: styles.arrowSmall,
  help: styles.arrow,
  'terminal-tip': styles.arrowTiny,
};

export default function CollapsibleSection({
  label,
  children,
  defaultOpen = false,
  variant = 'toggle',
}: CollapsibleSectionProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  const toggleClass = TOGGLE_CLASS[variant];
  const arrowSize = ARROW_SIZE[variant];

  return (
    <>
      <button
        className={toggleClass}
        onClick={() => setIsOpen(prev => !prev)}
      >
        <span className={`${styles.arrow} ${arrowSize} ${isOpen ? styles.arrowOpen : ''}`}>
          &#9654;
        </span>{' '}
        {label}
      </button>
      {isOpen && children}
    </>
  );
}
