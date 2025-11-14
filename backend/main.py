import asyncio
import json
import re
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import sys
import os
from .transcription_service import TranscriptionService
from .agent import AgentService


sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
app = FastAPI()

# Configure CORS to allow the React frontend to connect.
# In production, you should restrict this to your frontend's domain.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)


async def transcription_sender(websocket: WebSocket, language: str, shutdown_event: asyncio.Event):
    """
    Handles the transcription and agent services, sending data to the client.
    This function only WRITES to the websocket.
    """
    text_queue = asyncio.Queue()
    finished_text_queue = asyncio.Queue()
    sentence_count = 0
    stabilized_text = ""
    agent_service = None
    try:
        async def send_to_agent(text_to_send):
            """Helper function to send text to the agent and handle the response."""
            if not text_to_send:
                return
            try:
                response = await asyncio.to_thread(
                    agent_service.get_response, text_to_send, "transcript-1"
                )
                if response and response.strip().upper() != "[SILENT]":
                    # Check if the websocket is still active before sending
                    if websocket.client_state.name == "CONNECTED":
                        await websocket.send_text(
                            json.dumps({"type": "insight", "data": response})
                        )
            except Exception as e:
                print(f"Error sending transcript to agent: {e}")

        agent_service = AgentService(language=language)
        transcription_service = TranscriptionService(
            language, text_queue, finished_text_queue
        )
        print(f"Starting transcription service for language: {language}")

        # Run the blocking start method in a separate thread
        await asyncio.to_thread(transcription_service.start)
        print(f"Transcription started for language: {language}")
        
        # Notify the client that the service is ready and listening
        await websocket.send_text(
            json.dumps({"type": "status", "data": "listening"})
        )

        while not shutdown_event.is_set():
            try:
                # Wait for new text or for the shutdown signal
                get_task = asyncio.create_task(finished_text_queue.get())
                wait_task = asyncio.create_task(shutdown_event.wait())
                done, pending = await asyncio.wait(
                    {get_task, wait_task}, return_when=asyncio.FIRST_COMPLETED
                )

                if wait_task in done:
                    # Shutdown event was set, break the loop
                    get_task.cancel()
                    break

                stabilized_text = get_task.result()
                for task in pending:
                    task.cancel()

            except asyncio.CancelledError:
                break

            # Send the full transcript to the client
            await websocket.send_text(
                json.dumps({"type": "transcript", "data": stabilized_text})
            )

            # print(f"Stabilized text: {stabilized_text}")

            # Count sentences in the stabilized text.
            # This is a simple regex that looks for sentence-ending punctuation.
            current_sentences = len(re.findall(r"[.!?]+", stabilized_text))

            # Send the full transcript to the agent every N sentences.
            # Using modulo is more reliable than integer division for this.
            if current_sentences > 0 and current_sentences % 3 == 0 and current_sentences != sentence_count:
                print(
                    f"Sending full transcript to agent. Sentence count: {current_sentences}"
                )
                await send_to_agent(stabilized_text)
                sentence_count = current_sentences

    except asyncio.CancelledError:
        print("Transcription sender task cancelled.")
    except Exception as e:
        print(f"An error occurred in transcription_sender: {e}")
    finally:
        # This block now handles final sends and cleanup.
        # It's triggered by the shutdown_event or by cancellation.
        if websocket.client_state.name == "CONNECTED":
            print("Sending final (complete) transcript to client.")
            await websocket.send_text(
                json.dumps({"type": "transcript", "data": stabilized_text})
            )
    
        print("Transcription service shutting down.")
        if 'transcription_service' in locals() and transcription_service:
            transcription_service.shutdown()

    # Return the final state to the caller for final processing, after cleanup.
    return stabilized_text, agent_service, sentence_count

async def message_receiver(
    websocket: WebSocket, transcription_task_group, shutdown_events
):
    """
    Handles receiving messages from the client.
    This function only READS from the websocket.
    """
    try:
        while True:
            message = await websocket.receive_text()
            data = json.loads(message)

            action = data.get("action")
            if action == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
            elif action == "start":
                print("Received start message.")
                # Cancel any existing transcription task before starting a new one.
                for task in transcription_task_group:
                    task.cancel()
                # Notify the client that the service is starting
                await websocket.send_text(
                    json.dumps({"type": "status", "data": "starting"})
                )

                language = data.get("language", "de")
                shutdown_event = asyncio.Event()
                shutdown_events.append(shutdown_event)
                # Create a new task in the provided task group
                new_task = asyncio.create_task(
                    transcription_sender(websocket, language, shutdown_event)
                )
                transcription_task_group.add(new_task)
            elif action == "stop":
                print("Received stop message. Signaling transcription tasks to shut down.")
                # Signal all transcription tasks to shut down gracefully
                for event in shutdown_events:
                    event.set()
                print("Waiting for transcription tasks to send final messages and clean up.")
                # Await the completion of the tasks to ensure they finish gracefully.
                results = await asyncio.gather(
                    *transcription_task_group, return_exceptions=True
                )
                
                # Process the final transcript after the transcriber has stopped.
                if results and not isinstance(results[0], Exception):
                    stabilized_text, agent_service, sentence_count = results[0]
                    if agent_service and stabilized_text:
                        print("Sending final transcript to agent and waiting for response.")
                        response = await asyncio.to_thread(
                            agent_service.get_response, stabilized_text, "transcript-1"
                        )
                        if response and response.strip().upper() != "[SILENT]":
                            await websocket.send_text(
                                json.dumps({"type": "insight", "data": response})
                            )

                print("All tasks gracefully stopped. Closing connection.")
                await websocket.close() # Close the connection as the very last step.
                break # Exit the while loop.

    except WebSocketDisconnect:
        print("Client disconnected from receiver.")
        # If the client disconnects, we still need to signal any running tasks to stop.
        for event in shutdown_events:
            event.set()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    The main WebSocket endpoint that handles client connections.
    It creates two concurrent tasks: one for receiving messages and one for sending them.
    """
    await websocket.accept()
    transcription_tasks = set()
    shutdown_events = []

    try:
        # Run the sender and receiver tasks concurrently.
        # They will run until one of them finishes (e.g., due to disconnection).
        await message_receiver(websocket, transcription_tasks, shutdown_events)

    except WebSocketDisconnect:
        print("Client disconnected.")
    finally:
        # Ensure all transcription tasks are cancelled on disconnect.
        for task in transcription_tasks:
            task.cancel()
        print("All transcription tasks cancelled.")
