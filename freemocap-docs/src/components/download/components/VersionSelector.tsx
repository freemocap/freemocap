import type { GitHubRelease } from '../data/downloads';
import styles from '../DownloadPage.module.css';

interface VersionSelectorProps {
  releases: GitHubRelease[];
  selectedTag: string;
  onSelectVersion: (tag: string) => void;
  isLoading: boolean;
}

export default function VersionSelector({
  releases,
  selectedTag,
  onSelectVersion,
  isLoading,
}: VersionSelectorProps) {
  if (isLoading || releases.length === 0) return null;

  return (
    <div className={styles.versionRow}>
      <label htmlFor="version-select">Version:</label>
      <select
        id="version-select"
        className={styles.versionSelect}
        value={selectedTag}
        onChange={e => onSelectVersion(e.target.value)}
      >
        {releases.map(r => (
          <option key={r.tag_name} value={r.tag_name}>
            {r.tag_name}
            {r === releases[0] ? ' (latest)' : ''}
            {r.prerelease ? ' · pre-release' : ''}
          </option>
        ))}
      </select>
    </div>
  );
}
