import asyncio
import sys
import os

# This setup allows the script to be run from the project root (e.g., `python -m backend.test_agent`)
# and handles the relative imports within the backend module correctly.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.agent import AgentService
from langgraph.graph import START, END


async def run_test():
    """
    Initializes the AgentService and runs a series of test transcripts against it
    to verify its behavior in isolation.
    """
    print("--- Initializing Agent Service for Testing ---")
    # We use a consistent user_id to ensure the agent maintains memory across calls.
    agent_service = AgentService(language="de", user_id="test_user_123")
    print("--- Agent Service Initialized ---\n")

    # A list of transcripts to simulate a conversation flow.
    test_transcripts = [
        # 1. Initial greeting, should be silent.
        "Guten Tag, ich würde gerne über meine Anlagen sprechen.",
        
        # 2. Client states a goal. Agent should provide a suggestion.
        "Mein Ziel ist es, ein ausgewogenes Portfolio zu haben.",
        
        # 3. Client asks for specific products, which should trigger the tool.
        # The agent should first call the tool, then interpret the result in the next step.
        "Können Sie mir Produkte mit hohem Kupon finden?",

        # 4. A repeated statement, which should be caught by the repetition check.
        "Mein Ziel ist es, ein ausgewogenes Portfolio zu haben.",

        # 5. A new goal that requires a different suggestion.
        "Ich habe meine Meinung geändert, ich möchte jetzt ein konservatives Risikoprofil.",
    ]

    full_transcript = ""
    for i, transcript in enumerate(test_transcripts):
        print(f"--- Test Case {i+1} ---")
        full_transcript += (" " + transcript).strip()
        print(f"Input Transcript: '{full_transcript}'")
        
        # In a real app, this is an async call, so we await it.
        # We use asyncio.to_thread because the underlying graph invoke call is synchronous.
        await asyncio.to_thread(agent_service.get_response, full_transcript)

        # Optional: Print the full memory state to see how the history evolves
        # print("\n--- Current Agent Memory State ---")
        # memory = await asyncio.to_thread(agent_service.get_memory)
        # for key, value in memory.items():
        #     print(f"{key}: {value}")
        # print("-" * 20 + "\n")

async def run_long_transcript_test():
    """
    Runs a test with a long, realistic transcript, calling the agent
    incrementally to simulate a real-time conversation.
    """
    print("--- Initializing Agent Service for Long Transcript Test ---")
    agent_service = AgentService(language="de", user_id="test_user_long_transcript")
    print("--- Agent Service Initialized ---\n")

    full_text = """
Guten Tag, Herr Keller. Schön, Sie zu sehen. Wie geht es Ihnen?
Guten Tag, Frau Herzog. Danke, mir geht es gut. Ich hoffe, Ihnen auch?
Ja, danke. Nehmen Sie doch bitte Platz. Sie sagten am Telefon, Sie würden gerne über Ihre Anlagesituation sprechen.
Ja, ganz genau. Wissen Sie, ich werde nächstes Jahr 64, und der Ruhestand klopft langsam, aber sicher an die Tür. Meine Frau und ich fangen an, uns ernsthafte Gedanken über die Zeit danach zu machen.
Das ist eine sehr wichtige und spannende Phase. Es ist klug, dass Sie sich jetzt damit befassen. Was sind denn Ihre Prioritäten, wenn Sie an Ihre Finanzen im Ruhestand denken?
Also, das Wichtigste für uns ist Stabilität und Sicherheit. Wir haben über die Jahre einiges auf die Seite legen können. Die wilden Zeiten an der Börse, wo man vielleicht noch mehr Risiko eingegangen ist, sind für mich vorbei.
Das kann ich absolut nachvollziehen. Der Fokus verschiebt sich also klar in Richtung Kapitalerhalt.
Genau. Sehen Sie, unsere beiden Kinder sind aus dem Haus und glücklicherweise gut verheiratet. Wir müssen also niemanden mehr direkt unterstützen, was eine grosse Erleichterung ist. Aber das Vermögen, das wir haben, das soll uns den Ruhestand eben... nun ja, vergolden.
Das heisst, es geht Ihnen nicht nur um den Erhalt, sondern vielleicht auch um einen gewissen Ertrag?
Ja, das wäre der Idealfall. Wir suchen sichere Anlagen, die nicht bei jedem Windstoss am Markt gleich ins Wanken geraten. Aber wenn dabei ein kleines, regelmässiges Zusatzeinkommen herausspringen würde – vielleicht für eine schönere Reise pro Jahr oder einfach als Puffer – wäre das natürlich wunderbar. Es geht nicht um die Maximierung, sondern um Beständigkeit.
Verstehe. Also, um es zusammenzufassen: Die Kinder sind versorgt, die grosse "Aufbauphase" ist abgeschlossen. Jetzt suchen Sie nach einer Strategie für die "Genussphase", bei der die Sicherheit des Kapitals an erster Stelle steht, aber ein stabiler, zusätzlicher Ertrag sehr willkommen ist.
Besser hätte ich es nicht sagen können, Frau Herzog. Genau das ist es.
Vielen Dank für diese klare Darstellung Ihrer Situation und Ihrer Ziele. Das ist die beste Grundlage. Ihre Situation ist nicht ungewöhnlich, aber sie erfordert eine massgeschneiderte Lösung, keinen Standardplan.
Und was würden Sie mir da vorschlagen?
Wissen Sie, Herr Keller, ich möchte Ihnen jetzt ungern eine vorschnelle Antwort geben. Ihre Ziele sind klar definiert – Stabilität und beständiger Ertrag. Ich möchte mir die Zeit nehmen, einige Produkte und Strukturen zu prüfen, die genau auf dieses Profil passen, anstatt Ihnen einfach das nächstbeste zu präsentieren.
Das weiss ich zu schätzen.
Ich werde mir Ihre aktuelle Depotstruktur noch einmal genau ansehen und dazu ein paar fundierte Gedanken machen. Ich melde mich dann bis spätestens Ende nächster Woche bei Ihnen, um einen Folgetermin zu vereinbaren, bei dem wir dann ganz konkrete Optionen besprechen können. Ist das in Ordnung für Sie?
Ja, das klingt nach einem sehr guten Plan. So machen wir es. Vielen Dank für Ihre Zeit, Frau Herzog.
Sehr gerne, Herr Keller. Es war mir eine Freude. Ich begleite Sie noch zur Tür.
"""
    # Split the text into sentences, preserving the delimiters.
    sentences = [s.strip() for s in full_text.replace('?', '?|').replace('.', '.|').replace('!', '!|').split('|') if s.strip()]

    transcript_chunk = ""
    last_call_index = 0
    for i, sentence in enumerate(sentences):
        transcript_chunk += (" " + sentence).strip()
        
        # Call agent after every 10th sentence
        if (i + 1) % 10 == 0:
            print(f"--- Test Case: Calling agent after sentence {i + 1} ---")
            print(f"Input Transcript: '{transcript_chunk}'")
            await asyncio.to_thread(agent_service.get_response, transcript_chunk)
            print("-" * 20 + "\n")
            last_call_index = i + 1

    # Final call with the full transcript if it hasn't been called already
    if last_call_index < len(sentences):
        print("--- Test Case: Final call with full transcript ---")
        print(f"Input Transcript: '{transcript_chunk}'")
        await asyncio.to_thread(agent_service.get_response, transcript_chunk)
        print("-" * 20 + "\n")

if __name__ == "__main__":
    # To run this script, navigate to your project's root directory and execute:
    # python -m backend.test_agent
    # asyncio.run(run_test())
    asyncio.run(run_long_transcript_test())