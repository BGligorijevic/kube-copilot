import queue
from RealtimeSTT import AudioToTextRecorder


class TranscriptionService:
    """
    Manages the AudioToTextRecorder instance and transcription state.
    """

    def __init__(self, language: str, text_queue: queue.Queue, finished_text_queue: queue.Queue):
        self.language = language
        self.text_queue = text_queue
        self.finished_text_queue = finished_text_queue
        self._recorder = self._create_recorder()

    def _create_recorder(self) -> AudioToTextRecorder:
        """Creates a new AudioToTextRecorder instance."""
        return AudioToTextRecorder(
            model="nebi/whisper-large-v3-turbo-swiss-german-ct2",
            language=self.language,
            device="mps",
            compute_type="auto",
            on_realtime_transcription_update=self._get_on_realtime_text_update(),
            on_realtime_transcription_stabilized=self._get_on_transcription_finished(),
            realtime_model_type="tiny",
            enable_realtime_transcription=True,
            realtime_processing_pause=1 # Wait for a 1-second pause before stabilizing
        )

    def _get_on_realtime_text_update(self):
        """Returns a thread-safe callback for text updates."""

        def on_realtime_text_update(text: str):
            self.text_queue.put(text)

        return on_realtime_text_update

    def _get_on_transcription_finished(self):
        """Returns a thread-safe callback for finished text updates."""
        def on_transcription_finished(text: str):
            self.finished_text_queue.put(text)

        return on_transcription_finished

    def start(self):
        self._recorder.start()

    def stop(self):
        self._recorder.stop()
