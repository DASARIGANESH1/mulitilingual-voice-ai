"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

export interface MicrophoneState {
  isRecording: boolean;
  durationSec: number;
  audioBlob: Blob | null;
  errorCode: MicrophoneErrorCode | null;
  errorMessage: string;
  requestingPermission: boolean;
}

export type MicrophoneErrorCode =
  | "mic_not_supported"
  | "mic_permission_denied"
  | "mic_no_device"
  | "mic_start_failed"
  | "mic_data_unavailable";

export interface UseMicrophoneResult extends MicrophoneState {
  startRecording: () => Promise<void>;
  stopRecording: () => Promise<Blob | null>;
  reset: () => void;
}


// ============================================================================
// MIME TYPES
// ============================================================================

const MIME_CANDIDATES = [
  "audio/webm;codecs=opus",
  "audio/webm",
  "audio/ogg;codecs=opus",
  "audio/mp4",
  "audio/aac",
];

const MIN_RECORDING_SECONDS = 1;

function pickMimeType(): string | undefined {
  if (
    typeof window === "undefined" ||
    typeof MediaRecorder === "undefined"
  ) {
    return undefined;
  }

  for (const mime of MIME_CANDIDATES) {
    try {
      if (MediaRecorder.isTypeSupported(mime)) {
        return mime;
      }
    } catch {
      // Continue trying the next format.
    }
  }

  return undefined;
}


// ============================================================================
// HOOK
// ============================================================================

export function useMicrophone(): UseMicrophoneResult {
  const [isRecording, setIsRecording] = useState(false);
  const [durationSec, setDurationSec] = useState(0);
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null);

  const [errorCode, setErrorCode] =
    useState<MicrophoneErrorCode | null>(null);

  const [errorMessage, setErrorMessage] = useState("");

  const [requestingPermission, setRequestingPermission] =
    useState(false);

  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  const chunksRef = useRef<Blob[]>([]);

  const mimeRef = useRef<string | undefined>(undefined);

  const timerRef =
    useRef<ReturnType<typeof setInterval> | null>(null);

  const durationRef = useRef(0);

  const startedAtRef = useRef<number>(0);

  const stoppingRef = useRef(false);


  // ==========================================================================
  // STOP STREAM
  // ==========================================================================

  const stopStream = useCallback(() => {
    const stream = streamRef.current;

    if (!stream) {
      return;
    }

    for (const track of stream.getTracks()) {
      try {
        track.stop();
      } catch {
        // Ignore cleanup errors.
      }
    }

    streamRef.current = null;
  }, []);


  // ==========================================================================
  // STOP TIMER
  // ==========================================================================

  const stopTimer = useCallback(() => {
    if (timerRef.current !== null) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, []);


  // ==========================================================================
  // RESET
  // ==========================================================================

  const reset = useCallback(() => {
    durationRef.current = 0;
    setAudioBlob(null);
    setErrorCode(null);
    setErrorMessage("");
    setDurationSec(0);
  }, []);


  // ==========================================================================
  // START RECORDING
  // ==========================================================================

  const startRecording = useCallback(async () => {
    if (isRecording || recorderRef.current) {
      return;
    }

    setErrorCode(null);
    setErrorMessage("");
    setAudioBlob(null);
    durationRef.current = 0;
    setDurationSec(0);
    setRequestingPermission(true);

    if (
      typeof window === "undefined" ||
      !navigator.mediaDevices?.getUserMedia
    ) {
      setRequestingPermission(false);

      setErrorCode("mic_not_supported");

      setErrorMessage(
        "Microphone capture is not supported by this browser.",
      );

      return;
    }

    if (typeof MediaRecorder === "undefined") {
      setRequestingPermission(false);

      setErrorCode("mic_not_supported");

      setErrorMessage(
        "MediaRecorder is not supported by this browser.",
      );

      return;
    }


    // =========================================================================
    // MICROPHONE CAPTURE
    // =========================================================================

    let stream: MediaStream;

    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          // Mono is preferable for speech recognition.
          channelCount: {
            ideal: 1,
          },

          // Browser-level speech processing.
          echoCancellation: {
            ideal: true,
          },

          noiseSuppression: {
            ideal: true,
          },

          autoGainControl: {
            ideal: true,
          },
        },
      });
    } catch (error: unknown) {
      setRequestingPermission(false);

      const name =
        error instanceof DOMException
          ? error.name
          : "";

      if (
        name === "NotAllowedError" ||
        name === "SecurityError"
      ) {
        setErrorCode("mic_permission_denied");

        setErrorMessage(
          "Microphone permission was denied. Allow microphone access and try again.",
        );

        return;
      }

      if (
        name === "NotFoundError" ||
        name === "OverconstrainedError"
      ) {
        setErrorCode("mic_no_device");

        setErrorMessage(
          "No suitable microphone was found.",
        );

        return;
      }

      setErrorCode("mic_start_failed");

      setErrorMessage(
        error instanceof Error
          ? error.message
          : "Could not start the microphone.",
      );

      return;
    }


    // =========================================================================
    // MICROPHONE DIAGNOSTICS
    // =========================================================================

    const audioTrack = stream.getAudioTracks()[0];

    if (!audioTrack) {
      setRequestingPermission(false);

      for (const track of stream.getTracks()) {
        track.stop();
      }

      setErrorCode("mic_no_device");

      setErrorMessage(
        "The browser did not provide an audio microphone track.",
      );

      return;
    }

    const settings = audioTrack.getSettings();

    durationRef.current = 0;

    console.groupCollapsed(
      "%c🎤 Multilingual Voice AI — Microphone",
      "font-weight:bold;",
    );

    console.log("Device:", audioTrack.label);

    console.log("Settings:", {
      sampleRate: settings.sampleRate,
      sampleSize: settings.sampleSize,
      channelCount: settings.channelCount,
      echoCancellation: settings.echoCancellation,
      noiseSuppression: settings.noiseSuppression,
      autoGainControl: settings.autoGainControl,
    });

    if (typeof audioTrack.getCapabilities === "function") {
      console.log(
        "Capabilities:",
        audioTrack.getCapabilities(),
      );
    }

    console.log(
      "Supported constraints:",
      navigator.mediaDevices.getSupportedConstraints(),
    );

    console.groupEnd();


    // =========================================================================
    // MIME
    // =========================================================================

    const mimeType = pickMimeType();

    mimeRef.current = mimeType;

    console.log(
      "🎙️ Selected recording MIME:",
      mimeType ?? "browser default",
    );


    // =========================================================================
    // MEDIA RECORDER
    // =========================================================================

    let recorder: MediaRecorder;

    try {
      const options: MediaRecorderOptions = {
        audioBitsPerSecond: 128_000,
      };

      if (mimeType) {
        options.mimeType = mimeType;
      }

      recorder = new MediaRecorder(
        stream,
        options,
      );  
    } catch (error: unknown) {
      for (const track of stream.getTracks()) {
        track.stop();
      }

      setRequestingPermission(false);

      setErrorCode("mic_start_failed");

      setErrorMessage(
        error instanceof Error
          ? error.message
          : "Could not initialize the audio recorder.",
      );

      return;
    }


    streamRef.current = stream;

    chunksRef.current = [];

    stoppingRef.current = false;


    // =========================================================================
    // DATA
    // =========================================================================

    recorder.ondataavailable = (event: BlobEvent) => {
      if (
        event.data &&
        event.data.size > 0
      ) {
        chunksRef.current.push(event.data);
      }
    };


    // =========================================================================
    // ERROR
    // =========================================================================

    recorder.onerror = () => {
      console.error(
        "❌ MediaRecorder error",
      );

      setErrorCode("mic_data_unavailable");

      setErrorMessage(
        "The microphone recording failed. Please try again.",
      );

      setIsRecording(false);

      stopTimer();
      stopStream();

      recorderRef.current = null;
    };


    // =========================================================================
    // STOP
    // =========================================================================

    recorder.onstop = () => {
      // The actual Blob is resolved by stopRecording().
    };


    recorderRef.current = recorder;

    startedAtRef.current = Date.now();

    setRequestingPermission(false);

    try {
      // Small timeslice allows data to arrive progressively.
      recorder.start(250);
    } catch (error: unknown) {
      recorderRef.current = null;

      stopStream();

      setErrorCode("mic_start_failed");

      setErrorMessage(
        error instanceof Error
          ? error.message
          : "Could not start recording.",
      );

      return;
    }

    setIsRecording(true);


    // =========================================================================
    // TIMER
    // =========================================================================

    timerRef.current = setInterval(() => {
      const elapsed =
        Math.floor(
          (Date.now() - startedAtRef.current) /
            1000,
        );

      durationRef.current = elapsed;
      setDurationSec(elapsed);
    }, 250);

  }, [
    isRecording,
    stopStream,
    stopTimer,
  ]);


  // ==========================================================================
  // STOP RECORDING
  // ==========================================================================

  const stopRecording = useCallback(async () => {
    stopTimer();

    const recorder = recorderRef.current;

    if (
      !recorder ||
      stoppingRef.current
    ) {
      return null;
    }

    stoppingRef.current = true;


    const finalBlob =
      await new Promise<Blob | null>(
        (resolve) => {

          const finish = () => {
            const chunks =
              chunksRef.current;

            chunksRef.current = [];

            const mimeType =
              mimeRef.current ||
              chunks[0]?.type ||
              "audio/webm";

            if (chunks.length === 0) {
              resolve(null);
              return;
            }

            const blob = new Blob(
              chunks,
              {
                type: mimeType,
              },
            );

            resolve(blob);
          };


          recorder.addEventListener(
            "stop",
            finish,
            {
              once: true,
            },
          );


          try {
            if (
              recorder.state !==
              "inactive"
            ) {
              recorder.stop();
            } else {
              finish();
            }
          } catch {
            resolve(null);
          }
        },
      );


    setIsRecording(false);

    recorderRef.current = null;

    stopStream();

    stoppingRef.current = false;


    if (!finalBlob || finalBlob.size === 0) {
      setErrorCode(
        "mic_data_unavailable",
      );

      setErrorMessage(
        "No usable audio was captured. Please speak again.",
      );

      return null;
    }

    if (
      durationRef.current < MIN_RECORDING_SECONDS ||
      finalBlob.size < 512
    ) {
      setErrorCode(
        "mic_data_unavailable",
      );

      setErrorMessage(
        "I couldn't hear a usable voice sample. Speak clearly for a moment and try again.",
      );

      return null;
    }


    console.log(
      "🎧 Final audio:",
      {
        type: finalBlob.type,
        size: finalBlob.size,
        durationSec: durationRef.current,
      },
    );


    setAudioBlob(finalBlob);

    return finalBlob;

  }, [
    stopStream,
    stopTimer,
  ]);


  // ==========================================================================
  // CLEANUP
  // ==========================================================================

  useEffect(() => {
    return () => {
      stopTimer();

      const recorder =
        recorderRef.current;

      if (
        recorder &&
        recorder.state !==
          "inactive"
      ) {
        try {
          recorder.stop();
        } catch {
          // Ignore cleanup errors.
        }
      }

      stopStream();

      recorderRef.current = null;
    };
  }, [
    stopStream,
    stopTimer,
  ]);


  // ==========================================================================
  // RETURN
  // ==========================================================================

  return useMemo(
    () => ({
      isRecording,
      durationSec,
      audioBlob,
      errorCode,
      errorMessage,
      requestingPermission,
      startRecording,
      stopRecording,
      reset,
    }),
    [
      isRecording,
      durationSec,
      audioBlob,
      errorCode,
      errorMessage,
      requestingPermission,
      startRecording,
      stopRecording,
      reset,
    ],
  );
}