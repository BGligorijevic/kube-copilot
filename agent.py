from langchain_ollama import ChatOllama
from langchain.agents import create_agent

class AgentService:
    """
    A service to interact with a Large Language Model (LLM).

    This is a placeholder implementation that simply echoes the input text.
    In the future, this will be replaced with actual calls to a local LLM.
    """
    def __init__(self):
        self._llm = ChatOllama(model="llama3.1", temperature=0)
        self._agent = create_agent(
            model=self._llm,
            system_prompt="You help the bank client advisor advise the customer based on the transcript of the discussion you receive from the customer and the bank client advisor." \
            "Always respond in the same language you receive the questions in. You are based in Switzerland and are consulting client advisors who works in a Swiss bank." \
            "The customers are almost always Swiss residents. Be consise and clear, because your suggestions are read in real-time from the client advisor. He cannot read too much text quickly."
)

    def get_response(self, input: str) -> str:
        """Receives text and returns a response from the 'LLM'."""
        
        print(f"Received from the transcript: {input}")
        messages = [
            {"role": "user", "content": input},
        ]

        result = self._agent.invoke({"messages": messages})

        ai_messages = [m for m in result["messages"] if m.__class__.__name__ == "AIMessage" and m.content]
        content_str = ai_messages[0].content

        return content_str

