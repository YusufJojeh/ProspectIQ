import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useVoiceInput } from "@/hooks/use-voice-input";

afterEach(() => {
  delete (window as unknown as Record<string, unknown>).SpeechRecognition;
  delete (window as unknown as Record<string, unknown>).webkitSpeechRecognition;
});

describe("useVoiceInput", () => {
  it("reports unsupported and no-ops when the Web Speech API is missing", () => {
    const onTranscript = vi.fn();
    const { result } = renderHook(() => useVoiceInput(onTranscript));
    expect(result.current.supported).toBe(false);
    expect(result.current.listening).toBe(false);
    act(() => result.current.toggle());
    expect(result.current.listening).toBe(false);
    expect(onTranscript).not.toHaveBeenCalled();
  });

  it("starts recognition and forwards the transcript when supported", () => {
    const startSpy = vi.fn(function (this: FakeRecognition) {
      this.onresult?.({
        results: { length: 1, 0: { 0: { transcript: "dentists in dubai" }, isFinal: true } },
      });
    });
    class FakeRecognition {
      lang = "";
      continuous = false;
      interimResults = false;
      onresult:
        | ((event: {
            results: { length: number; [i: number]: { 0: { transcript: string }; isFinal: boolean } };
          }) => void)
        | null = null;
      onerror: (() => void) | null = null;
      onend: (() => void) | null = null;
      start = startSpy;
      stop = vi.fn();
    }
    (window as unknown as Record<string, unknown>).SpeechRecognition = FakeRecognition;

    const onTranscript = vi.fn();
    const { result } = renderHook(() => useVoiceInput(onTranscript, "en-US"));
    expect(result.current.supported).toBe(true);

    act(() => result.current.toggle());
    expect(startSpy).toHaveBeenCalled();
    expect(onTranscript).toHaveBeenCalledWith("dentists in dubai");
  });
});
