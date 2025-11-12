import streamlit as st
import logging
import queue
import time

def main():
    """
    Main function to run the Streamlit application.
    """
    st.title("🎙️ RealtimeSTT Demo")

    # Initialize session state variables
    if 'is_recording' not in st.session_state:
        st.session_state.is_recording = False
    if 'transcriber' not in st.session_state:
        st.session_state.transcriber = None
    if 'text_queue' not in st.session_state:
        st.session_state.text_queue = queue.Queue()
    if 'realtime_text' not in st.session_state:
        st.session_state.realtime_text = ""

    def get_on_realtime_text_update(text_queue: queue.Queue):
        """
        Returns a thread-safe callback function that puts text into the provided queue.
        """
        def on_realtime_text_update(text: str):
            text_queue.put(text)
        return on_realtime_text_update

    # Create the button and define its behavior
    if st.button("Stop Recording" if st.session_state.is_recording else "Start Recording"):
        st.session_state.is_recording = not st.session_state.is_recording

        if st.session_state.is_recording:
            st.session_state.realtime_text = "" # Clear previous text
            # Lazy import and create a new transcriber instance
            from RealtimeSTT import AudioToTextRecorder

            with st.spinner("Loading model and starting recording..."):
                # Clear the queue for the new session
                while not st.session_state.text_queue.empty():
                    st.session_state.text_queue.get()

                st.session_state.transcriber = AudioToTextRecorder(
                    model="medium.en",
                    language="en",
                    device="mps",
                    compute_type="auto",
                    on_realtime_transcription_update=get_on_realtime_text_update(st.session_state.text_queue),
                    realtime_model_type="tiny.en",
                    enable_realtime_transcription=True,
                    level=logging.INFO
                )
                st.session_state.transcriber.start()
            st.info("Recording started.")
        else:
            # Stop and destroy the transcriber instance
            if st.session_state.transcriber:
                st.session_state.transcriber.stop()
                st.session_state.transcriber = None
            st.info("Recording stopped.")

        st.rerun()

    # Display the transcription text area
    st.subheader("Transcription:")
    text_area = st.empty()

    # This is the main UI update loop
    if st.session_state.is_recording:
        try:
            # Check the queue for new text
            while not st.session_state.text_queue.empty():
                text = st.session_state.text_queue.get(block=False)
                st.session_state.realtime_text = text

            text_area.text_area("Live Transcription", value=st.session_state.realtime_text, height=200)

            # Rerun periodically to check the queue
            time.sleep(0.05)
            st.rerun()

        except queue.Empty:
            # If the queue is empty, just wait and rerun
            time.sleep(0.05)
            st.rerun()
    else:
        # When not recording, just display the last text
        text_area.text_area("Live Transcription", value=st.session_state.realtime_text, height=200)

if __name__ == '__main__':
    main()