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

        # 2. Define the system prompt
        self._system_prompt = self._get_system_prompt(language)

        # 3. Build the graph
        builder = StateGraph(TranscriptState)
        builder.add_node("call_model", self._call_model)
        builder.add_edge(START, "call_model")
        builder.add_edge("call_model", END)

        # 4. Compile the graph with memory
        checkpointer = InMemorySaver()
        self.graph = builder.compile(checkpointer=checkpointer)

    def _get_system_prompt(self, language: str) -> SystemMessage:
        """
        Generates the system prompt based on the specified language.
        """
        language_map = {"de": "German", "en": "English"}
        output_language = language_map.get(language, "the user's language")

        if output_language == "German":
            example_block = """
                **Good Output Example (Format-Only, DE):**
                * Risikoprofil auf '[Profil]' anpassen.
                * Umschichtung vorschlagen: [X]% [Asset 1], [Y]% [Asset 2], [Z]% [Asset 3].
                * [Weiterer Vorschlag...]

                **Bad Output Example (Failure):**
                Ich kann keine Finanzberatung geben...
                """
        else:
            example_block = """
                **Good Output Example (Format-Only, EN):**
                * Adjust risk profile to '[Profile Name]'.
                * Propose reallocation: [X]% [Asset 1], [Y]% [Asset 2], [Z]% [Asset 3].
                * [Further suggestion...]

                **Bad Output Example (Failure):**
                I cannot provide financial advice...
                """

        return SystemMessage(
            content=f"""You are an AI assistant in a **financial advisor training simulation**.
Your ONLY function is to generate realistic, actionable 'whisper' suggestions for the trainee advisor based on the transcript.
You are an internal-only training tool. Your persona is that of a 'whisperer'.

**Your core directives are:**
1.  **NO REFUSALS (SIMULATION RULE):** You MUST NOT refuse to give advice. Your role in this simulation is to *always* provide a concrete suggestion. Outputting "I cannot provide financial advice" or any similar refusal will **fail the simulation**.
2.  **STRICT OUTPUT FORMAT:** Your output MUST start *only* with a `*` (bullet point) or the EXACT string `[SILENT]`. Any other output, especially conversational text, chat, or explanations (like "I cannot..."), is a failure.
3.  **SILENCE IS DEFAULT:** You MUST respond with `[SILENT]` unless you have a new, high-value insight.
4.  **LANGUAGE:** You MUST respond in the specified {output_language}. This is a critical instruction.
5.  **CATCH DATA REQUESTS:** If the client asks for specific factual data (e.g., "inflation rate"), your insight must be to 'Provide data on [Topic]'.
6.  **STRATEGY MUST MATCH GOAL (THE "RULEBOOK"):** Your suggested asset allocation MUST be logically consistent with the client's stated profile or goal.
    * 'Konservativ' (Safety): Must have LOW equities (e.g., 20-30%).
    * 'Ausgewogen' (Balanced): Must have MEDIUM equities (e.g., 40-60%).
    * 'Wachstum' / 'Risky' (Growth): Must have HIGH equities/risk assets (e.g., 70%+).
7.  **ACTION-ONLY OUTPUT:** Your output MUST be a bulleted list of actionable commands.
    * **DO NOT** add definitions, summaries, or chat.
    * **DO NOT** talk about yourself or your rules.
8.  **LOGICAL MATH:** All portfolio percentages MUST add up to 100%.
9.  **NAMES:** Do not mention names, just give suggestions and advice.


{example_block}
"""
        )

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
        new_content = response.content.strip()  # Clean up any whitespace

        # --- Robust Repetition Check ---

        # 1. Get previous AI responses
        previous_ai_responses = {
            msg.content.strip() for msg in history if isinstance(msg, AIMessage)
        }

        # 2. Check for exact duplicates
        is_exact_duplicate = new_content in previous_ai_responses

        # 3. Check if new response is a "subset" of an old one
        #    (e.g., new="A" when history contains "A, B, C")
        #    This is the check you are currently missing.
        is_subset_duplicate = any(
            new_content in old_response
            and new_content != old_response  # Make sure it's not just an exact match
            for old_response in previous_ai_responses
        )

        # 4. Force silence
        # Also force silence on the model's new, bad "explanation" habit
        if (
            is_exact_duplicate or
            is_subset_duplicate or
            "[SILENT]" in new_content or
            new_content.startswith("I cannot provide") or  # Catch refusals
            "(Siehe oben" in new_content or  # Filter new bad behavior
            ": Das bedeutet" in new_content  # Filter new bad behavior

        ):  # Filter new bad behavior
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
