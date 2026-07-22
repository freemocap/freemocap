import type { DownloadEntry } from '../downloads';
import { downloadUrl, formatMeta } from '../downloads';
import styles from '../DownloadPage.module.css';

type CardVariant = 'recommended' | 'server-rec' | 'secondary';

interface DownloadCardProps {
  download: DownloadEntry;
  variant: CardVariant;
  version: string;
}

export default function DownloadCard({ download, variant, version }: DownloadCardProps) {
  const cardClasses = [styles.dlCard];
  if (variant === 'recommended') cardClasses.push(styles.dlCardRecommended);
  if (variant === 'server-rec') cardClasses.push(styles.dlCardServerRec, styles.dlCardServer);

  const btnClass =
    variant === 'recommended'
      ? styles.dlBtnPrimary
      : variant === 'server-rec'
        ? styles.dlBtnServer
        : styles.dlBtnSecondary;

  const badgeClass =
    variant === 'recommended'
      ? styles.badgeRec
      : variant === 'server-rec'
        ? styles.badgeServer
        : null;

  const badgeText =
    variant === 'recommended'
      ? 'recommended'
      : variant === 'server-rec'
        ? 'your system'
        : null;

  return (
    <a
      href={downloadUrl(download.file, download.os, version, download.variant)}
      className={cardClasses.join(' ')}
    >
      <div className={styles.dlInfo}>
        <div className={styles.dlName}>
          {download.label}
          {badgeClass && badgeText && (
            <span className={`${styles.badge} ${badgeClass}`}>{badgeText}</span>
          )}
        </div>
        <div className={styles.dlMeta}>{formatMeta(download)}</div>
      </div>
      <div className={styles.dlRight}>
        {download.size && <span className={styles.dlSize}>{download.size}</span>}
        <span className={`${styles.dlBtn} ${btnClass}`}>Download</span>
      </div>
    </a>
  );
}
