import asyncio
import sys
import os

# This setup allows the script to be run from the project root (e.g., `python -m backend.test_agent`)
# and handles the relative imports within the backend module correctly.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.agent import AgentService
from langgraph.graph import START, END


class TestScenarios:
    """
    A container for different test transcript scenarios.
    This makes it easier to add, remove, or select tests.
    """
    SAFETY_AND_INCOME_DE = """
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

    GROWTH_DE = """
Guten Tag. Schön, Sie zu sehen. Worum geht es Ihnen heute? Guten Tag. Ich wollte mir meine Anlagestrategie ansehen. 
Ich habe das Gefühl, wir könnten da etwas mutiger sein. Das heisst, Sie sind bereit, für höhere Renditechancen auch ein höheres Risiko einzugehen? 
Ja, genau. Ich bin beruflich etabliert, habe einen langen Anlagehorizont und möchte mein Kapital aktiv vermehren. 
Ein paar Schwankungen am Markt werfen mich nicht aus der Bahn. Verstehe. Der Fokus liegt also klar auf Wachstum, weniger auf Kapitalerhalt oder Ausschüttungen. 
Richtig. Ich möchte in Sektoren investieren, die echtes Potenzial haben, auch wenn sie volatiler sind. Stillstand ist für mich derzeit keine Option. Das ist ein klares Profil. 
In dem Fall sollten wir uns von den "sicheren Häfen" etwas entfernen und uns stattdessen gezielt wachstumsstarke Technologiefonds oder auch Schwellenmärkte ansehen. 
Das klingt genau nach dem, was ich mir vorgestellt habe. Gut. Ich werde ein paar Simulationen mit einer dynamischeren Portfolio-Allokation durchführen und Ihnen drei konkrete 
Umschichtungsvorschläge ausarbeiten. Perfekt. Ich warte auf Ihre Vorschläge. Sehr gerne. Dann bis in Kürze.
"""

    BALANCED_EN = """
Good afternoon. It's good to see you. What's on your mind today?
Good afternoon. I'd like to review my investment strategy. I feel it might be time for a more balanced approach.
Meaning you'd like to reduce some of the volatility, even if it means slightly more moderate returns?
Yes, precisely. We've had some good growth, but looking ahead, I'd prefer a bit more stability. I'm not looking to eliminate all risk, just to find a better equilibrium.
I understand. So, the goal is shifting from pure aggressive growth towards a blend of growth and capital preservation?
Exactly. I want to remain invested, but I'd sleep better knowing it's not quite so exposed to market swings. I'm interested in steady, long-term performance now.
That's a very sensible adjustment. In that case, we should look at re-weighting your portfolio. We can reduce exposure to the high-growth sectors and increase allocations in high-quality dividend funds or diversified bond holdings.
That sounds like the direction I was hoping for.
Excellent. I will prepare an analysis of your current holdings and model a new, more balanced allocation. I'll come back to you with three concrete proposals for us to discuss.
That's great. I look forward to seeing those.
My pleasure. I'll be in touch shortly.
"""

    STABLE_EN = """
Hello, thanks for making the time. 
What shall we cover today? Hello. I've been reading about market volatility, and frankly, I'm a bit concerned about my retirement savings. 
I understand. You're feeling that your current plan might be too exposed to a potential downturn? Exactly. I'm approaching retirement, and my main priority now is capital protection. 
I can't afford a big loss. That's a very clear and valid priority. So, we need to shift the focus firmly from accumulation to preservation? Yes. 
I'm less concerned with high returns now and more concerned with stable, predictable income and protecting what I've built. Right. 
This means we should review your equity holdings and significantly increase your allocation to fixed-income assets, perhaps even some annuities, to ensure a stable floor. 
That sounds much more suitable for my current situation. Good. I will re-run your plan with a capital preservation model. I'll prepare a new strategy that heavily emphasizes low-volatility 
assets and guaranteed income streams. Thank you, that would give me peace of mind. Of course. Let me work on that, and I'll send you the revised proposal by the end of the day.
"""

    STABLE_EN_FOCUS_CHF = """
Hello, thanks for making the time. 
What shall we cover today? Hello. I've been reading about market volatility, and frankly, I'm a bit concerned about my retirement savings. 
I understand. You're feeling that your current plan might be too exposed to a potential downturn? Exactly. I'm approaching retirement, and my main priority now is capital protection. 
I can't afford a big loss. That's a very clear and valid priority. So, we need to shift the focus firmly from accumulation to preservation? Yes. 
I'm less concerned with high returns now and more concerned with stable, predictable income and protecting what I've built. Right. 
I am also very concerned about the weakness of the USD and other major currencies compared to the swiss franc.
Of course. Let me work on that, and I'll send you the revised proposal by the end of the day.
"""

async def run_long_transcript_test():
    """
    Runs a test with a long, realistic transcript, calling the agent
    incrementally to simulate a real-time conversation.
    """
    
    # --- Select the test case to run ---
    scenario_name = "STABLE_EN_FOCUS_CHF"
    transcript_to_use = getattr(TestScenarios, scenario_name)
    
    # --- Determine language from the chosen transcript ---
    if "_EN" in scenario_name:
        language = "en"
    else:
        language = "de"

    print("--- Initializing Agent Service for Long Transcript Test ---")
    agent_service = AgentService(language=language, user_id="test_user_long_transcript")
    print("--- Agent Service Initialized ---\n")

    # Split the text into sentences, preserving the delimiters.
    sentences = [s.strip() for s in transcript_to_use.replace('?', '?|').replace('.', '.|').replace('!', '!|').split('|') if s.strip()]

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