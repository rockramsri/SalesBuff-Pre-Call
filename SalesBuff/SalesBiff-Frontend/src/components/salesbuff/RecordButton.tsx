import { Mic, Square } from "lucide-react";

export function RecordButton({
  recording,
  onClick,
  disabled,
}: {
  recording: boolean;
  onClick: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      data-recording={recording}
      aria-pressed={recording}
      aria-label={recording ? "Stop recording" : "Start recording"}
      className="record-btn"
    >
      {recording ? <Square fill="currentColor" size={28} /> : <Mic size={34} strokeWidth={2.4} />}
    </button>
  );
}
