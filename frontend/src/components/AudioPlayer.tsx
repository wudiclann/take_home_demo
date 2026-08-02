import { useEffect, useRef, useState } from "react";
import { PauseIcon, PlayIcon } from "./icons";

interface AudioPlayerProps {
  src: string;
  autoPlay?: boolean;
}

function formatTime(seconds: number): string {
  if (!Number.isFinite(seconds)) return "0:00";
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export default function AudioPlayer({ src, autoPlay }: AudioPlayerProps) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);

  useEffect(() => {
    setIsPlaying(false);
    setCurrentTime(0);
    setDuration(0);
  }, [src]);

  // Each AudioPlayer instance is mounted once for a given message (new array
  // entry -> new key), so a mount-only autoplay is exactly "play once, when
  // this specific answer first appears" -- never replays on later re-renders.
  useEffect(() => {
    if (autoPlay) {
      audioRef.current?.play().catch(() => {
        // Autoplay-with-sound can still be blocked by the browser in some
        // cases (e.g. no prior user gesture on this origin) -- fail silently
        // and leave the manual play button as the fallback.
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const playedPct = duration > 0 && Number.isFinite(duration) ? `${Math.min(100, (currentTime / duration) * 100)}%` : "0%";

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
    if (!audio || duration === 0 || !Number.isFinite(duration)) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const ratio = Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width));
    audio.currentTime = ratio * duration;
  }

  function handleLoadedMetadata(e: React.SyntheticEvent<HTMLAudioElement>) {
    const audio = e.currentTarget;
    if (Number.isFinite(audio.duration)) {
      setDuration(audio.duration);
      return;
    }
    // MediaRecorder-produced webm/opus blobs (voice recordings) report duration as
    // Infinity here -- webm is a streaming container, so the real duration isn't
    // known until the browser scans to the end of the data. Seeking far past the
    // end forces that scan; the resulting timeupdate carries the real duration.
    audio.currentTime = 1e101;
    const onTimeUpdate = () => {
      audio.removeEventListener("timeupdate", onTimeUpdate);
      setDuration(audio.duration);
      audio.currentTime = 0;
    };
    audio.addEventListener("timeupdate", onTimeUpdate);
  }

  return (
    <div style={{ marginTop: "var(--space-3)", display: "flex", alignItems: "center", gap: "var(--space-2)", minWidth: 220 }}>
      <audio
        ref={audioRef}
        src={src}
        preload={autoPlay ? "auto" : "metadata"}
        onPlay={() => setIsPlaying(true)}
        onPause={() => setIsPlaying(false)}
        onEnded={() => setIsPlaying(false)}
        onLoadedMetadata={handleLoadedMetadata}
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