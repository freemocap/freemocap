import type { DownloadEntry } from '../data/downloads';
import DownloadCard from './DownloadCard';
import CollapsibleSection from './CollapsibleSection';
import styles from '../DownloadPage.module.css';

interface AllPlatformsSectionProps {
  otherApp: DownloadEntry[];
  otherServer: DownloadEntry[];
  baseUrl: string;
  defaultOpen?: boolean;
}

export default function AllPlatformsSection({
  otherApp,
  otherServer,
  baseUrl,
  defaultOpen = false,
}: AllPlatformsSectionProps) {
  if (otherApp.length === 0 && otherServer.length === 0) return null;

  return (
    <CollapsibleSection
      label="All platforms & formats"
      variant="toggle"
      defaultOpen={defaultOpen}
    >
      {otherApp.length > 0 && (
        <>
          <div className={styles.sectionLabel} style={{ marginTop: 8 }}>
            App Installer &mdash; other platforms
          </div>
          <div className={styles.downloads}>
            {otherApp.map(d => (
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
      {otherServer.length > 0 && (
        <>
          <div className={styles.sectionLabel} style={{ marginTop: 24 }}>
            Backend Server &mdash; other platforms
          </div>
          <div className={styles.downloads}>
            {otherServer.map(d => (
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
    </CollapsibleSection>
  );
}
