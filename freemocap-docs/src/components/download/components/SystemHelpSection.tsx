import { SYSTEM_HELP_SECTIONS } from '../data/systemHelp';
import CollapsibleSection from './CollapsibleSection';
import styles from '../DownloadPage.module.css';

export default function SystemHelpSection() {
  return (
    <div className={styles.systemHelp}>
      <CollapsibleSection label="Not sure what system you have?" variant="help">
        <div className={styles.helpContent}>
          {SYSTEM_HELP_SECTIONS.map((section, i) => (
            <div key={i} className={styles.helpSection}>
              <div className={styles.helpSectionTitle}>
                <span className={styles.helpIcon}>{section.icon}</span>
                {section.title}
              </div>
              {section.content.map((block, j) => {
                if (block.type === 'paragraph') {
                  return (
                    <p
                      key={j}
                      dangerouslySetInnerHTML={{ __html: block.text! }}
                    />
                  );
                }
                return (
                  <ul key={j}>
                    {block.items!.map((item, k) => (
                      <li
                        key={k}
                        dangerouslySetInnerHTML={{ __html: item }}
                      />
                    ))}
                  </ul>
                );
              })}
            </div>
          ))}
        </div>
      </CollapsibleSection>
    </div>
  );
}
