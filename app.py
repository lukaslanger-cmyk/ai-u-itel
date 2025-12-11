import streamlit as st
import asyncio
import edge_tts
from groq import Groq
from streamlit_mic_recorder import mic_recorder
import io

# --- 1. KONFIGURACE APLIKACE & CSS ---
st.set_page_config(page_title="AI English Teacher Pro", page_icon="🎓", layout="wide")

st.markdown("""
<style>
    .main { background-color: #ffffff; }
    section[data-testid="stSidebar"] { background-color: #f7f9fc; border-right: 1px solid #e0e0e0; }
    .sidebar-header { font-size: 1.2em; font-weight: bold; color: #1e3a8a; margin-bottom: 10px; border-bottom: 2px solid #1e3a8a; padding-bottom: 5px; }
    .stButton>button { width: 100%; border-radius: 8px; height: 3em; font-weight: 600; border: none; background-color: #2563eb; color: white; transition: all 0.2s; }
    .stButton>button:hover { background-color: #1d4ed8; transform: translateY(-2px); box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
    .task-card { background: linear-gradient(135deg, #ffffff 0%, #f0f9ff 100%); padding: 30px; border-radius: 20px; border: 1px solid #bae6fd; box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1); text-align: center; margin-bottom: 25px; }
    .feedback-box { padding: 20px; border-radius: 12px; margin-top: 15px; text-align: left; font-size: 1.05em; line-height: 1.6; }
    .fb-success { background-color: #dcfce7; border-left: 5px solid #22c55e; color: #14532d; }
    .fb-error { background-color: #fee2e2; border-left: 5px solid #ef4444; color: #7f1d1d; }
    /* Zvětšení audio přehrávače */
    audio { width: 100%; margin-top: 10px; margin-bottom: 20px; }
    h1, h2, h3 { color: #1e293b; font-family: 'Segoe UI', sans-serif; }
</style>
""", unsafe_allow_html=True)

try:
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
except:
    st.error("⚠️ CRITICAL: Chybí API klíč.")
    st.stop()

client = Groq(api_key=GROQ_API_KEY)

# --- 2. PEDAGOGICKY UPRAVENÝ SYLABUS ---
SYLLABUS_DATA = [
  {"id": 1, "title": "1. Být či nebýt? (TO BE)", "topic": "Verb TO BE (Singular: I am, You are, He is / Plural: We are, They are) + Negatives (I am not)", "goal": "Umět používat sloveso BÝT v jednotném i množném čísle a v záporu."},
  {"id": 2, "title": "2. Kde co leží? (Předložky)", "topic": "Prepositions (in, on, under, next to, behind)", "goal": "Určit polohu věcí (jedné i více)."},
  {"id": 3, "title": "3. Mít či nemít? (HAVE GOT)", "topic": "Verb HAVE GOT (Singular & Plural) + Questions (Have you got?)", "goal": "Mluvit o vlastnictví věcí a zvířat."},
  {"id": 4, "title": "4. Superman (CAN / CAN'T)", "topic": "Modal verb CAN (Schopnosti)", "goal": "Říct, co umíme a co neumíme my i ostatní."},
  {"id": 5, "title": "5. Moje rodina (MY, YOUR...)", "topic": "Possessives (My, Your, Our, Their) + Family members", "goal": "Představit členy rodiny a čí co je."}
]

TASK_TYPES = {
    1: {"type": "listen", "name": "👂 Krok 1: Porozumění (Poslech)", "instruction": "Poslouchej anglickou větu. Co to znamená česky?", "lang_rec": "cs"},
    2: {"type": "imitate", "name": "🦜 Krok 2: Výslovnost (Papoušek)", "instruction": "Přečti a zopakuj anglickou větu. Snaž se o přízvuk.", "lang_rec": "en"},
    3: {"type": "translate", "name": "✍️ Krok 3: Překlad (Dril)", "instruction": "Přelož tuto větu do angličtiny.", "lang_rec": "en"},
    4: {"type": "respond", "name": "🗣️ Krok 4: Konverzace (Reakce)", "instruction": "Odpověz anglicky na otázku. Mluv pravdu nebo si vymýšlej.", "lang_rec": "en"},
    5: {"type": "boss", "name": "🏆 Krok 5: Boss Fight (Výzva)", "instruction": "Těžší věta. Dej si pozor na gramatiku!", "lang_rec": "en"}
}

# --- 3. JÁDRO APLIKACE ---

def init_session():
    defaults = {
        'step': 0,
        'current_lesson_index': 0,
        'theory_content': None,
        'task_data': None,
        'feedback': None,
        'task_audio_bytes': None # Změna názvu - ukládáme bajty
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

def reset_lesson():
    st.session_state.step = 0
    st.session_state.task_data = None
    st.session_state.feedback = None
    st.session_state.theory_content = None
    st.session_state.task_audio_bytes = None

async def generate_audio_bytes(text, lang="en"):
    """Generuje audio a vrací surová DATA (bytes), ne ukazatel."""
    try:
        voice = "en-US-AnaNeural" if lang == "en" else "cs-CZ-VlastaNeural"
        clean = text.replace("**", "").replace("*", "").replace("`", "")
        communicate = edge_tts.Communicate(clean, voice)
        fp = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio": fp.write(chunk["data"])
        return fp.getvalue() # VRACÍME HODNOTU, NE OBJEKT
    except: return None

def get_theory(lesson_data):
    prompt = f"""
    Jsi zkušený učitel angličtiny. Téma: {lesson_data['topic']}.
    Cíl: Vysvětlit látku dětem (8-12 let).
    POŽADAVKY:
    1. Vysvětli jednotné číslo (Já/Ty) I množné číslo (My/Vy/Oni).
    2. Vysvětli zápor (pokud je v tématu).
    3. Uveď 4 jasné příklady (2x jednotné, 2x množné).
    4. Používej Markdown odrážky.
    """
    try:
        return client.chat.completions.create(
            model="llama-3.3-70b-versatile", messages=[{"role": "system", "content": prompt}]
        ).choices[0].message.content
    except: return "Chyba teorie."

def generate_task_data(lesson_data, step_number):
    task_type = TASK_TYPES[step_number]["type"]
    topic = lesson_data['topic']
    
    prompt = f"""
    Generuj cvičení. Téma: {topic}. Typ: {task_type}.
    INSTRUKCE: Používej slovní zásobu A1/A2. 
    DŮLEŽITÉ: Střídej osoby! Nechtěj jen "I am". Chtěj "We are", "They are", "She is".
    Pokud je téma o záporu, použij ho.
    
    Formáty:
    LISTEN: EN věta|CZ překlad
    IMITATE: EN věta|CZ význam
    TRANSLATE: CZ věta|EN překlad
    RESPOND: EN otázka|Typ odpovědi
    BOSS: CZ souvětí|EN překlad
    
    ODPOVĚZ JEN: PART1|PART2
    """
    try:
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile", messages=[{"role": "system", "content": prompt}], temperature=0.5
        ).choices[0].message.content
        parts = resp.split('|')
        return {"primary": parts[0].strip(), "secondary": parts[1].strip() if len(parts)>1 else "", "type": task_type}
    except: return {"primary": "Error", "secondary": "", "type": "error"}

def evaluate_student(student_text, task_data, task_type):
    prompt = f"""
    Jsi učitel. Úkol: {task_type}. Cíl: "{task_data['primary']}" (nebo "{task_data['secondary']}").
    Dítě řeklo: "{student_text}".
    
    Pravidla:
    1. Ignoruj interpunkci a velikost písmen.
    2. Uznej zkrácené tvary (I'm = I am).
    3. Pokud dítě řeklo správný význam jinými slovy (u konverzace), uznej to.
    
    Výstup: VERDIKT (Výborně/Pozor/Zkus to)|VYSVĚTLENÍ (Česky)|CORRECT_EN
    """
    try:
        return client.chat.completions.create(
            model="llama-3.3-70b-versatile", messages=[{"role": "system", "content": prompt}]
        ).choices[0].message.content
    except: return "Chyba|-|-|-"

# --- 4. UI LOGIKA ---
def main():
    init_session() 

    # --- LEVÝ PANEL ---
    with st.sidebar:
        st.markdown('<div class="sidebar-header">🦁 Můj profil</div>', unsafe_allow_html=True)
        st.caption("Student: **Začátečník**")
        st.progress(st.session_state.current_lesson_index / len(SYLLABUS_DATA), text="Celkový postup")
        
        st.markdown("---")
        st.markdown('<div class="sidebar
