import streamlit as st
import asyncio
import edge_tts
from groq import Groq
from streamlit_mic_recorder import mic_recorder
import io
import re

# --- 1. KONFIGURACE APLIKACE ---
st.set_page_config(page_title="AI English Buddy", page_icon="🦁", layout="centered")

# Styly
st.markdown("""
<style>
    .stButton>button {
        width: 100%;
        border-radius: 12px;
        height: 3.5em;
        font-weight: bold;
        font-size: 1.1em;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .task-box {
        background-color: #f0f8ff;
        padding: 25px;
        border-radius: 15px;
        border: 2px solid #87CEEB;
        text-align: center;
        margin-bottom: 20px;
    }
    h1 { color: #2E86C1; text-align: center; }
</style>
""", unsafe_allow_html=True)

# Kontrola API klíče
try:
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
except:
    st.error("⚠️ CRITICAL ERROR: Chybí API klíč v Streamlit Secrets.")
    st.stop()

client = Groq(api_key=GROQ_API_KEY)

# --- 2. UČEBNICE (VLOŽENÁ PŘÍMO V KÓDU) ---
# Už nepotřebuješ externí soubor syllabus.json
SYLLABUS_DATA = [
  {
    "id": 1,
    "title": "1. Kdo jsem? (Sloveso TO BE)",
    "topic": "Verb TO BE (I am, You are, He is)",
    "review_topic": None,
    "goal": "Představit se a říct, kdo jsem."
  },
  {
    "id": 2,
    "title": "2. Kde to je? (Předložky IN, ON)",
    "topic": "Prepositions of place (in, on, under)",
    "review_topic": "Verb TO BE",
    "goal": "Popsat, kde se nachází věci."
  },
  {
    "id": 3,
    "title": "3. Co mám? (HAVE GOT)",
    "topic": "Verb HAVE GOT (I have got, She has got)",
    "review_topic": "Animals / Objects",
    "goal": "Říct, co vlastním (hračky, zvířata)."
  },
  {
    "id": 4,
    "title": "4. Co umím? (CAN)",
    "topic": "Modal verb CAN / CAN'T",
    "review_topic": "Action verbs",
    "goal": "Popsat schopnosti (I can jump)."
  },
  {
    "id": 5,
    "title": "5. Moje rodina (MY, YOUR)",
    "topic": "Possessive adjectives (My, Your, His)",
    "review_topic": "Family members",
    "goal": "Představit členy rodiny."
  },
  {
    "id": 6,
    "title": "6. Co se děje? (Průběhový čas)",
    "topic": "Present Continuous (I am playing)",
    "review_topic": "Verb TO BE",
    "goal": "Popsat činnost, která se děje právě teď."
  },
  {
    "id": 7,
    "title": "7. Každý den (Přítomný čas)",
    "topic": "Present Simple (I play, He plays)",
    "review_topic": "Days of the week",
    "goal": "Popsat zvyky a rutinu."
  },
  {
    "id": 8,
    "title": "8. Otázky (DO you...?)",
    "topic": "Questions in Present Simple",
    "review_topic": "Present Simple",
    "goal": "Zeptat se kamaráda."
  },
  {
    "id": 9,
    "title": "9. Oblečení (Barvy a Vlastnosti)",
    "topic": "Adjectives (Red t-shirt, Big shoes)",
    "review_topic": "Colors",
    "goal": "Popsat oblečení."
  },
  {
    "id": 10,
    "title": "10. Počítání a Jídlo (SOME / ANY)",
    "topic": "Countable vs Uncountable",
    "review_topic": "Food",
    "goal": "Nakupování a jídlo."
  }
]

# Definice typů úkolů (Ping-Pong metoda)
TASK_TYPES = {
    1: {"type": "listen", "name": "👂 Krok 1: Poslech (Co to znamená?)", "lang_expect": "cs"},
    2: {"type": "imitate", "name": "🦜 Krok 2: Papoušek (Opakuj přesně)", "lang_expect": "en"},
    3: {"type": "translate", "name": "✍️ Krok 3: Překladatel (Řekni anglicky)", "lang_expect": "en"},
    4: {"type": "respond", "name": "🗣️ Krok 4: Konverzace (Odpověz na otázku)", "lang_expect": "en"},
    5: {"type": "boss", "name": "🏆 Krok 5: Boss Fight (Komplexní úkol)", "lang_expect": "en"}
}

# --- 3. POMOCNÉ FUNKCE ---

async def generate_audio_memory(text, lang="en"):
    """Generuje audio bezpečně do RAM."""
    try:
        voice = "en-US-AnaNeural" if lang == "en" else "cs-CZ-VlastaNeural"
        clean_text = text.replace("**", "").replace("*", "").replace("`", "").replace("🦁", "")
        communicate = edge_tts.Communicate(clean_text, voice)
        mp3_fp = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                mp3_fp.write(chunk["data"])
        mp3_fp.seek(0)
        return mp3_fp
    except:
        return None

def get_theory(lesson_data):
    """Generuje výklad učitele."""
    prompt = f"Jsi učitel. Téma: {lesson_data['topic']}. Vysvětli látku česky, jednoduše pro děti. Dej 3 příklady."
    try:
        return client.chat.completions.create(
            model="llama-3.3-70b-versatile", messages=[{"role": "system", "content": prompt}]
        ).choices[0].message.content
    except:
        return "Omlouvám se, učitel si zapomněl poznámky. Zkus to znovu."

def generate_task_data(lesson_data, step_number):
    """Generuje zadání úkolu."""
    task_type = TASK_TYPES[step_number]["type"]
    prompt = f"""
    Generuj cvičení. Téma: {lesson_data['topic']}. Typ: {task_type}.
    
    POKUD JE TYP 'listen': Vygeneruj EN větu a CZ překlad. Formát: EN|CZ
    POKUD JE TYP 'imitate': Vygeneruj EN frázi. Formát: EN|CZ_VYZNAM
    POKUD JE TYP 'translate': Vygeneruj CZ větu a EN překlad. Formát: CZ|EN
    POKUD JE TYP 'respond': Vygeneruj EN otázku. Formát: EN_OTAZKA|OČEKÁVANÁ_ODPOVĚĎ_TYP
    POKUD JE TYP 'boss': Vygeneruj těžší CZ větu. Formát: CZ|EN
    
    ODPOVĚZ JEN: PRVNÍ_ČÁST|DRUHÁ_ČÁST
    """
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile", messages=[{"role": "system", "content": prompt}]
        ).choices[0].message.content
        parts = response.split('|')
        return {"primary": parts[0].strip(), "secondary": parts[1].strip() if len(parts)>1 else "", "type": task_type}
    except:
        return {"primary": "Error loading task", "secondary": "", "type": "error"}

def evaluate_student(student_text, task_data, task_type):
    """Hodnotí odpověď žáka."""
    prompt = f"Úkol: {task_type}. Cíl: {task_data['primary']}. Student řekl: {student_text}. Ohodnoť česky, vysvětli chyby. Na konec dej [Correct English Sentence]."
    try:
        return client.chat.completions.create(
            model="llama-3.3-70b-versatile", messages=[{"role": "system", "content": prompt}]
        ).choices[0].message.content
    except:
        return "Chyba při hodnocení."

# --- 4. HLAVNÍ LOGIKA APLIKACE ---
def main():
    st.title("🦁 AI English Buddy")

    # Sidebar
    with st.sidebar:
        st.header("🗂️ Lekce")
        lesson_titles = [l['title'] for l in SYLLABUS_DATA]
        selected_lesson = st.selectbox("Vyber lekci:", lesson_titles)
        if st.button("🔄 Restartovat lekci"):
            st.session_state.step = 0
            st.rerun()

    current_lesson = next(l for l in SYLLABUS_DATA if l['title'] == selected_lesson)

    # --- BEZPEČNÁ INICIALIZACE (FIX) ---
    if 'step' not in st.session_state:
        st.session_state.step = 0
    if 'current_lesson_id' not in st.session_state:
        st.session_state.current_lesson_id = current_lesson['id']
    
    # Detekce změny lekce
    if st.session_state.current_lesson_id != current_lesson['id']:
        st.session_state.current_lesson_id = current_lesson['id']
        st.session_state.step = 0
        st.session_state.theory_content = None
        st.session_state.task_data = None
        st.session_state.feedback = None
        st.session_state.task_audio = None
        st.rerun()

    # KROK 0: TEORIE
    if st.session_state.step == 0:
        st.markdown(f"## 🎓 {current_lesson['title']}")
        if 'theory_content' not in st.session_state or not st.session_state.theory_content:
            with st.spinner("Příprava výkladu..."):
                st.session_state.theory_content = get_theory(current_lesson)
        
        st.info(st.session_state.theory_content)
        if st.button("Jdeme trénovat! 🚀", type="primary"):
            st.session_state.step = 1
            st.rerun()

    # KROKY 1-5
    elif st.session_state.step <= 5:
        step = st.session_state.step
        task_info = TASK_TYPES[step]
        st.progress(step/5, text=task_info['name'])

        if 'task_data' not in st.session_state or not st.session_state.task_data:
            with st.spinner("Generuji úkol..."):
                data = generate_task_data(current_lesson, step)
                st.session_state.task_data = data
                st.session_state.feedback = None
                # Audio zadání
                if data["type"] in ["listen", "imitate", "respond"]:
                    st.session_state.task_audio = asyncio.run(generate_audio_memory(data["primary"], "en"))
                else:
                    st.session_state.task_audio = None

        data = st.session_state.task_data
        
        # Zobrazení úkolu
        st.markdown(f'<div class="task-box"><h3>{task_info["name"]}</h3>', unsafe_allow_html=True)
        
        if data["type"] == "listen":
            st.write("🔊 Poslouchej a přelož do češtiny (Text je skrytý!)")
        else:
            st.markdown(f"**{data['primary']}**")
        
        if st.session_state.task_audio:
            st.audio(st.session_state.task_audio, format='audio/mp3')
            
        st.markdown('</div>', unsafe_allow_html=True)

        # Feedback nebo Nahrávání
        if st.session_state.feedback:
            st.success("Hodnocení:")
            st.write(st.session_state.feedback)
            if st.button("Další úkol ➡️"):
                st.session_state.step += 1
                st.session_state.task_data = None
                st.rerun()
        else:
            lang = task_info["lang_expect"]
            # Dynamický klíč pro nahrávátko, aby se neresetovalo předčasně
            audio_data = mic_recorder(start_prompt=f"🔴 Nahrát ({lang.upper()})", stop_prompt="⏹️ Odeslat", key=f"rec_{step}_{current_lesson['id']}")
            
            if audio_data:
                with st.spinner("Vyhodnocuji..."):
                    bio = io.BytesIO(audio_data['bytes'])
                    bio.name = "audio.wav"
                    try:
                        transcript = client.audio.transcriptions.create(
                            file=(bio.name, bio.read()), model="whisper-large-v3-turbo", language=lang, response_format="text"
                        ).strip()
                        st.info(f"Slyšel jsem: {transcript}")
                        st.session_state.feedback = evaluate_student(transcript, data, data["type"])
                        st.rerun()
                    except Exception as e:
                        st.error(f"Chyba: {e}")

    else:
        st.balloons()
        st.success("🎉 Lekce hotova!")
        if st.button("Zpět"):
            st.session_state.step = 0
            st.rerun()

if __name__ == "__main__":
    main()
