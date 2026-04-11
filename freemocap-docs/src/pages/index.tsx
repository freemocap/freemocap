import { Redirect } from '@docusaurus/router';
export default function Home() {
  return <Redirect to="docs/intro" />;
}
// import { IndexPage } from '@freemocap/skellydocs';
// import config from '../../content.config';
//
// export default function Home() {
//   return <IndexPage config={config} />;
// }
