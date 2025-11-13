import streamlit as st
import queue
import time
from dataclasses import dataclass, field
from transcription_service import TranscriptionService
from agent import AgentService


@dataclass
class AppState:
    """A dataclass to hold the application's state, managed in st.session_state."""
    is_listening: bool = False
    language: str = "de"
    conversation: list = field(default_factory=list)
    stabilized_text: str = ""
    last_agent_transcript: str = ""

    # Service-related state
    transcription_service: TranscriptionService | None = None
    agent_service: AgentService | None = None
    text_queue: queue.Queue = field(default_factory=queue.Queue)
    finished_text_queue: queue.Queue = field(default_factory=queue.Queue)


def get_state() -> AppState:
    """Initializes and retrieves the app state from Streamlit's session state."""
    if "app_state" not in st.session_state:
        st.session_state.app_state = AppState()
    return st.session_state.app_state


def _apply_custom_css():
    """Applies custom CSS for styling the Streamlit page."""
    st.markdown("""
        <style>
            .block-container {
                max-width: 1400px;
            }
            .stTextArea textarea {
                font-size: 1.2rem;
                line-height: 1.6;
            }
        </style>
    """, unsafe_allow_html=True)


def _stop_listening(state: AppState):
    """Stops the transcription service and updates the state."""
    state.is_listening = False
    if state.transcription_service:
        state.transcription_service.stop()


def _start_listening(state: AppState):
    """Resets state and services to begin a new listening session."""
    # Invalidate services to force re-creation.
    if state.transcription_service:
        state.transcription_service.shutdown()

    # Create a completely new state object for a clean session.
    st.session_state.app_state = AppState(language=state.language)
    new_state = get_state()

    # Services will be re-created on the next rerun, then we start listening.
    st.session_state.start_listening_requested = True
    st.rerun()


def render_header(state: AppState):
    """Renders the header, language selection, and start/stop button."""
    with st.container():
        _, col2, _ = st.columns([1, 2, 1])
        with col2:
            st.title("🎙️ KuBe Co-Pilot")

            language_code = st.radio(
                "Language",
                ("DE", "EN"),
                horizontal=True,
                index=0 if state.language == "de" else 1,
            ).lower()

            # Handle language change
            if language_code != state.language:
                _stop_listening(state)
                state.language = language_code
                # Invalidate services to force re-creation with the new language
                state.transcription_service = None
                state.agent_service = None
                st.rerun()

            if st.button(
                "Stop Listening" if state.is_listening else "Start Listening",
                use_container_width=True
            ):
                if state.is_listening:
                    _stop_listening(state)
                    st.rerun()
                else:
                    _start_listening(state)


def _ensure_services_are_running(state: AppState):
    """Initializes and starts services if they are not already running."""
    if state.agent_service is None or state.transcription_service is None:
        is_first_run = not st.session_state.get("services_initialized", False)

        def create_services():
            """Creates and assigns the transcription and agent services."""
            state.agent_service = AgentService(language=state.language)
            state.transcription_service = TranscriptionService(
                state.language,
                state.text_queue,
                state.finished_text_queue
            )
            st.session_state.services_initialized = True

        if is_first_run:
            with st.spinner("The app is loading, please wait..."):
                create_services()
        else:
            create_services()

    # If a start was requested, and services are ready, begin listening.
    if st.session_state.get("start_listening_requested", False):
        # Clear any stale items from queues before starting
        while not state.text_queue.empty(): state.text_queue.get()
        while not state.finished_text_queue.empty(): state.finished_text_queue.get()

        state.transcription_service.start()
        state.is_listening = True
        st.session_state.start_listening_requested = False  # Reset the flag
        st.info("Started listening.")
        st.rerun()


def process_transcription_updates(state: AppState):
    """
    Checks queues for new text, processes it, and calls the agent service.
    Returns True if the UI should be updated.
    """
    if not state.is_listening:
        return False

    new_chunk_received = False
    try:
        # Drain the real-time queue (currently not displayed, but good practice)
        while not state.text_queue.empty():
            state.text_queue.get_nowait()

        # Process stabilized text from the finished queue
        while not state.finished_text_queue.empty():
            new_full_transcript = state.finished_text_queue.get_nowait()
            if new_full_transcript != state.stabilized_text:
                state.stabilized_text = new_full_transcript
                new_chunk_received = True

        if new_chunk_received:
            # Identify the new part of the transcript to send to the agent
            new_transcript_chunk = state.stabilized_text[len(state.last_agent_transcript):].strip()

            if new_transcript_chunk and len(new_transcript_chunk.split()) > 2:
                history = state.conversation.copy()
                state.conversation.append(("user", new_transcript_chunk))
                response = state.agent_service.get_response(new_transcript_chunk, history)
                if response:
                    state.conversation.append(("agent", response))

            # Crucially, update the pointer for the last processed transcript
            state.last_agent_transcript = state.stabilized_text
            return True # Indicates a state change that requires a UI update

    except queue.Empty:
        # This is expected when no new text is available
        pass

    return False


def render_ui(state: AppState):
    """Renders the main UI components for transcription and insights."""
    col1, col2 = st.columns(2, gap="large")

    with col1:
        st.subheader("Transcript:")
        st.text_area(
            "Live Transcription",
            value=state.stabilized_text.strip(),
            height=800,
            label_visibility="collapsed",
        )

    with col2:
        st.subheader("Co-Pilot Insights:")
        chat_display = ""
        for speaker, text in state.conversation:
            if speaker == "agent":
                chat_display += f"{text}\n---\n"
        st.text_area(
            "Co-Pilot Display",
            value=chat_display,
            height=800,
            label_visibility="collapsed",
            disabled=True
        )


def main():
    """Main function to run the Streamlit application."""
    st.set_page_config(layout="centered")
    _apply_custom_css()

    state = get_state()

    render_header(state)
    _ensure_services_are_running(state)

    # Process any new text from the transcription service
    process_transcription_updates(state)

    # The UI is rendered on every run, reflecting the current state
    render_ui(state)

    # The core polling loop: if listening, schedule a rerun to check for new text
    if state.is_listening:
        time.sleep(0.1)
        st.rerun()


if __name__ == "__main__":
    main()
