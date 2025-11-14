from asyncio import Queue
from RealtimeSTT import AudioToTextRecorder


class TranscriptionService:
    """
    Manages the AudioToTextRecorder instance and transcription state.
    """

    def __init__(self, language: str, text_queue: Queue, finished_text_queue: Queue, device: str = "mps"):
        self.language = language
        self.text_queue = text_queue
        self.finished_text_queue = finished_text_queue
        self.device = device
        self._recorder: AudioToTextRecorder | None = None

    def _create_recorder(self) -> AudioToTextRecorder:
        """Creates a new AudioToTextRecorder instance."""
        print(f"TranscriptionService: Initializing recorder for language '{self.language}' with model 'nebi/whisper-large-v3-turbo-swiss-german-ct2' and device '{self.device}'.")
        return AudioToTextRecorder(
            model="nebi/whisper-large-v3-turbo-swiss-german-ct2",
            language=self.language,
            device=self.device,
            compute_type="auto",
            on_realtime_transcription_update=self._get_on_realtime_text_update(),
            on_realtime_transcription_stabilized=self._get_on_transcription_finished(),
            realtime_model_type="tiny",
            enable_realtime_transcription=True,
            realtime_processing_pause=1, # Wait for a 1-second pause before stabilizing
            no_log_file=True,
            spinner=False
        )

    def _get_on_realtime_text_update(self):
        """Returns a thread-safe callback for text updates."""

        def on_realtime_text_update(text: str):
            # print(f"TranscriptionService: Realtime update received: '{text}'")
            self.text_queue.put_nowait(text)

        return on_realtime_text_update

    def _get_on_transcription_finished(self):
        """Returns a thread-safe callback for finished text updates."""
        def on_transcription_finished(text: str):
            # print(f"TranscriptionService: Stabilized text received: '{text}'")
            self.finished_text_queue.put_nowait(text)

        return on_transcription_finished

    def start(self):
        print("TranscriptionService: Starting recorder.")
        if not self._recorder:
            self._recorder = self._create_recorder()
        self._recorder.start()

    def stop(self):
        """Stops and completely shuts down the recorder."""
        print("TranscriptionService: Stopping recorder.")
        self.shutdown()

    def shutdown(self):
        """Explicitly stops and deletes the recorder instance to free resources."""
        if hasattr(self, '_recorder') and self._recorder:
            self._recorder.stop()
            del self._recorder
            print("TranscriptionService: Recorder shut down.")
