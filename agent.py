from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import AIMessage, HumanMessage

class AgentService:
    """
    A service to interact with a Large Language Model (LLM) agent
    that can decide when it is appropriate to provide insights.
    """
    def __init__(self, language: str = "de"):
        self._llm = ChatOllama(model="llama3.1", temperature=0)

        language_map = {
            "de": "German",
            "en": "English"
        }
        output_language = language_map.get(language, "the user's language")

        # This prompt instructs the agent on its role and tells it to output '[SILENT]'
        # when it has no valuable insight to contribute.
        prompt = ChatPromptTemplate.from_messages([
            ("system", f"""You are a 'Co-Pilot' assistant for a Swiss bank client advisor, acting as a whisperer in their ear. Your role is to provide ONLY concise, actionable insights based on the live conversation transcript.

**Your core directives are:**
1.  **BE SILENT BY DEFAULT:** If you do not have a concrete, valuable insight, you MUST respond with the exact string '[SILENT]'.
2.  **PROVIDE INSIGHTS, NOT CONVERSATION:** Do not engage in conversation. Do not ask questions. Do not greet the user or state the obvious (e.g., 'The conversation has started'). Your output should be a direct insight, not a commentary on the conversation.
3.  **BE A WHISPERER:** Your output should be a direct, bullet-pointed insight that the advisor can use immediately. Think of it as a helpful note passed during a meeting.
4.  **LANGUAGE:** You MUST respond in {output_language}.

**Example of a good insight:**
* Suggest checking the client's risk tolerance due to mentions of market volatility.
* Flag opportunity to discuss sustainable investment products based on client's interest in environmental topics.

Analyze the transcript and provide only high-value, actionable intelligence.
"""),
            MessagesPlaceholder("chat_history"),
            ("human", "{input}"),
        ])

        # We create a simple chain that pipes the formatted prompt into the language model.
        self._chain = prompt | self._llm

    def get_response(self, input: str, chat_history: list) -> str:
        """Receives text and returns a response from the 'LLM'."""
        print(f"Received from the transcript: {input}")

        # Convert our simple chat history into the format LangChain expects.
        history_messages = []
        for speaker, text in chat_history:
            if speaker == "agent":
                history_messages.append(AIMessage(content=text))
            else:
                history_messages.append(HumanMessage(content=text))

        result = self._chain.invoke({"input": input, "chat_history": history_messages})
        print(f"Agent raw response: {result}")

        # Extract the text content from the AIMessage response.
        content = result.content if isinstance(result, AIMessage) else ""

        # If the agent decides to be silent, we return an empty string.
        if "[SILENT]" in content:
            content = ""

        print(f"Agent final output: {content}")
        return content
