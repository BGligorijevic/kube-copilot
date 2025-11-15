import operator
from typing import Annotated, TypedDict, List
from langchain_core.messages import (
    HumanMessage,
    SystemMessage,
    BaseMessage,
    ToolMessage,
)
from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver
from langchain_core.messages import AIMessage
from langgraph.prebuilt import ToolNode
from .tools.product_tool import search_structured_products

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

    def __init__(self, language: str = "de", user_id: str = "none"):
        """
        Initializes the LLM, system prompt, and compiles the
        stateful graph with in-memory persistence.
        """
        self._language = language
        self._user_id = user_id

        print(f"user id:  {self._user_id}")

        # 1. Initialize the LLM and tools
        llm = ChatOllama(model="llama3.1", temperature=0)
        self._tools = []
        self._tools.append(search_structured_products)

        if self._tools:
            self._llm = llm.bind_tools(self._tools)
        else:
            self._llm = llm

        # 2. Define the system prompt
        self._system_prompt = self._get_system_prompt()

        # 3. Build the graph
        builder = StateGraph(TranscriptState)
        builder.add_node("call_model", self.call_model_node)
        tool_node = ToolNode(self._tools, messages_key="ai_history")
        builder.add_node("call_tool", tool_node)

        builder.add_conditional_edges(
            "call_model", self.should_continue, {"continue": "call_tool", "__end__": END}
        )
        builder.add_edge(START, "call_model")
        builder.add_edge("call_tool", "call_model")

        # 4. Compile the graph with memory
        checkpointer = InMemorySaver()
        self.graph = builder.compile(checkpointer=checkpointer)

    def _get_system_prompt(self) -> SystemMessage:
        """
        Generates the system prompt based on the specified language.
        """
        language_map = {"de": "German", "en": "English"}
        output_language = language_map.get(self._language, "the user's language")

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
5.  **TOOL USAGE & INTERPRETATION:**
    *   If the user asks for specific investment products (e.g., "find products with high coupon"), you MUST use the `search_structured_products` tool. Do not describe the tool call; execute it directly.
    *   After the tool returns a result (which will be a list of products in JSON format), your next step is to **interpret** it. You MUST formulate a natural language suggestion based on the tool's output and the user's original request. For example, if the user wanted growth and the tool returns product 'SP010', your output should be something like: `* Recommend product SP010 (Swissquote Dynamic Growth Certificate) as it aligns with the client's interest in growth stocks.`
6.  **NO CHAT:** Do not output conversational text, apologies ("Es tut mir leid..."), or hypothetical scenarios ("Wenn wir annehmen..."). Your output is either a direct suggestion, a tool call, or silence.
7.  **STRATEGY MUST MATCH GOAL (THE "RULEBOOK"):** Your suggested asset allocation MUST be logically consistent with the client's stated profile or goal.
    * 'Konservativ' (Safety): Must have LOW equities (e.g., 20-30%).
    * 'Ausgewogen' (Balanced): Must have MEDIUM equities (e.g., 40-60%).
    * 'Wachstum' / 'Risky' (Growth): Must have HIGH equities/risk assets (e.g., 70%+).
8.  **ACTION-ONLY OUTPUT:** Your output MUST be a bulleted list of actionable commands.
    * **DO NOT** add definitions, summaries, or chat.
    * **DO NOT** talk about yourself or your rules.
9.  **LOGICAL MATH:** All portfolio percentages MUST add up to 100%.
10. **NAMES:** Do not mention names, just give suggestions and advice.


{example_block}
"""
        )

    def call_model_node(self, state: TranscriptState) -> dict:
        """
        The node function that calls the LLM.
        It is invoked by the graph and receives the current state.
        """
        history = state.get("ai_history") or []
        latest_transcript = state.get("latest_transcript")

        # Assemble the final list of messages to send to the LLM
        messages_for_llm = [self._system_prompt]
        messages_for_llm.extend(history)

        # Only add the transcript if it's a new one. After a tool call, we don't need it again.
        if latest_transcript:
            messages_for_llm.append(latest_transcript)
        # After a tool call, the latest message in history is a ToolMessage.
        # The LLM needs the original user request (the last HumanMessage) to make sense of the tool output.
        elif history and isinstance(history[-1], ToolMessage):
            # Find the last HumanMessage in the history and add it back to the prompt.
            last_human_message = next(
                (msg for msg in reversed(history) if isinstance(msg, HumanMessage)),
                None,
            )
            if last_human_message:
                messages_for_llm.append(last_human_message)

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

        # We clear the latest_transcript to prevent it from being used in the next iteration
        # within the same graph run (e.g., after a tool call).
        # The history is appended, which is the correct stateful operation.
        return {"ai_history": [response], "latest_transcript": None}

    def should_continue(self, state: TranscriptState) -> str:
        """
        Determines the next step in the graph.
        If the model made a tool call, we route to the 'call_tool' node.
        Otherwise, we end the process.
        """
        # If the LLM makes a tool call, then we route to the tool node
        last_message = state["ai_history"][-1]
        if last_message.tool_calls:
            return "continue"
        # Otherwise, we end the graph.
        return "__end__"

    def get_response(self, transcript: str) -> str:
        """
        Analyzes the latest transcript chunk for a given conversation thread.

        Args:
            transcript: The latest full transcript text.

        Returns:
            The AI's insight or '[SILENT]'.
        """
        config = {"configurable": {"thread_id": self._user_id}}

        # The input must match our state's structure
        input_data = {"latest_transcript": HumanMessage(content=transcript)}

        # Run the graph
        result = self.graph.invoke(input_data, config=config)

        # final_memory = self.get_memory()
        # print(f"AI memory - transcript:\n{final_memory['latest_transcript'].content}")
        # print(f"AI memory - his insights:\n")
        # for msg in final_memory['ai_history']:
        #    print(f"  - {msg.content}")

        # Return the content of the *last* AI message added
        agent_output = result["ai_history"][-1].content
        print(f"{bcolors.OKGREEN}Agent Response: {agent_output}{bcolors.ENDC}")
        return agent_output

    def get_memory(self) -> dict:
        """
        Retrieves the full current memory state for a given user.
        """
        config = {"configurable": {"thread_id": self._user_id}}
        state = self.graph.get_state(config=config)
        return state.values

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'