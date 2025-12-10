import streamlit as st
import json
import asyncio
import edge_tts
from groq import Groq
from streamlit_mic_recorder import mic_recorder
import io
import re

# --- KONFIGURACE ---
st.set_page_config(page_title="AI English Buddy", page_icon="🦁", layout="centered")

# CSS Design
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

# API Check
try:
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
except:
    st.error("⚠️ CRITICAL ERROR: Chybí API klíč v Streamlit Secrets.")
    st.stop()

client = Groq(api_key=GROQ_API_KEY)

# DEFINICE TYPŮ ÚKOLŮ
TASK_TYPES = {
    1: {"type": "listen", "name": "👂 Krok 1: Poslech (Co to znamená?)", "lang_expect": "cs"},
    2: {"type": "imitate", "name": "🦜 Krok 2: Papoušek (Opakuj přesně)", "lang_expect": "en"},
    3: {"type": "translate", "name": "✍️ Krok 3: Překladatel (Řekni anglicky)", "lang_expect": "en"},
    4: {"type": "respond", "name": "🗣️ Krok 4: Konverzace (Odpověz na otázku)", "lang_expect": "en"},
    5: {"type": "boss", "name": "🏆 Krok 5: Boss Fight (Komplexní úkol)", "lang_expect": "en"}
}

# --- FUNKCE ---

async def generate_audio_memory(text, lang="en"):
    """Generuje audio bezpečně."""
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

def load_syllabus():
    try:
        with open('syllabus.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return []

def get_theory(lesson_data):
    prompt = f"Jsi učitel. Téma: {lesson_data['topic']}. Vysvětli látku česky, jednoduše pro děti. Dej 3 příklady."
    return client.chat.completions.create(
        model="llama-3.3-70b-versatile", messages=[{"role": "system", "content": prompt}]
    ).choices[0].message.content

def generate_task_data(lesson_data, step_number):
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
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile", messages=[{"role": "system", "content": prompt}]
    ).choices[0].message.content
    
    try:
        parts = response.split('|')
        return {"primary": parts[0].strip(), "secondary": parts[1].strip() if len(parts)>1 else "", "type": task_type}
    except:
        return {"primary": "Error", "secondary": "", "type": "error"}

def evaluate_student(student_text, task_data, task_type):
    prompt = f"Úkol: {task_type}. Cíl: {task_data['primary']}. Student řekl: {student_text}. Ohodnoť česky, vysvětli chyby. Na konec dej [Correct English Sentence]."
    return client.chat.completions.create(
        model="llama-3.3-70b-versatile", messages=[{"role": "system", "content": prompt}]
    ).choices[0].message.content

# --- HLAVNÍ LOGIKA ---
def main():
    st.title("🦁 AI English Buddy")

    syllabus = load_syllabus()
    if not syllabus:
        st.error("Chybí syllabus.json!")
        st.stop()

    # Sidebar
    with st.sidebar:
        st.header("🗂️ Lekce")
        lesson_titles = [l['title'] for l in syllabus]
        selected_lesson = st.selectbox("Vyber lekci:", lesson_titles)
        if st.button("🔄 Restartovat lekci"):
            st.session_state.step = 0
            st.rerun()

    current_lesson = next(l for l in syllabus if l['title'] == selected_lesson)

    # --- BEZPEČNÁ INICIALIZACE STAVU (THE FIX) ---
    # Toto zajistí, že proměnné vždy existují
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
            audio_data = mic_recorder(start_prompt=f"🔴 Nahrát ({lang.upper()})", stop_prompt="⏹️ Odeslat", key=f"rec_{step}")
            
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
