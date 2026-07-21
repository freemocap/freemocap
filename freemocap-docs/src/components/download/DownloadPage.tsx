import { useState, useMemo, useEffect } from 'react';
import type { OsType, ArchType } from './downloads';
import {
  DEFAULT_VERSION,
  getReleaseBaseUrl,
  buildAppDownloads,
  buildServerDownloads,
  enrichDownloadsWithAssets,
  matchesExpectedPattern,
  stripVersionPrefix,
  OS_NOTES,
} from './downloads';
import {
  getAppInstallInstructions,
  getServerInstallInstructions,
} from './installInstructions';
import { useSystemDetection } from './hooks/useSystemDetection';
import { useReleaseVersions } from './hooks/useReleaseVersions';

import Header from './components/Header';
import SystemDetector from './components/SystemDetector';
import SystemHelpSection from './components/SystemHelpSection';
import VersionSelector from './components/VersionSelector';
import DownloadSection from './components/DownloadSection';
import TerminalInstallSection from './components/TerminalInstallSection';
import AllPlatformsSection from './components/AllPlatformsSection';
import LegacyReleaseView from './components/LegacyReleaseView';
import TerminalTip from './components/TerminalTip';
import Footer from './components/Footer';
import styles from './DownloadPage.module.css';

export default function DownloadPage() {
  const detected = useSystemDetection();
  const { releases, isLoading: releasesLoading } = useReleaseVersions();

  // Selected system (seeded from detection, overridable via pills)
  const [selectedOs, setSelectedOs] = useState<OsType | 'unknown'>('unknown');
  const [selectedArch, setSelectedArch] = useState<ArchType>('x64');
  const [hasManuallySelected, setHasManuallySelected] = useState(false);

  // Sync detected system to selection (only if user hasn't manually picked)
  useEffect(() => {
    if (!hasManuallySelected && detected.os !== 'unknown') {
      setSelectedOs(detected.os);
      setSelectedArch(detected.arch);
    }
  }, [detected.os, detected.arch, hasManuallySelected]);

  const handleSelectSystem = (os: OsType, arch: ArchType) => {
    setSelectedOs(os);
    setSelectedArch(arch);
    setHasManuallySelected(true);
  };

  // Selected version (defaults to latest release or hardcoded)
  const [selectedTag, setSelectedTag] = useState<string>(`v${DEFAULT_VERSION}`);

  // Once releases load, default to the latest
  useEffect(() => {
    if (releases.length > 0 && !hasManualVersionSelection) {
      setSelectedTag(releases[0].tag_name);
    }
  }, [releases]);

  const [hasManualVersionSelection, setHasManualVersionSelection] = useState(false);
  const handleSelectVersion = (tag: string) => {
    setSelectedTag(tag);
    setHasManualVersionSelection(true);
  };

  // Determine current release data
  const selectedRelease = useMemo(
    () => releases.find(r => r.tag_name === selectedTag),
    [releases, selectedTag],
  );

  const version = stripVersionPrefix(selectedTag);
  const baseUrl = getReleaseBaseUrl(version);

  const isLegacy = useMemo(() => {
    if (!selectedRelease) return false;
    return !matchesExpectedPattern(selectedRelease.assets, version);
  }, [selectedRelease, version]);

  // Build download entries for the selected version
  const { appDownloads, serverDownloads } = useMemo(() => {
    let app = buildAppDownloads(version);
    let server = buildServerDownloads(version);

    if (selectedRelease) {
      app = enrichDownloadsWithAssets(app, selectedRelease.assets);
      server = enrichDownloadsWithAssets(server, selectedRelease.assets);
    }

    return { appDownloads: app, serverDownloads: server };
  }, [version, selectedRelease]);

  // Sort into recommended / alternate / other
  const { recApp, altApp, otherApp, recServer, otherServer } = useMemo(() => {
    const rA: typeof appDownloads = [];
    const aA: typeof appDownloads = [];
    const oA: typeof appDownloads = [];

    for (const d of appDownloads) {
      if (d.os === selectedOs && d.arch === selectedArch) {
        (d.recommended ? rA : aA).push(d);
      } else {
        oA.push(d);
      }
    }

    const rS: typeof serverDownloads = [];
    const oS: typeof serverDownloads = [];
    for (const d of serverDownloads) {
      if (d.os === selectedOs && d.arch === selectedArch) {
        rS.push(d);
      } else {
        oS.push(d);
      }
    }

    return { recApp: rA, altApp: aA, otherApp: oA, recServer: rS, otherServer: oS };
  }, [appDownloads, serverDownloads, selectedOs, selectedArch]);

  const osForInstructions = selectedOs === 'unknown' ? undefined : selectedOs;
  const appInstructions = osForInstructions
    ? getAppInstallInstructions(osForInstructions, selectedArch, version)
    : [];
  const serverInstructions = osForInstructions
    ? getServerInstallInstructions(osForInstructions, selectedArch, version)
    : [];

  // Filter OS notes for the selected system
  const activeNotes = OS_NOTES.filter(
    n => n.os === selectedOs && (n.arch === undefined || n.arch === selectedArch),
  );

  const noDetect = selectedOs === 'unknown';

  return (
    <div className={styles.downloadPage}>
      <div className={styles.glow} />
      <div className={styles.container}>
        <Header />

        <SystemDetector
          os={selectedOs}
          arch={selectedArch}
          onSelectSystem={handleSelectSystem}
        />

        <SystemHelpSection />

        <VersionSelector
          releases={releases}
          selectedTag={selectedTag}
          onSelectVersion={handleSelectVersion}
          isLoading={releasesLoading}
        />

        {isLegacy && selectedRelease ? (
          <LegacyReleaseView
            assets={selectedRelease.assets}
            tagName={selectedRelease.tag_name}
          />
        ) : (
          <>
            <DownloadSection
              icon={'\uD83D\uDC80\uD83D\uDCF8'}
              title="FreeMoCap App Installer"
              subtitle={
                <>
                  <strong>Recommended</strong> &mdash; this is what most people want
                </>
              }
              detailsLabel="What's included?"
              detailsContent="Desktop application with camera preview, recording controls, and settings. The backend server is already bundled inside &mdash; you don't need to download it separately."
              recommended={recApp}
              alternates={altApp}
              installInstructions={appInstructions}
              baseUrl={baseUrl}
              variant="primary"
              noDetectMessage={
                noDetect
                  ? 'Could not detect your OS. See all downloads below.'
                  : undefined
              }
              showTerminalTip={osForInstructions === 'linux'}
              terminalTipContent={
                osForInstructions && osForInstructions !== 'windows' ? (
                  <TerminalTip os={osForInstructions} />
                ) : undefined
              }
              notes={activeNotes}
            />

            <TerminalInstallSection
              os={selectedOs}
              arch={selectedArch}
              version={version}
              baseUrl={baseUrl}
            />

            <hr className={styles.sectionDivider} />

            <DownloadSection
              icon={'\u26A1'}
              title="FreeMoCap Backend Server"
              subtitle={
                <>
                  <strong>Advanced</strong> &mdash; headless machines, Raspberry Pi, API use
                </>
              }
              detailsLabel="When do I need this?"
              detailsContent="Just the camera backend server binary, no GUI. Useful for headless capture rigs, remote systems you connect to over a network, or building a custom client against the FreeMoCap API. <strong>You don't need this if you downloaded the App Installer above.</strong>"
              recommended={recServer}
              installInstructions={serverInstructions}
              baseUrl={baseUrl}
              variant="secondary"
              showTerminalTip={osForInstructions != null && osForInstructions !== 'windows'}
              terminalTipContent={
                osForInstructions && osForInstructions !== 'windows' ? (
                  <TerminalTip os={osForInstructions} />
                ) : undefined
              }
            />

            <AllPlatformsSection
              otherApp={otherApp}
              otherServer={otherServer}
              baseUrl={baseUrl}
              defaultOpen={noDetect}
            />
          </>
        )}

        <Footer />
      </div>
    </div>
  );
}
