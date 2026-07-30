import type { Language, Strings } from "../i18n";

interface SettingsViewProps {
  t: Strings;
  language: Language;
  onLanguageChange: (language: Language) => void;
}

export default function SettingsView({ t, language, onLanguageChange }: SettingsViewProps) {
  return (
    <div className="m-scroll" style={{ flex: 1, overflow: "auto", padding: "var(--space-8) var(--space-6)" }}>
      <div style={{ maxWidth: 560, margin: "0 auto" }}>
        <h1 style={{ fontSize: 34, margin: "0 0 var(--space-2)" }}>{t.settingsTitle}</h1>
        <p style={{ opacity: 0.65, margin: "0 0 var(--space-6)" }}>{t.settingsSubtitle}</p>

        <div className="card" style={{ padding: "var(--space-6)", gap: "var(--space-4)" }}>
          <div className="field" style={{ margin: 0 }}>
            <label id="lang-label">{t.langLabel}</label>
            <div className="seg" role="radiogroup" aria-labelledby="lang-label">
              <label className="seg-opt">
                <input type="radio" name="lang" checked={language === "en"} onChange={() => onLanguageChange("en")} />
                English
              </label>
              <label className="seg-opt">
                <input type="radio" name="lang" checked={language === "zh"} onChange={() => onLanguageChange("zh")} />
                中文
              </label>
            </div>
          </div>
          <p style={{ fontSize: 12, opacity: 0.55, margin: 0 }}>{t.langDesc}</p>
        </div>
      </div>
    </div>
  );
}
