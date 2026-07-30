import { useEffect, useRef, useState } from "react";
import { PauseIcon, PlayIcon } from "./icons";

interface AudioPlayerProps {
  src: string;
}

function formatTime(seconds: number): string {
  if (!Number.isFinite(seconds)) return "0:00";
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export default function AudioPlayer({ src }: AudioPlayerProps) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);

  useEffect(() => {
    setIsPlaying(false);
    setCurrentTime(0);
    setDuration(0);
  }, [src]);

  const playedPct = duration > 0 ? `${Math.min(100, (currentTime / duration) * 100)}%` : "0%";

  function togglePlay() {
    const audio = audioRef.current;
    if (!audio) return;
    if (audio.paused) {
      audio.play();
    } else {
      audio.pause();
    }
  }

  function seek(e: React.MouseEvent<HTMLDivElement>) {
    const audio = audioRef.current;
    if (!audio || duration === 0) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const ratio = Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width));
    audio.currentTime = ratio * duration;
  }

  return (
    <div style={{ marginTop: "var(--space-3)", display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
      <audio
        ref={audioRef}
        src={src}
        preload="metadata"
        onPlay={() => setIsPlaying(true)}
        onPause={() => setIsPlaying(false)}
        onEnded={() => setIsPlaying(false)}
        onLoadedMetadata={(e) => setDuration(e.currentTarget.duration)}
        onTimeUpdate={(e) => setCurrentTime(e.currentTarget.currentTime)}
      />
      <button
        type="button"
        className="btn btn-ghost btn-icon"
        aria-label={isPlaying ? "Pause answer" : "Play answer"}
        style={{ width: 28, height: 28 }}
        onClick={togglePlay}
      >
        {isPlaying ? <PauseIcon /> : <PlayIcon />}
      </button>
      <div
        style={{ flex: 1, height: 6, background: "var(--color-neutral-300)", borderRadius: 2, position: "relative", cursor: "pointer" }}
        onClick={seek}
      >
        <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: playedPct, background: "var(--color-accent-700)", borderRadius: 2 }} />
      </div>
      <span style={{ fontSize: 11, opacity: 0.55, minWidth: 44, textAlign: "right" }}>
        {formatTime(currentTime)} / {formatTime(duration)}
      </span>
    </div>
  );
}
