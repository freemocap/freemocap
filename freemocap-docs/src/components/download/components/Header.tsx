import styles from '../DownloadPage.module.css';

export default function Header() {
  return (
    <>
      <div className={styles.logoRow}>
        <a href="https://github.com/freemocap/freemocap" title="FreeMoCap on GitHub">
          <img
            className={styles.logoImg}
            src="https://raw.githubusercontent.com/freemocap/freemocap/main/shared/freemocap-logo/freemocap-logo.png"
            alt="FreeMoCap logo"
          />
        </a>
        <h1 className={styles.title}>
          Free<span className={styles.titleAccent}>MoCap</span>
        </h1>
      </div>

      <p className={styles.tagline}>
        Free, open-source markerless motion capture. Record with ordinary
        cameras and reconstruct full-body 3D movement &mdash; no suits, no
        markers, no expensive hardware. Learn more at{' '}
        <a href="https://freemocap.org">freemocap.org</a>.
      </p>

      <div className={styles.repoLinks}>
        <a href="https://github.com/freemocap/freemocap">GitHub</a>
        <span className={styles.repoSep}>&middot;</span>
        <a href="https://github.com/freemocap/freemocap/releases">
          Release Notes
        </a>
        <span className={styles.repoSep}>&middot;</span>
        <a href="https://github.com/freemocap/freemocap/blob/main/LICENSE">
          AGPL-3.0
        </a>
      </div>
    </>
  );
}
