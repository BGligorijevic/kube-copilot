import asyncio
import json
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


async def transcription_sender(websocket: WebSocket, language: str):
    """
    Handles the transcription and agent services, sending data to the client.
    This function only WRITES to the websocket.
    """
    text_queue = asyncio.Queue()
    finished_text_queue = asyncio.Queue()
    conversation = []
    last_agent_transcript = ""
    try:
        agent_service = AgentService(language=language)
        transcription_service = TranscriptionService(
            language, text_queue, finished_text_queue
        )
        print(f"Starting transcription service for language: {language}")

        # Run the blocking start method in a separate thread
        await asyncio.to_thread(transcription_service.start)
        print(f"Transcription started for language: {language}")
        while True:
            # Asynchronously wait for a new transcript to be available in the queue.
            # This is non-blocking and integrates with the asyncio event loop.
            # Notify the client that the service is ready and listening
            await websocket.send_text(json.dumps({
                "type": "status",
                "data": "listening"
            }))

            stabilized_text = await finished_text_queue.get()

            # Send the full transcript to the client
            await websocket.send_text(json.dumps({
                "type": "transcript",
                "data": stabilized_text
            }))

            # Identify the new part of the transcript to send to the agent
            new_chunk = stabilized_text[len(last_agent_transcript):].strip()

            # number of words
            if new_chunk and len(new_chunk.split()) > 10:
                history = conversation.copy()
                conversation.append(("user", new_chunk))
                response = await asyncio.to_thread(agent_service.get_response, new_chunk, history)
                if response:
                    conversation.append(("agent", response))
                    # Send agent insight to the client
                    await websocket.send_text(json.dumps({
                        "type": "insight",
                        "data": response
                    }))

            last_agent_transcript = stabilized_text

    except (Exception, asyncio.CancelledError) as e:
        print(f"An error occurred: {e}")
    finally:
        print("Transcription service shutting down.")
        if 'transcription_service' in locals() and transcription_service:
            transcription_service.shutdown()


async def message_receiver(websocket: WebSocket, transcription_task_group):
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
                await websocket.send_text(json.dumps({
                    "type": "status",
                    "data": "starting"
                }))

                language = data.get("language", "de")
                # Create a new task in the provided task group
                new_task = asyncio.create_task(transcription_sender(websocket, language))
                transcription_task_group.add(new_task)

    except WebSocketDisconnect:
        print("Client disconnected from receiver.")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    The main WebSocket endpoint that handles client connections.
    It creates two concurrent tasks: one for receiving messages and one for sending them.
    """
    await websocket.accept()
    transcription_tasks = set()

    try:
        # Run the sender and receiver tasks concurrently.
        # They will run until one of them finishes (e.g., due to disconnection).
        await message_receiver(websocket, transcription_tasks)

    except WebSocketDisconnect:
        print("Client disconnected.")
    finally:
        # Ensure all transcription tasks are cancelled on disconnect.
        for task in transcription_tasks:
            task.cancel()
        print("All transcription tasks cancelled.")