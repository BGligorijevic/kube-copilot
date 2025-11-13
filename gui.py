import streamlit as st
import queue
import time
from transcription_service import TranscriptionService
from agent import AgentService
import re

# --- Constants ---

def handle_button_click():
    """Handles the logic for the 'Start/Stop Listening' button."""
    if st.session_state.is_listening:
        # This was a "Stop Listening" click
        st.session_state.is_listening = False
        if st.session_state.transcription_service:
            st.session_state.transcription_service.stop()

        # Process any remaining text from the queue
        while not st.session_state.finished_text_queue.empty():
            final_text = st.session_state.finished_text_queue.get(block=False)
            # TODO: This overwrites previous stabilized text. This should probably append.
            st.session_state.stabilized_text_buffer = final_text
        
        if st.session_state.stabilized_text_buffer:
            response = st.session_state.agent_service.get_response(st.session_state.stabilized_text_buffer)
            st.session_state.conversation.append(("agent", response))
        st.rerun()
    else:
        # This was a "Start Listening" click
        st.session_state.realtime_text = ""  # Clear previous text
        st.session_state.accumulated_text = ""
        st.session_state.stabilized_text_buffer = ""
        st.session_state.conversation = []
        # Clear the queue for the new session
        while not st.session_state.text_queue.empty():
            st.session_state.text_queue.get()
        while not st.session_state.finished_text_queue.empty():
            st.session_state.finished_text_queue.get()

        if st.session_state.transcription_service:
            st.session_state.transcription_service.start()
            st.session_state.is_listening = True
            st.info("Started listening.")
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
    if "transcription_service" not in st.session_state:
        st.session_state.transcription_service = None
    if "language" not in st.session_state:
        st.session_state.language = "de"
    if "agent_service" not in st.session_state:
        st.session_state.agent_service = AgentService()
    if "accumulated_text" not in st.session_state:
        st.session_state.accumulated_text = ""
    if "stabilized_text_buffer" not in st.session_state:
        st.session_state.stabilized_text_buffer = ""
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

    # If language changed, reset the transcriber
    if language_code != st.session_state.language:
        st.session_state.language = language_code
        st.session_state.transcription_service = None  # Invalidate the service
        st.rerun()

    # Load the transcriber model on first run
    if st.session_state.transcription_service is None:
        with st.spinner("The app is loading, please wait..."):
            st.session_state.text_queue = queue.Queue()
            st.session_state.finished_text_queue = queue.Queue()
            st.session_state.transcription_service = TranscriptionService(
                st.session_state.language, 
                st.session_state.text_queue,
                st.session_state.finished_text_queue
            )
        st.rerun()

    # Display the transcription text area
    col1, col2 = st.columns(2, gap="large")
    with col1:
        st.subheader("Transcript:")
    with col2:
        st.subheader("Co-Pilot Insights:")
    if st.session_state.get("is_listening", False):
        try:
            # Check the queue for live text updates
            while not st.session_state.text_queue.empty():
                text = st.session_state.text_queue.get(block=False)
                st.session_state.accumulated_text = text

            with col1:
                st.text_area(
                    "Live Transcription",
                    value=st.session_state.accumulated_text,
                    height=800,
                    label_visibility="collapsed",
                )

            # Accumulate stabilized text from the queue
            while not st.session_state.finished_text_queue.empty():
                final_text = st.session_state.finished_text_queue.get(block=False)
                st.session_state.stabilized_text_buffer = final_text

            # Display conversation
            chat_display = ""
            for speaker, text in st.session_state.conversation:
                if speaker == "agent":
                    chat_display += f"{text}\n\n"
            # Use a disabled text_area for the co-pilot to match the transcript's look and feel
            with col2:
                st.text_area("Co-Pilot Display", value=chat_display, height=400, label_visibility="collapsed", disabled=True)

            if not st.session_state.is_listening:
                st.info("Stopped listening. Processing final text...")

            # Rerun periodically to check the queue
            time.sleep(0.05)
            st.rerun()

        except queue.Empty:
            # If the queue is empty, just wait and rerun
            time.sleep(0.05)
            st.rerun()
    else:
        # When not listening, just display the last text
        with col1:
            st.text_area(
                "Transcription",
                value=st.session_state.get("stabilized_text_buffer", ""),
                height=800,
                label_visibility="collapsed",
            )
        # Display conversation
        chat_display = ""
        for speaker, text in st.session_state.conversation:
            if speaker == "agent":
                chat_display += f"{text}\n\n"
        # Use a disabled text_area for the co-pilot to match the transcript's look and feel
        with col2:
            st.text_area("Co-Pilot Display", value=chat_display, height=800, label_visibility="collapsed", disabled=True)


if __name__ == "__main__":
    main()
