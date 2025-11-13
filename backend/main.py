import asyncio
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import sys
import os

# Add the parent directory to the Python path to import sibling modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from transcription_service import TranscriptionService
from agent import AgentService

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


async def transcription_agent_task(
    websocket: WebSocket,
    language: str
):
    """
    Manages the transcription and agent services for a single WebSocket connection.
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

        # Run the blocking start method in a separate thread
        await asyncio.to_thread(transcription_service.start)
        print(f"Transcription started for language: {language}")

        # Notify the client that the service is ready and listening
        await websocket.send_text(json.dumps({
            "type": "status",
            "data": "listening"
        }))

        while True:
            # Asynchronously wait for a new transcript to be available in the queue.
            # This is non-blocking and integrates with the asyncio event loop.
            stabilized_text = await finished_text_queue.get()

            # Send the full transcript to the client
            await websocket.send_text(json.dumps({
                "type": "transcript",
                "data": stabilized_text
            }))

            # Identify the new part of the transcript to send to the agent
            new_chunk = stabilized_text[len(last_agent_transcript):].strip()

            if new_chunk and len(new_chunk.split()) > 2:
                history = conversation.copy()
                conversation.append(("user", new_chunk))
                response = agent_service.get_response(new_chunk, history)
                if response:
                    conversation.append(("agent", response))
                    # Send agent insight to the client
                    await websocket.send_text(json.dumps({
                        "type": "insight",
                        "data": response
                    }))

            last_agent_transcript = stabilized_text

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        print("Transcription service shutting down.")
        if 'transcription_service' in locals() and transcription_service:
            transcription_service.shutdown()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    The main WebSocket endpoint that handles client connections.
    Awaits a 'start' message from the client to begin transcription.
    """
    await websocket.accept()
    transcription_task = None

    try:
        while True:
            message = await websocket.receive_text()
            data = json.loads(message)

            if data.get("action") == "start":
                if transcription_task:
                    transcription_task.cancel()

                language = data.get("language", "de")
                transcription_task = asyncio.create_task(
                    transcription_agent_task(websocket, language)
                )

    except WebSocketDisconnect:
        print("Client disconnected.")
        if transcription_task:
            transcription_task.cancel()