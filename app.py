import streamlit as st
import logging
import queue
import time
from RealtimeSTT import AudioToTextRecorder


def main():
    """
    Main function to run the Streamlit application.
    """
    st.title("🎙️ KuBe Co-Pilot")

    # Initialize session state variables
    if 'is_listening' not in st.session_state:
        st.session_state.is_listening = False
    if 'transcriber' not in st.session_state:
        st.session_state.transcriber = None
    if 'language' not in st.session_state:
        st.session_state.language = 'de'

    def get_on_realtime_text_update(text_queue: queue.Queue):
        """
        Returns a thread-safe callback function that puts text into the provided queue.
        """
        def on_realtime_text_update(text: str):
            text_queue.put(text)
        return on_realtime_text_update

    # Language selection UI
    language_code = st.radio(
        "Language",
        ("DE", "EN"),
        horizontal=True,
        index=0 if st.session_state.language == 'de' else 1
    ).lower()

    # If language changed, reset the transcriber
    if language_code != st.session_state.language:
        st.session_state.language = language_code
        st.session_state.transcriber = None
        st.rerun()

    # Load the transcriber model on first run
    if st.session_state.transcriber is None:
        with st.spinner("The app is loading, please wait..."):
            st.session_state.text_queue = queue.Queue()
            st.session_state.realtime_text = ""

            st.session_state.transcriber = AudioToTextRecorder(
                model="nebi/whisper-large-v3-turbo-swiss-german-ct2",
                language=st.session_state.language,
                device="mps",
                compute_type="auto",
                on_realtime_transcription_update=get_on_realtime_text_update(st.session_state.text_queue),
                realtime_model_type="tiny",
                enable_realtime_transcription=True,
                level=logging.INFO
            )
        st.rerun()

    # Create the button and define its behavior
    # Disable button if loading
    if st.button("Stop Listening" if st.session_state.is_listening else "Start Listening"):
        
        if st.session_state.is_listening:
            # This was a "Stop Listening" click
            st.session_state.is_listening = False
            if st.session_state.transcriber:
                st.session_state.transcriber.stop()
            st.info("Stopped listening.")
            st.rerun()
        else:
            # This was a "Start Listening" click
            st.session_state.realtime_text = "" # Clear previous text
            # Clear the queue for the new session
            while not st.session_state.text_queue.empty():
                st.session_state.text_queue.get()

            if st.session_state.transcriber:
                st.session_state.transcriber.start()
                st.session_state.is_listening = True
                st.info("Started listening.")
                st.rerun()

    # Display the transcription text area
    st.subheader("Transcription:")
    text_area = st.empty()

    # This is the main UI update loop
    if st.session_state.get('is_listening', False):
        try:
            # Check the queue for new text
            while not st.session_state.text_queue.empty():
                text = st.session_state.text_queue.get(block=False)
                st.session_state.realtime_text = text

            text_area.text_area("Live Transcription", value=st.session_state.realtime_text, height=200, label_visibility="collapsed")

            # Rerun periodically to check the queue
            time.sleep(0.05)
            st.rerun()

        except queue.Empty:
            # If the queue is empty, just wait and rerun
            time.sleep(0.05)
            st.rerun()
    else:
        # When not listening, just display the last text
        text_area.text_area("Live Transcription", value=st.session_state.get('realtime_text', ''), height=200, label_visibility="collapsed")

if __name__ == '__main__':
    main()