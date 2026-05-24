export default function LanguageBadge({ lang = "en" }) {
  const isUrdu = lang === "ur";

  return (
    <span
      key={lang}
      className={`language-badge ${isUrdu ? "language-badge--ur" : "language-badge--en"}`}
      aria-live="polite"
    >
      {isUrdu ? "🇵🇰 اردو" : "🇬🇧 EN"}
    </span>
  );
}
