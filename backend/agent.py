import operator
from typing import Annotated, TypedDict, List
from langchain_core.messages import HumanMessage, SystemMessage, BaseMessage
from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver
from langchain_core.messages import AIMessage


class TranscriptState(TypedDict):
    """
    latest_transcript: Replaces the previous transcript.
    ai_history: Appends to the list of AI insights.
    """
    latest_transcript: HumanMessage
    ai_history: Annotated[List[BaseMessage], operator.add]


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
            content=f"""You are an expert 'Co-Pilot' assistant. Your job is to provide actionable insights.
You will analyze the transcript and your own proposed advice in a step-by-step "internal monologue" that you will NOT output.
You will ONLY output the final, clean insight, or `[SILENT]`.

**INTERNAL MONOLOGUE (DO NOT OUTPUT THIS PART):**
1.  **Analyze Goal:** What is the client's current profile? What new profile do they *want*? (e.g., 'Ausgewogen' -> 'Konservativ'). What is their stated motivation? (e.g., 'Sicherheit').
2.  **Draft Advice:** Based on the new goal, draft a portfolio. (e.g., "Draft: 20% Stocks, 70% Bonds, 10% ESG").
3.  **Check 1 (Logic):** Does this draft match the client's goal? (e.g., "Is 20% stocks good for 'Konservativ'?") -> "Yes". (If I drafted 50% stocks, the answer would be "No", and I must redraft).
4.  **Check 2 (Math):** Do the percentages add up to 100%? (e.g., "20+70+10 = 100") -> "Yes". (If not, I must redraft).
5.  **Check 3 (Format):** Is the output clean, with no definitions, explanations, or chat? -> "Yes".
6.  **Final Output:** (Produce the final, clean advice).

**YOUR ACTUAL OUTPUT RULES:**
1.  **SILENCE IS DEFAULT:** You MUST respond with the exact string `[SILENT]` unless you have a new, high-value insight.
2.  **CLEAN OUTPUT ONLY:** Your output MUST be a bulleted list of *actionable commands only*.
    * **DO NOT** output your "internal monologue".
    * **DO NOT** add definitions, summaries, or chat.
3.  **LANGUAGE:** You MUST respond in {output_language}.

**Good Output Example:**
* Risikoprofil auf 'Konservativ' anpassen.
* Umschichtung vorschlagen: 20% Aktien, 70% Anleihen, 10% ESG.
* Globalen Anleihenfonds (Laufzeit 5-10 Jahre) vorschlagen.

**Bad Output Example (Violates Rules):**
* 1. Analyze Goal: The client wants... (Violates Rule 2)
* Umschichtung vorschlagen: 50% Aktien... (Logic Failure)
* Umschichtung vorschlagen: 20% Aktien, 40%... (Math Failure)
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
        new_content = response.content.strip() # Clean up any whitespace

        # --- Robust Repetition Check ---
        
        # 1. Get previous AI responses
        previous_ai_responses = {
            msg.content.strip() for msg in history 
            if isinstance(msg, AIMessage)
        }

        # 2. Check for exact duplicates
        is_exact_duplicate = new_content in previous_ai_responses

        # 3. Check if new response is a "subset" of an old one
        #    (e.g., new="A" when history contains "A, B, C")
        #    This is the check you are currently missing.
        is_subset_duplicate = any(
            new_content in old_response 
            and new_content != old_response # Make sure it's not just an exact match
            for old_response in previous_ai_responses
        )

        # 4. Force silence
        # Also force silence on the model's new, bad "explanation" habit
        if (is_exact_duplicate or 
            is_subset_duplicate or 
            new_content == "[SILENT]" or
            "(Siehe oben" in new_content or # Filter new bad behavior
            ": Das bedeutet" in new_content): # Filter new bad behavior
            
            response.content = "[SILENT]"

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

        # final_memory = self.get_memory(thread_id)
        # print(f"AI memory - transcript:\n{final_memory['latest_transcript'].content}")
        # print(f"AI memory - his insights:\n")
        # for msg in final_memory['ai_history']:
        #    print(f"  - {msg.content}")

        # Return the content of the *last* AI message added
        agent_output = result["ai_history"][-1].content
        print(f"Agent output: {agent_output}\n")
        return agent_output

    def get_memory(self, thread_id: str) -> dict:
        """
        Retrieves the full current memory state for a given thread.
        """
        config = {"configurable": {"thread_id": thread_id}}
        state = self.graph.get_state(config=config)
        return state.values
