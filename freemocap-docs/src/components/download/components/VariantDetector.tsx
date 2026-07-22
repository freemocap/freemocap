import type { VariantType } from '../downloads';
import { VARIANT_PILL_OPTIONS } from '../downloads';
import styles from '../DownloadPage.module.css';

interface VariantDetectorProps {
  variant: VariantType;
  detected: boolean;
  onSelectVariant: (variant: VariantType) => void;
}

export default function VariantDetector({ variant, detected, onSelectVariant }: VariantDetectorProps) {
  return (
    <div className={styles.detectRow}>
      <div className={styles.detected}>
        <span className={styles.dot} />
        {detected ? (
          <>Detected: <strong>NVIDIA GPU</strong></>
        ) : (
          <>No GPU detected, recommending <strong>CPU-only</strong></>
        )}
      </div>
      <div className={styles.osPillsWrap}>
        <span className={styles.wrongDetect}>Not right? Select a build:</span>
        <div className={styles.osPills}>
          {VARIANT_PILL_OPTIONS.map(pill => (
            <button
              key={pill.variant}
              className={`${styles.osPill} ${
                pill.variant === variant ? styles.osPillActive : ''
              }`}
              onClick={() => onSelectVariant(pill.variant)}
            >
              {pill.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
