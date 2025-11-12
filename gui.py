import streamlit as st
import queue
import time
from transcription_service import TranscriptionService


def main():
    """
    Main function to run the Streamlit application.
    """
    st.title("🎙️ KuBe Co-Pilot")

    # Initialize session state variables
    if "is_listening" not in st.session_state:
        st.session_state.is_listening = False
    if "transcription_service" not in st.session_state:
        st.session_state.transcription_service = None
    if "language" not in st.session_state:
        st.session_state.language = "de"

    # --- UI Components ---
    language_code = st.radio(
        "Language",
        ("DE", "EN"),
        horizontal=True,
        index=0 if st.session_state.language == "de" else 1,
    ).lower()

    # If language changed, reset the transcriber
    if language_code != st.session_state.language:
        st.session_state.language = language_code
        st.session_state.transcription_service = None  # Invalidate the service
        st.rerun()

    # Load the transcriber model on first run
    if st.session_state.transcription_service is None:
        with st.spinner("The app is loading, please wait..."):
            st.session_state.text_queue = queue.Queue()
            st.session_state.realtime_text = ""
            st.session_state.transcription_service = TranscriptionService(
                st.session_state.language, st.session_state.text_queue
            )
        st.rerun()

    # Create the button and define its behavior
    if st.button(
        "Stop Listening" if st.session_state.is_listening else "Start Listening"
    ):

        if st.session_state.is_listening:
            # This was a "Stop Listening" click
            st.session_state.is_listening = False
            if st.session_state.transcription_service:
                st.session_state.transcription_service.stop()
            st.info("Stopped listening.")
            st.rerun()
        else:
            # This was a "Start Listening" click
            st.session_state.realtime_text = ""  # Clear previous text
            # Clear the queue for the new session
            while not st.session_state.text_queue.empty():
                st.session_state.text_queue.get()

            if st.session_state.transcription_service:
                st.session_state.transcription_service.start()
                st.session_state.is_listening = True
                st.info("Started listening.")
                st.rerun()

    # Display the transcription text area
    st.subheader("Transcription:")
    text_area = st.empty()

    # This is the main UI update loop
    if st.session_state.get("is_listening", False):
        try:
            # Check the queue for new text
            while not st.session_state.text_queue.empty():
                text = st.session_state.text_queue.get(block=False)
                st.session_state.realtime_text = text

            text_area.text_area(
                "Live Transcription",
                value=st.session_state.realtime_text,
                height=200,
                label_visibility="collapsed",
            )

            # Rerun periodically to check the queue
            time.sleep(0.05)
            st.rerun()

        except queue.Empty:
            # If the queue is empty, just wait and rerun
            time.sleep(0.05)
            st.rerun()
    else:
        # When not listening, just display the last text
        text_area.text_area(
            "Live Transcription",
            value=st.session_state.get("realtime_text", ""),
            height=200,
            label_visibility="collapsed",
        )


if __name__ == "__main__":
    main()
