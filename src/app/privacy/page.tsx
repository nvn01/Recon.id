import { permanentRedirect } from "next/navigation";

export default function LegacyPrivacyPage() {
  permanentRedirect("/privacy-policy");
}
