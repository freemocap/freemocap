import type { GitHubAsset } from '../downloads';
import { formatBytes } from '../downloads';
import styles from '../DownloadPage.module.css';

interface LegacyReleaseViewProps {
  assets: GitHubAsset[];
  tagName: string;
}

export default function LegacyReleaseView({ assets, tagName }: LegacyReleaseViewProps) {
  // Filter out source code archives
  const downloadableAssets = assets.filter(
    a => !a.name.endsWith('.tar.gz') && !a.name.endsWith('.zip') || a.name.includes('freemocap'),
  );

  return (
    <div>
      <div className={styles.legacyNotice}>
        <span className={styles.legacyNoticeIcon}>{'\uD83D\uDCE6'}</span>
        <div>
          This release (<strong>{tagName}</strong>) predates our smart download
          page. Here are all available files &mdash; pick the one that matches
          your system.
        </div>
      </div>
      <div className={styles.legacyAssetList}>
        {downloadableAssets.map(asset => (
          <a
            key={asset.name}
            href={asset.browser_download_url}
            className={styles.legacyAsset}
          >
            <span className={styles.legacyAssetName}>{asset.name}</span>
            <span className={styles.legacyAssetSize}>
              {formatBytes(asset.size)}
            </span>
          </a>
        ))}
      </div>
    </div>
  );
}
