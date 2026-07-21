import type { OsType, ArchType } from '../downloads';
import { OS_LABELS, archLabel, OS_PILL_OPTIONS } from '../downloads';
import styles from '../DownloadPage.module.css';

interface SystemDetectorProps {
  os: OsType | 'unknown';
  arch: ArchType;
  onSelectSystem: (os: OsType, arch: ArchType) => void;
}

export default function SystemDetector({ os, arch, onSelectSystem }: SystemDetectorProps) {
  return (
    <div className={styles.detectRow}>
      <div className={styles.detected}>
        <span className={styles.dot} />
        Detected: <strong>{OS_LABELS[os] ?? os} &middot; {archLabel(arch)}</strong>
      </div>
      <div className={styles.osPillsWrap}>
        <span className={styles.wrongDetect}>Not right? Select your system:</span>
        <div className={styles.osPills}>
          {OS_PILL_OPTIONS.map(pill => (
            <button
              key={`${pill.os}-${pill.arch}`}
              className={`${styles.osPill} ${
                pill.os === os && pill.arch === arch ? styles.osPillActive : ''
              }`}
              onClick={() => onSelectSystem(pill.os, pill.arch)}
            >
              {pill.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
