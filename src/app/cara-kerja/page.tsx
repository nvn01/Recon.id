import { permanentRedirect } from "next/navigation";

export default function LegacyHowItWorksPage() {
  permanentRedirect("/about-us");
}
