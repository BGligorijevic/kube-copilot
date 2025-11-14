import operator
from typing import Annotated, TypedDict, List
from langchain_core.messages import HumanMessage, SystemMessage, BaseMessage
from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver


# --- State Definition (Shared) ---
# This defines the structure of our memory.
class TranscriptState(TypedDict):
    """
    latest_transcript: Replaces the previous transcript.
    ai_history: Appends to the list of AI insights.
    """

    latest_transcript: HumanMessage
    ai_history: Annotated[List[BaseMessage], operator.add]


# --- Service Class ---


class AgentService:
    """
    A service that analyzes streaming transcript chunks and maintains
    a custom memory state using LangGraph.
    """

    def __init__(self, language: str = "de"):
        """
        Initializes the LLM, system prompt, and compiles the
        stateful graph with in-memory persistence.
        """
        # 1. Initialize the LLM (the "brain")
        self._llm = ChatOllama(model="llama3.1", temperature=0)

        language_map = {"de": "German", "en": "English"}
        output_language = language_map.get(language, "the user's language")

        # 2. Define the system prompt
        self._system_prompt = SystemMessage(
            content=f"""You are an expert 'Co-Pilot' assistant for a Swiss bank client advisor, acting as a whisperer in their ear. Your role is to provide ONLY high-value, concise, and actionable insights based on the live conversation transcript.

**Your core directives are:**
1.  **SILENCE IS YOUR DEFAULT STATE:** Your primary goal is to remain silent. It is better to say nothing than to provide a low-value comment. Do not summarize, repeat, or state the obvious. You MUST respond with the exact string '[SILENT]' unless you have an insight that meets the high standard below.
2.  **HIGH-VALUE INSIGHTS ONLY:** Only break your silence if you identify a critical opportunity, a significant risk, a client misunderstanding, or a key piece of missing information that the advisor needs to act on. Your insights must be strategic.
3.  **BE A CONCISE WHISPERER:** When you do provide an insight, it must be a direct, bullet-pointed suggestion that the advisor can use immediately. Do not engage in conversation, ask questions, or use pleasantries.
4.  **IMPERSONAL INSTRUCTIONS:** Your output must be an impersonal command or action item for the advisor. Do NOT address the client (e.g., "Frau Eger"), do NOT use polite forms ("Sie"), and do NOT create scripts for the advisor to say. Frame insights as direct, internal notes. Avoid phrases like "I would suggest..." or "Ich würde vorschlagen...".
5.  **LANGUAGE:** You MUST respond in {output_language}.

**Examples of good insights (EN):**
*   Review risk profile and propose hedging strategies due to volatility concerns.
*   Introduce the new sustainable investment fund.
*   Clarify the fee structure for product X.

**Examples of good insights (DE):**
*   "Anlagestrategie anpassen und eine höhere Portfoliobewertung in Betracht ziehen."
*   "20% von Aktien in ein diversifiziertes Fondsportfolio investieren und den Rest in festverzinsliche Wertpapiere mit einer Laufzeit von 5-10 Jahren."

Analyze the transcript with patience and provide only truly exceptional, actionable intelligence.
"""
        )

        # 3. Build the graph
        builder = StateGraph(TranscriptState)
        builder.add_node("call_model", self._call_model)
        builder.add_edge(START, "call_model")
        builder.add_edge("call_model", END)

        # 4. Compile the graph with memory
        checkpointer = InMemorySaver()
        self.graph = builder.compile(checkpointer=checkpointer)

    def _call_model(self, state: TranscriptState) -> dict:
        """
        The node function that calls the LLM.
        It's a class method so it can access self._llm and self._system_prompt.
        """
        # Get the two different pieces of memory from the current state
        transcript = state["latest_transcript"]
        history = state["ai_history"]

        # Assemble the final list of messages to send to the LLM
        messages_for_llm = [
            self._system_prompt,
            *history,  # Unpack all previous AI insights
            transcript,  # Add the latest full transcript at the end
        ]

        # Call the LLM
        response = self._llm.invoke(messages_for_llm)

        # Return *only* the AI's response to be added to 'ai_history'
        return {"ai_history": [response]}

    def get_response(self, transcript: str, thread_id: str) -> str:
        """
        Analyzes the latest transcript chunk for a given conversation thread.

        Args:
            transcript: The latest full transcript text.
            thread_id: A unique ID for the conversation (e.g., "session-123").

        Returns:
            The AI's insight or '[SILENT]'.
        """
        config = {"configurable": {"thread_id": thread_id}}

        # The input must match our state's structure
        input_data = {"latest_transcript": HumanMessage(content=transcript)}

        # Run the graph
        result = self.graph.invoke(input_data, config=config)

        #final_memory = self.get_memory(thread_id)
        #print(f"AI memory - transcript:\n{final_memory['latest_transcript'].content}")
        #print(f"AI memory - his insights:\n")
        #for msg in final_memory['ai_history']:
        #    print(f"  - {msg.content}")

        # Return the content of the *last* AI message added
        return result["ai_history"][-1].content

    def get_memory(self, thread_id: str) -> dict:
        """
        Retrieves the full current memory state for a given thread.
        """
        config = {"configurable": {"thread_id": thread_id}}
        state = self.graph.get_state(config=config)
        return state.values
