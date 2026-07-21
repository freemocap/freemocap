import Layout from '@theme/Layout';
import Head from '@docusaurus/Head';
import DownloadPage from '../components/download/DownloadPage';

export default function Download() {
  return (
    <Layout>
      <Head>
        <title>Download | FreeMoCap</title>
        <meta name="description" content="Download FreeMoCap" />
      </Head>
      <DownloadPage />
    </Layout>
  );
}
