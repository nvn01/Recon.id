import { permanentRedirect } from "next/navigation";

import { siteConfig } from "~/lib/site";

export default function Home() {
  permanentRedirect(siteConfig.homePath);
}
