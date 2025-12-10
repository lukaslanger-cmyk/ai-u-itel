import streamlit as st
import json
import asyncio
import edge_tts
from groq import Groq
from streamlit_mic_recorder import mic_recorder
import io
import re

# --- KONFIGURACE PROSTŘEDÍ ---
st.set_page_config(page_title="AI English Teacher", page_icon="🦁", layout="centered")

# CSS Styly (Design na míru pro děti)
st.markdown("""
<style>
    .stButton>button {
        width: 100%;
        border-radius: 12px;
        height: 3.5em;
        font-weight: bold;
        font-size: 1.1em;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        transition: 0.3s;
    }
    .stButton>button:hover { transform: scale(1.02); }
    
    .task-box {
        background-color: #f0f8ff;
        padding: 25px;
        border-radius: 15px;
        border: 2px solid #87CEEB;
        text-align: center;
        margin-bottom: 20px;
    }
    .hidden-text {
        background-color: #eee;
        color: #eee;
        border-radius: 5px;
        user-select: none;
    }
    .hidden-text:hover { color: #333; } /* Cheat pro rodiče */
    
    h1 { color: #2E86C1; text-align: center; }
    h3 { color: #154360; }
</style>
""", unsafe_allow_html=True)

# API KLÍČ
try:
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
except:
    st.error("⚠️ CRITICAL ERROR: Chybí API klíč v Streamlit Secrets.")
    st.stop()

client = Groq(api_key=GROQ_API_KEY)

# --- DEFINICE TYPŮ ÚKOLŮ ---
TASK_TYPES = {
    1: {"type": "listen", "name": "👂 Poslech (Co to znamená?)", "lang_expect": "cs"},
    2: {"type": "imitate", "name": "🦜 Papoušek (Opakuj přesně)", "lang_expect": "en"},
    3: {"type": "translate", "name": "✍️ Překladatel (Řekni anglicky)", "lang_expect": "en"},
    4: {"type": "respond", "name": "🗣️ Konverzace (Odpověz na otázku)", "lang_expect": "en"},
    5: {"type": "boss", "name": "🏆 Boss Fight (Komplexní úkol)", "lang_expect": "en"}
}

# --- FUNKCE: AUDIO ENGINE (RAM) ---
async def generate_audio_memory(text, lang="en"):
    """Generuje audio přímo do paměti. Odolné proti pádům."""
    try:
        voice = "en-US-AnaNeural" # Výchozí učitelka
        if lang == "cs":
            voice = "cs-CZ-VlastaNeural" # Česká vysvětlovačka
        
        # Čištění textu (odstranění markdownu pro čtečku)
        clean_text = text.replace("**", "").replace("*", "").replace("`", "").replace("🦁", "")
        
        communicate = edge_tts.Communicate(clean_text, voice)
        mp3_fp = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                mp3_fp.write(chunk["data"])
        mp3_fp.seek(0)
        return mp3_fp
    except Exception as e:
        return None

# --- FUNKCE: AI MOZEK ---
def load_syllabus():
    try:
        with open('syllabus.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return []

def get_theory(lesson_data):
    prompt = f"""
    Jsi učitel angličtiny. Téma: {lesson_data['topic']}.
    Vysvětli látku česky, jednoduše, zábavně (pro děti).
    Uveď 3 příklady (EN - CZ). Formátuj pomocí Markdown.
    """
    return client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "system", "content": prompt}],
        temperature=0.3
    ).choices[0].message.content

def generate_task_data(lesson_data, step_number):
    """
    Generuje zadání pro konkrétní typ úkolu.
    Vrací slovník: {instruction_cz, en_sentence, hidden}
    """
    task_type = TASK_TYPES[step_number]["type"]
    topic = lesson_data['topic']
    
    # Prompting pro různé typy úkolů
    specific_instruction = ""
    if task_type == "listen":
        specific_instruction = "Vygeneruj jednoduchou anglickou větu k tématu. Výstupní formát: EN_VETA|CZ_PREKLAD"
    elif task_type == "imitate":
        specific_instruction = "Vygeneruj krátkou anglickou frázi k výslovnosti. Výstupní formát: EN_VETA|CZ_VYZNAM"
    elif task_type == "translate":
        specific_instruction = "Vygeneruj českou větu k překladu. Výstupní formát: CZ_VETA|SPRAVNY_EN_PREKLAD"
    elif task_type == "respond":
        specific_instruction = "Vygeneruj jednoduchou anglickou otázku k tématu. Výstupní formát: EN_OTAZKA|OČEKÁVANÁ_ODPOVĚĎ_TYP"
    elif task_type == "boss":
        specific_instruction = "Vygeneruj těžší větu na překlad (mix). Výstupní formát: CZ_VETA|EN_PREKLAD"

    prompt = f"""
    Jsi generátor cvičení. Téma: {topic}. Typ: {task_type}.
    {specific_instruction}
    ODPOVĚZ POUZE POŽADOVANÝM FORMÁTEM S ODDĚLOVAČEM '|'. Žádné omáčky okolo.
    """
    
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "system", "content": prompt}]
    ).choices[0].message.content

    # Zpracování odpovědi (Robustní parsing)
    try:
        parts = response.split('|')
        primary = parts[0].strip()
        secondary = parts[1].strip() if len(parts) > 1 else ""
        return {"primary": primary, "secondary": secondary, "type": task_type}
    except:
        return {"primary": "Error generating task", "secondary": "", "type": "error"}

def evaluate_student(student_text, task_data, task_type):
    """
    Chytrý hodnotitel - mění chování podle typu úkolu.
    """
    prompt = ""
    target = task_data["primary"]
    secondary = task_data["secondary"]

    if task_type == "listen":
        # Student mluví česky, ověřujeme pochopení anglické věty
        prompt = f"""
        Úkol: Poslech. Anglická věta byla: "{target}".
        Dítě řeklo česky: "{student_text}".
        Odpovídá to významově? (Ano/Ne). Pokud ne, vysvětli česky proč.
        Pochval česky.
        """
    elif task_type == "imitate":
        # Student opakuje anglicky
        prompt = f"""
        Úkol: Imitace. Cíl: "{target}". Dítě řeklo: "{student_text}".
        Je výslovnost a text správně? Ignoruj malé chyby.
        Odpověz česky.
        """
    elif task_type == "translate" or task_type == "boss":
        # Student překládá z CZ do EN
        prompt = f"""
        Úkol: Překlad. Zadání (CZ): "{target}". Správně (EN): "{secondary}".
        Dítě řeklo: "{student_text}".
        Je to gramaticky správně? Vysvětli chyby česky.
        Na konec dej do hranatých závorek správnou verzi [Correct English].
        """
    elif task_type == "respond":
        # Student odpovídá na otázku
        prompt = f"""
        Úkol: Konverzace. Otázka: "{target}".
        Dítě odpovědělo: "{student_text}".
        Dává odpověď smysl v kontextu? Je gramaticky OK?
        Odpověz česky.
        Na konec navrhni vylepšenou odpověď do závorek [Better answer].
        """

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "system", "content": prompt}]
    ).choices[0].message.content
    return response

# --- HLAVNÍ APLIKACE (UI) ---
def main():
    st.title("🦁 AI English Buddy")

    # Načtení osnovy
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

    # Session State Init
    if 'current_lesson_id' not in st.session_state or st.session_state.current_lesson_id != current_lesson['id']:
        st.session_state.current_lesson_id = current_lesson['id']
        st.session_state.step = 0
        st.session_state.theory_content = None
        st.session_state.task_data = None
        st.session_state.feedback = None
        st.session_state.task_audio = None # Audio zadání

    # --- KROK 0: TEORIE ---
    if st.session_state.step == 0:
        st.markdown(f"## 🎓 {current_lesson['title']}")
        if not st.session_state.theory_content:
            with st.spinner("Příprava materiálů..."):
                st.session_state.theory_content = get_theory(current_lesson)
        
        st.info(st.session_state.theory_content)
        
        if st.button("Jdeme trénovat! 🚀", type="primary"):
            st.session_state.step = 1
            st.session_state.task_data = None
            st.rerun()

    # --- KROKY 1-5: TRÉNINKOVÝ CYKLUS ---
    elif st.session_state.step <= 5:
        step = st.session_state.step
        task_info = TASK_TYPES[step]
        
        # Progress bar
        st.progress(step / 5, text=f"Krok {step}/5: {task_info['name']}")

        # 1. Generování zadání (pokud není)
        if not st.session_state.task_data:
            with st.spinner("Generuji úkol..."):
                data = generate_task_data(current_lesson, step)
                st.session_state.task_data = data
                st.session_state.feedback = None
                
                # Předgenerování audia pro zadání (pokud je třeba slyšet EN)
                if data["type"] in ["listen", "imitate", "respond"]:
                    st.session_state.task_audio = asyncio.run(generate_audio_memory(data["primary"], "en"))
                else:
                    st.session_state.task_audio = None

        data = st.session_state.task_data

        # 2. Zobrazení zadání (UI)
        st.markdown(f'<div class="task-box">', unsafe_allow_html=True)
        
        # Logika pro zobrazení obsahu podle typu
        if data["type"] == "listen":
            st.markdown("### 🔊 Poslouchej a přelož do češtiny")
            st.write("*(Text je skrytý, musíš použít uši!)*")
            if st.session_state.task_audio:
                st.audio(st.session_state.task_audio, format='audio/mp3', autoplay=False)
        
        elif data["type"] == "imitate":
            st.markdown("### 🦜 Poslouchej a zopakuj přesně anglicky")
            st.markdown(f"**{data['primary']}**")
            if st.session_state.task_audio:
                st.audio(st.session_state.task_audio, format='audio/mp3', autoplay=False)

        elif data["type"] == "translate" or data["type"] == "boss":
            st.markdown("### ✍️ Řekni tuto větu anglicky")
            st.markdown(f"**{data['primary']}**")

        elif data["type"] == "respond":
            st.markdown("### 🗣️ Odpověz na otázku anglicky")
            st.markdown(f"**{data['primary']}**")
            if st.session_state.task_audio:
                st.audio(st.session_state.task_audio, format='audio/mp3', autoplay=False)

        st.markdown('</div>', unsafe_allow_html=True)

        # 3. Nahrávání a Vyhodnocení
        if st.session_state.feedback:
            # Zobrazení výsledku
            st.success("Hodnocení:")
            st.write(st.session_state.feedback)
            st.button("Další úkol ➡️", on_click=lambda: next_step())
        else:
            # Rozhodnutí, jaký jazyk čekáme od Whisperu
            whisper_lang = task_info["lang_expect"] # 'cs' nebo 'en'
            btn_text = "🔴 Nahrát odpověď (CZ)" if whisper_lang == "cs" else "🔴 Nahrát odpověď (EN)"

            audio_data = mic_recorder(start_prompt=btn_text, stop_prompt="⏹️ Odeslat", key=f"rec_{step}")

            if audio_data:
                with st.spinner("Poslouchám a opravuji..."):
                    # Whisper Transkripce
                    bio = io.BytesIO(audio_data['bytes'])
                    bio.name = "audio.wav"
                    try:
                        transcript = client.audio.transcriptions.create(
                            file=(bio.name, bio.read()),
                            model="whisper-large-v3-turbo",
                            language=whisper_lang, # Důležité: Přepínání jazyka!
                            response_format="text"
                        ).strip()
                        
                        st.info(f"Slyšel jsem: {transcript}")
                        
                        # AI Evaluace
                        feedback = evaluate_student(transcript, data, data["type"])
                        st.session_state.feedback = feedback
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"Chyba: {e}")

    # --- KONEC LEKCE ---
    else:
        st.balloons()
        st.success("🎉 Lekce dokončena!")
        if st.button("Zpět na začátek"):
            st.session_state.step = 0
            st.rerun()

def next_step():
    st.session_state.step += 1
    st.session_state.task_data = None
    st.session_state.task_audio = None

if __name__ == "__main__":
    main()
