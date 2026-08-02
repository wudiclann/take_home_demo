import { useEffect, useState } from "react";
import { clearOpenAiKey, getSettings, saveOpenAiKey, saveVoiceSettings, type SettingsOut } from "../api/client";
import type { Language, Strings } from "../i18n";
import { showToast } from "./Toast";

interface SettingsViewProps {
  t: Strings;
  language: Language;
  onLanguageChange: (language: Language) => void;
  onApiKeyChange: (isConfigured: boolean) => void;
}

const SPEED_OPTIONS = [0.75, 1, 1.25, 1.5];

function capitalize(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

function ClearIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  );
}

export default function SettingsView({ t, language, onLanguageChange, onApiKeyChange }: SettingsViewProps) {
  const [settings, setSettings] = useState<SettingsOut | null>(null);
  const [isEditingKey, setIsEditingKey] = useState(true);
  const [keyDraft, setKeyDraft] = useState("");
  const [isSavingKey, setIsSavingKey] = useState(false);
  const [isClearingKey, setIsClearingKey] = useState(false);
  const [voice, setVoice] = useState("alloy");
  const [speed, setSpeed] = useState(1.25);

  useEffect(() => {
    getSettings().then((s) => {
      setSettings(s);
      setIsEditingKey(!s.is_openai_key_configured);
      setVoice(s.tts_voice);
      setSpeed(s.tts_speed);
    });
  }, []);

  async function handleSaveKey() {
    const apiKey = keyDraft.trim();
    if (!apiKey || isSavingKey) return;
    setIsSavingKey(true);
    try {
      const updated = await saveOpenAiKey(apiKey);
      setSettings(updated);
      setIsEditingKey(false);
      setKeyDraft("");
      onApiKeyChange(updated.is_openai_key_configured);
      showToast(t.keySavedToast, "info");
    } catch (err) {
      showToast(err instanceof Error ? err.message : t.invalidKeyToast, "error");
    } finally {
      setIsSavingKey(false);
    }
  }

  async function handleClearKey() {
    if (isClearingKey || !window.confirm(t.confirmClearKey)) return;
    setIsClearingKey(true);
    try {
      const updated = await clearOpenAiKey();
      setSettings(updated);
      setIsEditingKey(true);
      onApiKeyChange(updated.is_openai_key_configured);
      showToast(t.keyClearedToast, "info");
    } catch (err) {
      showToast(err instanceof Error ? err.message : t.keyClearedToast, "error");
    } finally {
      setIsClearingKey(false);
    }
  }

  async function handleVoiceSettingsChange(nextVoice: string, nextSpeed: number) {
    setVoice(nextVoice);
    setSpeed(nextSpeed);
    try {
      await saveVoiceSettings(nextVoice, nextSpeed);
      showToast(t.voiceSettingsSavedToast, "info");
    } catch (err) {
      showToast(err instanceof Error ? err.message : t.voiceSettingsSavedToast, "error");
    }
  }

  return (
    <div className="m-scroll" style={{ flex: 1, overflow: "auto", padding: "var(--space-8) var(--space-6)" }}>
      <div style={{ maxWidth: 560, margin: "0 auto" }}>
        <h1 style={{ fontSize: 34, margin: "0 0 var(--space-2)" }}>{t.settingsTitle}</h1>
        <p style={{ opacity: 0.65, margin: "0 0 var(--space-6)" }}>{t.settingsSubtitle}</p>

        <div className="card" style={{ padding: "var(--space-6)", gap: "var(--space-4)" }}>
          <div className="field" style={{ margin: 0 }}>
            <label htmlFor="openai-key">{t.apiKeyLabel}</label>
            {isEditingKey ? (
              <input
                className="input"
                id="openai-key"
                type="password"
                placeholder={t.apiKeyPlaceholder}
                value={keyDraft}
                autoComplete="off"
                onChange={(e) => setKeyDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleSaveKey();
                }}
              />
            ) : (
              <div style={{ position: "relative" }}>
                <input
                  className="input"
                  id="openai-key"
                  type="text"
                  value={settings?.openai_api_key_masked ?? ""}
                  readOnly
                  disabled
                  style={{ paddingRight: 34 }}
                />
                <button
                  type="button"
                  aria-label={t.clearKeyBtn}
                  onClick={handleClearKey}
                  disabled={isClearingKey}
                  style={{
                    position: "absolute",
                    right: 8,
                    top: "50%",
                    transform: "translateY(-50%)",
                    width: 22,
                    height: 22,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    background: "none",
                    border: "none",
                    borderRadius: "var(--radius-sm)",
                    cursor: isClearingKey ? "default" : "pointer",
                    opacity: isClearingKey ? 0.4 : 0.55,
                    color: "var(--color-text)",
                  }}
                >
                  <ClearIcon />
                </button>
              </div>
            )}
          </div>
          <p style={{ fontSize: 12, opacity: 0.55, margin: 0 }}>{t.apiKeyDesc}</p>
          <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)" }}>
            {isEditingKey ? (
              <>
                <button type="button" className="btn btn-primary" onClick={handleSaveKey} disabled={!keyDraft.trim() || isSavingKey}>
                  {t.saveKeyBtn}
                </button>
                {settings?.is_openai_key_configured && (
                  <button
                    type="button"
                    className="btn btn-ghost"
                    onClick={() => {
                      setIsEditingKey(false);
                      setKeyDraft("");
                    }}
                  >
                    {t.cancelKeyChangeBtn}
                  </button>
                )}
              </>
            ) : (
              <>
                <button type="button" className="btn btn-secondary" onClick={() => setIsEditingKey(true)}>
                  {t.changeKeyBtn}
                </button>
                <span className="tag tag-accent">{t.keySavedTag}</span>
              </>
            )}
          </div>
        </div>

        <div className="card" style={{ padding: "var(--space-6)", gap: "var(--space-4)", marginTop: "var(--space-4)" }}>
          <div style={{ fontSize: 11, letterSpacing: "0.08em", textTransform: "uppercase", opacity: 0.55 }}>
            {t.voiceSectionLabel}
          </div>
          <div className="field" style={{ margin: 0 }}>
            <label htmlFor="tts-voice">{t.voiceFieldLabel}</label>
            <select
              className="input"
              id="tts-voice"
              value={voice}
              onChange={(e) => handleVoiceSettingsChange(e.target.value, speed)}
            >
              {(settings?.available_voices ?? [voice]).map((v) => (
                <option key={v} value={v}>
                  {capitalize(v)}
                </option>
              ))}
            </select>
          </div>
          <div className="field" style={{ margin: 0 }}>
            <label id="speed-label">{t.speedFieldLabel}</label>
            <div className="seg" role="radiogroup" aria-labelledby="speed-label">
              {SPEED_OPTIONS.map((s) => (
                <label className="seg-opt" key={s}>
                  <input
                    type="radio"
                    name="speed"
                    checked={speed === s}
                    onChange={() => handleVoiceSettingsChange(voice, s)}
                  />
                  {s}x
                </label>
              ))}
            </div>
          </div>
          <p style={{ fontSize: 12, opacity: 0.55, margin: 0 }}>{t.voiceSectionDesc}</p>
        </div>

        <div className="card" style={{ padding: "var(--space-6)", gap: "var(--space-4)", marginTop: "var(--space-4)" }}>
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