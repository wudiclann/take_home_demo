import { useRef } from "react";
import { MicIcon } from "./icons";

interface MicButtonProps {
  isRecording: boolean;
  onStart: () => void;
  onStop: (blob: Blob) => void;
  disabled?: boolean;
}

export default function MicButton({ isRecording, onStart, onStop, disabled }: MicButtonProps) {
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  async function handleClick() {
    if (isRecording) {
      mediaRecorderRef.current?.stop();
      return;
    }

    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (err) {
      console.error("Microphone access denied or unavailable", err);
      return;
    }

    const mimeType = MediaRecorder.isTypeSupported("audio/webm") ? "audio/webm" : "";
    const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
    chunksRef.current = [];

    recorder.ondataavailable = (e) => {
      if (e.data.size > 0) chunksRef.current.push(e.data);
    };
    recorder.onstop = () => {
      const blob = new Blob(chunksRef.current, { type: mimeType || "audio/webm" });
      stream.getTracks().forEach((track) => track.stop());
      onStop(blob);
    };

    mediaRecorderRef.current = recorder;
    recorder.start();
    onStart();
  }

  return (
    <button
      type="button"
      className="btn btn-ghost btn-icon"
      style={{
        width: 32,
        height: 32,
        ...(isRecording
          ? { borderColor: "var(--color-accent-600)", color: "var(--color-accent-700)", background: "var(--color-accent-100)" }
          : {}),
      }}
      aria-label="Toggle microphone"
      onClick={handleClick}
      disabled={disabled}
    >
      <MicIcon />
    </button>
  );
}
