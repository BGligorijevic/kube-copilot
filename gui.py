import streamlit as st
import queue
import time
from transcription_service import TranscriptionService
from agent import AgentService
import re

# --- Constants ---
SENTENCE_THRESHOLD = 3  # Number of new sentences to trigger agent

def count_sentences(text: str) -> int:
    """Counts the number of sentences in a given text."""
    if not text:
        return 0
    # Use regex to split by '.', '?', '!' and count non-empty parts
    sentences = re.split(r'[.?!]', text)
    return len([s for s in sentences if s.strip()])

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
    if "agent_service" not in st.session_state:
        st.session_state.agent_service = AgentService()
    if "accumulated_text" not in st.session_state:
        st.session_state.accumulated_text = ""
    if "stabilized_text_buffer" not in st.session_state:
        st.session_state.stabilized_text_buffer = ""
    if "last_processed_text" not in st.session_state:
        st.session_state.last_processed_text = ""
    if "conversation" not in st.session_state:
        st.session_state.conversation = []

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
            st.session_state.finished_text_queue = queue.Queue()
            st.session_state.transcription_service = TranscriptionService(
                st.session_state.language, 
                st.session_state.text_queue,
                st.session_state.finished_text_queue
            )
        st.rerun()

    # Create the button and define its behavior
    if st.button(
        "Stop Listening" if st.session_state.is_listening else "Start Listening"
    ):

        if st.session_state.is_listening:
            # This was a "Stop Listening" click
            st.session_state.is_listening = False
            # Final check to process any remaining text
            while not st.session_state.finished_text_queue.empty():
                final_text = st.session_state.finished_text_queue.get(block=False)
                if final_text:
                    response = st.session_state.agent_service.get_response(final_text)
                    st.session_state.conversation.append(("user", final_text))
                    st.session_state.conversation.append(("agent", response))
            if st.session_state.transcription_service:
                st.session_state.transcription_service.stop()
            st.info("Stopped listening.")
            st.rerun()
        else:
            # This was a "Start Listening" click
            st.session_state.realtime_text = ""  # Clear previous text
            st.session_state.accumulated_text = ""
            st.session_state.stabilized_text_buffer = ""
            st.session_state.last_processed_text = ""
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

    # Display the transcription text area
    st.subheader("Transcription:")
    text_area = st.empty()
    st.subheader("Co-Pilot Response:")
    agent_area = st.empty()
    
    # This is the main UI update loop
    if st.session_state.get("is_listening", False):
        try:
            # Check the queue for live text updates
            while not st.session_state.text_queue.empty():
                text = st.session_state.text_queue.get(block=False)
                st.session_state.accumulated_text = text

            text_area.text_area( # This just shows the live, changing text
                "Live Transcription",
                value=st.session_state.accumulated_text,
                height=200,
                label_visibility="collapsed",
            )

            # --- Agent Trigger Logic based on accumulated STABILIZED text ---
            # 1. Accumulate stabilized text from the queue
            while not st.session_state.finished_text_queue.empty():
                final_text = st.session_state.finished_text_queue.get(block=False)
                st.session_state.stabilized_text_buffer = final_text

            # 2. Check if enough new sentences have been accumulated
            current_sentences = count_sentences(st.session_state.stabilized_text_buffer)
            processed_sentences = count_sentences(st.session_state.last_processed_text)

            if (current_sentences > processed_sentences and 
                (current_sentences - processed_sentences) >= SENTENCE_THRESHOLD):
                
                with st.spinner("Agent is thinking..."):
                    # Identify the new text to be processed
                    new_text_to_process = st.session_state.stabilized_text_buffer[len(st.session_state.last_processed_text):].strip()
                    st.session_state.last_processed_text = st.session_state.stabilized_text_buffer
                    response = st.session_state.agent_service.get_response(new_text_to_process)
                    st.session_state.conversation.append(("user", new_text_to_process))
                    with st.spinner("Agent is thinking..."):
                        st.session_state.conversation.append(("agent", response))

            # Display conversation
            chat_display = ""
            for speaker, text in st.session_state.conversation:
                if speaker == "agent":
                    chat_display += f"**Co-Pilot:** {text}\n\n"
            
            agent_area.markdown(chat_display)

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
            "Transcription",
            value=st.session_state.get("accumulated_text", ""),
            height=200,
            label_visibility="collapsed",
        )
        # Display conversation
        chat_display = ""
        for speaker, text in st.session_state.conversation:
            if speaker == "agent":
                chat_display += f"**Co-Pilot:** {text}\n\n"
        agent_area.markdown(chat_display)


if __name__ == "__main__":
    main()
