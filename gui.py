import streamlit as st
import queue
import time
from transcription_service import TranscriptionService
from agent import AgentService

# --- Constants ---

def handle_button_click():
    """Handles the logic for the 'Start/Stop Listening' button."""
    if st.session_state.is_listening:
        # This was a "Stop Listening" click
        st.session_state.is_listening = False
        if st.session_state.transcription_service:
            st.session_state.transcription_service.stop()

        st.rerun()
    else:
        # This was a "Start Listening" click
        # This is the single point where a new session is initiated.
        # We must clear ALL state here to guarantee a clean slate.

        # 1. Invalidate services to force re-creation.
        st.session_state.transcription_service = None
        st.session_state.agent_service = None

        # 2. Reset all text and conversation state.
        st.session_state.realtime_text = ""
        st.session_state.accumulated_text = ""
        st.session_state.stabilized_text = ""
        st.session_state.last_agent_transcript = ""
        st.session_state.conversation = []

        # 3. Set the flag to start listening after services are re-created.
        st.session_state.start_listening_requested = True
        st.rerun()

def main():
    """
    Main function to run the Streamlit application.
    """
    st.set_page_config(layout="centered")  # Use centered layout as a base

    # Inject custom CSS to set a custom max-width for the main container
    st.markdown("""
        <style>
            .block-container {
                max-width: 1400px;
            }
            /* Increase font size for text areas */
            .stTextArea textarea {
                font-size: 1.2rem;
                line-height: 1.6;
            }
        </style>
    """, unsafe_allow_html=True)

    # Initialize session state variables
    if "is_listening" not in st.session_state:
        st.session_state.is_listening = False
    if "start_listening_requested" not in st.session_state:
        st.session_state.start_listening_requested = False
    if "transcription_service" not in st.session_state:
        st.session_state.transcription_service = None
    if "language" not in st.session_state:
        st.session_state.language = "de"
    if "agent_service" not in st.session_state:
        st.session_state.agent_service = None
    if "accumulated_text" not in st.session_state:
        st.session_state.accumulated_text = ""
    if "stabilized_text" not in st.session_state:
        st.session_state.stabilized_text = ""
    if "last_agent_transcript" not in st.session_state:
        st.session_state.last_agent_transcript = ""
    if "conversation" not in st.session_state:
        st.session_state.conversation = []

    # --- UI Components ---
    # --- Centered Header ---
    with st.container():
        # Use columns to center the radio button and the main button
        _, col2, _ = st.columns([1, 2, 1])
        with col2:
            st.title("🎙️ KuBe Co-Pilot")

            language_code = st.radio(
                "Language",
                ("DE", "EN"),
                horizontal=True,
                index=0 if st.session_state.language == "de" else 1,
            ).lower()

            # Create the button and define its behavior
            if st.button(
                "Stop Listening" if st.session_state.is_listening else "Start Listening",
                use_container_width=True
            ):
                handle_button_click()

    # --- Service Initialization and Session Management ---

    # If language changed, reset the transcriber
    if language_code != st.session_state.language:
        st.session_state.language = language_code
        # Invalidate services to force re-creation with the new language
        st.session_state.transcription_service = None
        st.session_state.agent_service = None
        # Stop listening if it was active
        st.session_state.is_listening = False
        st.rerun()

    # Load the transcriber model on first run
    if st.session_state.transcription_service is None:
        # Determine if this is the very first run to decide if a spinner is needed.
        # The spinner is only for the initial model loading.
        is_first_run = not st.session_state.get("services_initialized", False)

        def create_services():
            """Function to create and initialize services."""
            st.session_state.agent_service = AgentService(language=st.session_state.language)
            st.session_state.text_queue = queue.Queue()
            st.session_state.finished_text_queue = queue.Queue()
            st.session_state.transcription_service = TranscriptionService(
                st.session_state.language,
                st.session_state.text_queue,
                st.session_state.finished_text_queue
            )
            st.session_state.services_initialized = True

        if is_first_run:
            with st.spinner("The app is loading, please wait..."):
                create_services()
        else:
            # On subsequent re-initializations, create services without a spinner.
            create_services()

    # If a start was requested, now that services are fresh, we can begin.
    if st.session_state.start_listening_requested:
        # Ensure queues are empty before starting
        if "text_queue" in st.session_state:
            while not st.session_state.text_queue.empty(): st.session_state.text_queue.get()
            while not st.session_state.finished_text_queue.empty(): st.session_state.finished_text_queue.get()

        st.session_state.transcription_service.start()
        st.session_state.is_listening = True
        st.session_state.start_listening_requested = False # Reset the flag
        st.info("Started listening.")
        st.rerun()

    # Main loop for when the app is listening for transcription
    if st.session_state.get("is_listening", False):
        new_chunk_received = False
        try:
            # Check the queue for live text updates
            while not st.session_state.text_queue.empty():
                text = st.session_state.text_queue.get(block=False)
                st.session_state.accumulated_text = text

            # Accumulate stabilized text from the queue
            while not st.session_state.finished_text_queue.empty():
                new_full_transcript = st.session_state.finished_text_queue.get(block=False)
                if new_full_transcript != st.session_state.stabilized_text:
                    st.session_state.stabilized_text = new_full_transcript
                    new_chunk_received = True

            if new_chunk_received:
                new_transcript_chunk = st.session_state.stabilized_text[len(st.session_state.last_agent_transcript):].strip()

                if new_transcript_chunk and len(new_transcript_chunk.split()) > 2:
                    history = st.session_state.conversation.copy()
                    st.session_state.conversation.append(("user", new_transcript_chunk))
                    response = st.session_state.agent_service.get_response(new_transcript_chunk, history)
                    if response:
                        st.session_state.conversation.append(("agent", response))
                
                # CRUCIALLY: Update the last processed transcript state immediately
                st.session_state.last_agent_transcript = st.session_state.stabilized_text

        except queue.Empty: # this is expected
            pass
        
    # --- UI Display (runs in all states) ---
    col1, col2 = st.columns(2, gap="large")

    with col1:
        st.subheader("Transcript:")
        st.text_area(
            "Live Transcription",
            value=st.session_state.stabilized_text.strip(),
            height=800,
            label_visibility="collapsed",
        )

    with col2:
        st.subheader("Co-Pilot Insights:")
        # Display the agent's suggestions
        chat_display = ""
        for speaker, text in st.session_state.conversation:
            if speaker == "agent":
                chat_display += f"{text}\n---\n"
        st.text_area("Co-Pilot Display", value=chat_display, height=800, label_visibility="collapsed", disabled=True)

    # If we are listening, we need to periodically rerun to update the UI
    if st.session_state.get("is_listening", False):
        # Rerun periodically to check the queue and update UI
        time.sleep(0.1)
        st.rerun()


if __name__ == "__main__":
    main()
