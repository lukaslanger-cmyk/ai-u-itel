import streamlit as st
import asyncio
import edge_tts
from groq import Groq
from streamlit_mic_recorder import mic_recorder
import io
import time

# --- 1. KONFIGURACE APLIKACE ---
st.set_page_config(page_title="AI English Buddy", page_icon="🦁", layout="centered")

# CSS Styly
st.markdown("""
<style>
    .stButton>button {
        width: 100%;
        border-radius: 12px;
        height: 3.5em;
        font-weight: bold;
        font-size: 1.1em;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        border: 2px solid #eee;
    }
    .stButton>button:hover {
        border-color: #87CEEB;
        color: #2E86C1;
    }
    .task-box {
        background-color: #f8fbff;
        padding: 20px;
        border-radius: 15px;
        border: 2px solid #87CEEB;
        text-align: center;
        margin-bottom: 20px;
    }
    .feedback-box-success {
        background-color: #e8f5e9;
        padding: 15px;
        border-radius: 10px;
        border-left: 5px solid #4caf50;
        margin-top: 10px;
        text-align: left;
    }
    .feedback-box-error {
        background-color: #ffebee;
        padding: 15px;
        border-radius: 10px;
        border-left: 5px solid #f44336;
        margin-top: 10px;
        text-align: left;
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

# --- 2. UČEBNICE (HARDCODED - ABY SE NEZTRATILA) ---
SYLLABUS_DATA = [
  {"id": 1, "title": "1. Kdo jsem? (Sloveso TO BE)", "topic": "Verb TO BE (I am, You are, He is)", "goal": "Představit se a říct, kdo jsem."},
  {"id": 2, "title": "2. Kde to je? (IN, ON, UNDER)", "topic": "Prepositions (The cat is on the table)", "goal": "Popsat pozici věcí."},
  {"id": 3, "title": "3. Co mám? (HAVE GOT)", "topic": "Verb HAVE GOT (I have got a dog)", "goal": "Říct, co vlastním."},
  {"id": 4, "title": "4. Co umím? (CAN)", "topic": "Modal verb CAN (I can jump)", "goal": "Popsat schopnosti."},
  {"id": 5, "title": "5. Moje rodina (MY, YOUR)", "topic": "Family & Possessives (This is my mum)", "goal": "Představit rodinu."},
  {"id": 6, "title": "6. Co dělám teď? (Průběhový)", "topic": "Present Continuous (I am sleeping)", "goal": "Popsat aktuální činnost."},
  {"id": 7, "title": "7. Každý den (Rutina)", "topic": "Present Simple (I play tennis)", "goal": "Popsat zvyky."},
  {"id": 8, "title": "8. Otázky (Do you like...?)", "topic": "Questions & Short answers", "goal": "Zeptat se kamaráda."},
  {"id": 9, "title": "9. Oblečení a Barvy", "topic": "Clothes & Adjectives (Red t-shirt)", "goal": "Popsat oblečení."},
  {"id": 10, "title": "10. Jídlo (I like / I don't like)", "topic": "Food vocabulary", "goal": "Říct, co mi chutná."}
]

# Typy úkolů
TASK_TYPES = {
    1: {"type": "listen", "name": "👂 Krok 1: Poslech", "instruction": "Poslouchej anglickou větu a řekni česky, co to znamená.", "lang_rec": "cs"},
    2: {"type": "imitate", "name": "🦜 Krok 2: Papoušek", "instruction": "Přečti a zopakuj anglickou větu přesně podle vzoru.", "lang_rec": "en"},
    3: {"type": "translate", "name": "✍️ Krok 3: Překladatel", "instruction": "Jak řekneš tuto větu anglicky?", "lang_rec": "en"},
    4: {"type": "respond", "name": "🗣️ Krok 4: Konverzace", "instruction": "Odpověz anglicky na otázku (podle pravdy).", "lang_rec": "en"},
    5: {"type": "boss", "name": "🏆 Krok 5: Boss Fight", "instruction": "Přelož tuto složitější větu.", "lang_rec": "en"}
}

# --- 3. FUNKCE ---

def init_session_state():
    """Záchranná brzda - Inicializuje proměnné, aby aplikace nespadla."""
    defaults = {
        'step': 0,
        'current_lesson_id': 1,
        'theory_content': None,
        'task_data': None,
        'feedback': None,
        'task_audio': None
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

def reset_lesson():
    """Callback pro restart."""
    st.session_state.step = 0
    st.session_state.task_data = None
    st.session_state.feedback = None
    st.session_state.theory_content = None

async def generate_audio_memory(text, lang="en"):
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
    prompt = f"""
    Jsi učitel pro děti (8 let). Téma: {lesson_data['topic']}.
    Vysvětli látku česky, jednoduše. Žádné složitosti.
    Uveď 3 příklady (EN - CZ).
    """
    try:
        return client.chat.completions.create(
            model="llama-3.3-70b-versatile", messages=[{"role": "system", "content": prompt}]
        ).choices[0].message.content
    except:
        return "Chyba při načítání teorie."

def generate_task_data(lesson_data, step_number):
    task_type = TASK_TYPES[step_number]["type"]
    topic = lesson_data['topic']
    
    constraints = "Používej POUZE slovní zásobu pro děti (A1). Žádný business jazyk."
    
    prompt = f"""
    Generuj cvičení. Téma: {topic}. Typ: {task_type}. {constraints}
    
    TYP 'listen': EN věta + CZ překlad (EN|CZ)
    TYP 'imitate': EN věta (EN|CZ_VYZNAM)
    TYP 'translate': CZ věta + EN překlad (CZ|EN)
    TYP 'respond': EN otázka (EN_OTAZKA|ANSWER_TYPE)
    TYP 'boss': CZ souvětí + EN překlad (CZ|EN)
    
    ODPOVĚZ JEN: PART1|PART2
    """
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile", messages=[{"role": "system", "content": prompt}], temperature=0.3
        ).choices[0].message.content
        parts = response.split('|')
        return {"primary": parts[0].strip(), "secondary": parts[1].strip() if len(parts)>1 else "", "type": task_type}
    except:
        return {"primary": "Error", "secondary": "", "type": "error"}

def evaluate_student(student_text, task_data, task_type):
    prompt = f"""
    Jsi hodný učitel. Úkol: {task_type}. Cíl: "{task_data['primary']}". 
    Dítě řeklo: "{student_text}".
    
    1. Ignoruj interpunkci.
    2. Pokud je to významově správně, pochval.
    3. Vysvětli chyby česky.
    
    Odpověz: VERDIKT (Perfektní/Dobře/Zkus to)|VYSVĚTLENÍ|CORRECT_EN
    """
    try:
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile", messages=[{"role": "system", "content": prompt}]
        ).choices[0].message.content
        return resp # Vrátíme celý string a zpracujeme v UI
    except:
        return "Chyba|Zkus to znovu.|-"

# --- 4. HLAVNÍ LOGIKA ---
def main():
    # 1. INICIALIZACE STAVU (MUST BE FIRST)
    init_session_state()

    st.title("🦁 AI English Buddy")

    # Sidebar
    with st.sidebar:
        st.header("🗂️ Lekce")
        lesson_titles = [l['title'] for l in SYLLABUS_DATA]
        selected_lesson = st.selectbox("Vyber lekci:", lesson_titles)
        st.button("🔄 Restartovat lekci", on_click=reset_lesson)

    # Určení aktuální lekce
    current_lesson_obj = next(l for l in SYLLABUS_DATA if l['title'] == selected_lesson)

    # Detekce změny lekce
    if st.session_state.current_lesson_id != current_lesson_obj['id']:
        st.session_state.current_lesson_id = current_lesson_obj['id']
        reset_lesson()
        st.rerun()

    # KROK 0: TEORIE
    if st.session_state.step == 0:
        st.markdown(f"## 🎓 {current_lesson_obj['title']}")
        if not st.session_state.theory_content:
            with st.spinner("Příprava výkladu..."):
                st.session_state.theory_content = get_theory(current_lesson_obj)
        
        st.info(st.session_state.theory_content)
        if st.button("Jdeme trénovat! 🚀", type="primary"):
            st.session_state.step = 1
            st.rerun()

    # KROKY 1-5
    elif st.session_state.step <= 5:
        step = st.session_state.step
        task_info = TASK_TYPES[step]
        st.progress(step/5, text=f"{task_info['name']}")

        # Generování zadání
        if not st.session_state.task_data:
            with st.spinner("Vymýšlím úkol..."):
                data = generate_task_data(current_lesson_obj, step)
                st.session_state.task_data = data
                st.session_state.feedback = None
                
                if data["type"] in ["listen", "imitate", "respond"]:
                    st.session_state.task_audio = asyncio.run(generate_audio_memory(data["primary"], "en"))
                else:
                    st.session_state.task_audio = None

        data = st.session_state.task_data
        
        # UI Zadání
        st.markdown(f'<div class="task-box"><h3>{task_info["name"]}</h3><p style="color:gray">{task_info["instruction"]}</p>', unsafe_allow_html=True)
        
        if data["type"] == "listen":
            if st.session_state.task_audio: st.audio(st.session_state.task_audio, format='audio/mp3')
            st.write("❓ **Co to znamená česky?**")
        elif data["type"] == "imitate":
            st.markdown(f"### 🗣️ {data['primary']}")
            if st.session_state.task_audio: st.audio(st.session_state.task_audio, format='audio/mp3')
        elif data["type"] == "translate":
            st.markdown(f"### 🇨🇿 {data['primary']}")
        elif data["type"] == "respond":
            st.markdown(f"### ❓ {data['primary']}")
            if st.session_state.task_audio: st.audio(st.session_state.task_audio, format='audio/mp3')
        elif data["type"] == "boss":
            st.markdown(f"### 🇨🇿 {data['primary']}")

        st.markdown('</div>', unsafe_allow_html=True)

        # UI Feedback / Nahrávání
        if st.session_state.feedback:
            # Rozparsování odpovědi evaluátora (Verdikt|Vysvětlení|Correct)
            parts = st.session_state.feedback.split('|')
            verdict = parts[0] if len(parts) > 0 else "Hodnocení"
            explanation = parts[1] if len(parts) > 1 else str(st.session_state.feedback)
            correct_en = parts[2] if len(parts) > 2 else ""

            is_good = "Perfektní" in verdict or "Dobře" in verdict
            box_class = "feedback-box-success" if is_good else "feedback-box-error"

            st.markdown(f'<div class="{box_class}"><b>{verdict}</b><br>{explanation}</div>', unsafe_allow_html=True)
            if correct_en and len(correct_en) > 2:
                 st.info(f"Correct English: {correct_en}")

            if st.button("Další úkol ➡️", type="primary"):
                st.session_state.step += 1
                st.session_state.task_data = None
                st.rerun()
        else:
            lang = task_info["lang_rec"]
            btn_txt = f"🔴 Nahrát odpověď ({lang.upper()})"
            audio_data = mic_recorder(start_prompt=btn_txt, stop_prompt="⏹️ Odeslat", key=f"rec_{step}_{current_lesson_obj['id']}")
            
            if audio_data:
                with st.spinner("Poslouchám..."):
                    bio = io.BytesIO(audio_data['bytes'])
                    bio.name = "audio.wav"
                    try:
                        transcript = client.audio.transcriptions.create(
                            file=(bio.name, bio.read()), model="whisper-large-v3-turbo", language=lang, response_format="text"
                        ).strip()
                        
                        st.info(f"Slyšel jsem: \"{transcript}\"")
                        if len(transcript) < 1:
                            st.warning("Nic jsem neslyšel.")
                        else:
                            st.session_state.feedback = evaluate_student(transcript, data, data["type"])
                            st.rerun()
                    except Exception as e:
                        st.error(f"Chyba: {e}")

    else:
        st.balloons()
        st.success("🎉 Lekce dokončena!")
        if st.button("Zpět na začátek"):
            reset_lesson()
            st.rerun()

if __name__ == "__main__":
    main()
