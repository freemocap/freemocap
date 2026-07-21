import styles from '../DownloadPage.module.css';

export default function Footer() {
  return (
    <div className={styles.note}>
      Part of the <a href="https://freemocap.org">FreeMoCap</a> project.
      Source code on{' '}
      <a href="https://github.com/freemocap/freemocap">GitHub</a>. Release
      notes and changelogs on the{' '}
      <a href="https://github.com/freemocap/freemocap/releases">Releases</a>{' '}
      page. Licensed under <code>AGPL-3.0</code>.
    </div>
  );
}
