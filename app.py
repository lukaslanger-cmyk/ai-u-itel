import streamlit as st
import asyncio
import edge_tts
from groq import Groq
from streamlit_mic_recorder import mic_recorder
import io
import time

# --- 1. KONFIGURACE APLIKACE ---
st.set_page_config(page_title="AI English Buddy", page_icon="🦁", layout="centered")

# CSS Styly - Čistý design pro děti
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
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }
    .feedback-box-success {
        background-color: #e8f5e9;
        padding: 15px;
        border-radius: 10px;
        border-left: 5px solid #4caf50;
        margin-top: 10px;
    }
    .feedback-box-error {
        background-color: #ffebee;
        padding: 15px;
        border-radius: 10px;
        border-left: 5px solid #f44336;
        margin-top: 10px;
    }
    h1 { color: #2E86C1; text-align: center; font-family: 'Comic Sans MS', sans-serif; }
    h3 { margin-bottom: 0px; }
</style>
""", unsafe_allow_html=True)

# Kontrola API klíče
try:
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
except:
    st.error("⚠️ CRITICAL ERROR: Chybí API klíč v Streamlit Secrets.")
    st.stop()

client = Groq(api_key=GROQ_API_KEY)

# --- 2. KOMPLETNÍ UČEBNICE (10 LEKCÍ) ---
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

# Definice typů úkolů
TASK_TYPES = {
    1: {"type": "listen", "name": "👂 Krok 1: Poslech", "instruction": "Poslouchej anglickou větu a řekni česky, co to znamená.", "lang_rec": "cs"},
    2: {"type": "imitate", "name": "🦜 Krok 2: Papoušek", "instruction": "Přečti a zopakuj anglickou větu přesně podle vzoru.", "lang_rec": "en"},
    3: {"type": "translate", "name": "✍️ Krok 3: Překladatel", "instruction": "Jak řekneš tuto větu anglicky?", "lang_rec": "en"},
    4: {"type": "respond", "name": "🗣️ Krok 4: Konverzace", "instruction": "Odpověz anglicky na otázku (podle pravdy).", "lang_rec": "en"},
    5: {"type": "boss", "name": "🏆 Krok 5: Boss Fight", "instruction": "Přelož tuto složitější větu.", "lang_rec": "en"}
}

# --- 3. POMOCNÉ FUNKCE ---

def reset_lesson():
    """Callback pro okamžitý reset."""
    st.session_state.step = 0
    st.session_state.task_data = None
    st.session_state.feedback = None
    st.session_state.theory_content = None

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
    """Generuje výklad."""
    prompt = f"""
    Jsi učitel angličtiny pro malé děti (8 let). Téma: {lesson_data['topic']}.
    Vysvětli látku česky, velmi jednoduše. Žádná složitá gramatika.
    Uveď 3 krátké příklady (EN - CZ).
    Buď stručný.
    """
    try:
        return client.chat.completions.create(
            model="llama-3.3-70b-versatile", messages=[{"role": "system", "content": prompt}]
        ).choices[0].message.content
    except:
        return "Učitel si rovná poznámky... Zkus to znovu."

def generate_task_data(lesson_data, step_number):
    """Generuje zadání úkolu - OMEZENO PRO DĚTI."""
    task_type = TASK_TYPES[step_number]["type"]
    topic = lesson_data['topic']
    
    # PŘÍSNÉ INSTRUKCE PRO AI, ABY NEVYMÝŠLELA MANAŽERY
    constraints = "Používej POUZE základní slovní zásobu pro děti (A1 level). Žádný business jazyk. Věty maximálně na 6 slov."
    
    prompt = f"""
    Generuj cvičení pro dítě. Téma: {topic}. Typ: {task_type}. {constraints}
    
    POKUD TYP 'listen': Vygeneruj jednoduchou EN větu a CZ překlad. Formát: EN|CZ
    POKUD TYP 'imitate': Vygeneruj jednoduchou EN větu. Formát: EN|CZ_VYZNAM
    POKUD TYP 'translate': Vygeneruj CZ větu a EN překlad. Formát: CZ|EN
    POKUD TYP 'respond': Vygeneruj jednoduchou EN otázku (např. What is your name?). Formát: EN_OTAZKA|TYPE_ANSWER
    POKUD TYP 'boss': Vygeneruj souvětí (např. I am happy and he is sad). Formát: CZ|EN
    
    ODPOVĚZ JEN: PRVNÍ_ČÁST|DRUHÁ_ČÁST
    """
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile", messages=[{"role": "system", "content": prompt}], temperature=0.3 # Nízká teplota pro menší kreativitu
        ).choices[0].message.content
        parts = response.split('|')
        return {"primary": parts[0].strip(), "secondary": parts[1].strip() if len(parts)>1 else "", "type": task_type}
    except:
        return {"primary": "Error", "secondary": "", "type": "error"}

def evaluate_student(student_text, task_data, task_type):
    """Hodnotí odpověď žáka - BEZ BUZERACE ZA TEČKY."""
    prompt = f"""
    Jsi hodný učitel pro děti. 
    Úkol: {task_type}. 
    Cíl (Target): "{task_data['primary']}" (nebo překlad "{task_data['secondary']}").
    Dítě řeklo (Transcript): "{student_text}".
    
    INSTRUKCE:
    1. Ignoruj interpunkci (tečky, čárky) v přepisu řeči.
    2. Pokud dítě řeklo stažený tvar (I'm) místo plného (I am), JE TO SPRÁVNĚ.
    3. Pokud je úkol 'respond', akceptuj jakoukoliv smysluplnou odpověď v angličtině.
    4. Pokud je úkol 'listen', dítě mělo říct český význam.
    
    Odpověz ve formátu:
    VERDIKT: (Perfektní / Dobře / Zkus to znovu)
    VYSVĚTLENÍ: (Česky, stručně, pro dítě. Pokud je chyba, vysvětli proč.)
    CORRECT: [Zde napiš správnou anglickou větu, pokud je to relevantní]
    """
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
        # Callback reset zajistí okamžitou reakci
        st.button("🔄 Restartovat lekci", on_click=reset_lesson)

    current_lesson = next(l for l in SYLLABUS_DATA if l['title'] == selected_lesson)

    # Inicializace
    if 'step' not in st.session_state: st.session_state.step = 0
    if 'current_lesson_id' not in st.session_state: st.session_state.current_lesson_id = current_lesson['id']
    
    # Změna lekce -> Auto Reset
    if st.session_state.current_lesson_id != current_lesson['id']:
        st.session_state.current_lesson_id = current_lesson['id']
        reset_lesson()
        st.rerun()

    # --- KROK 0: TEORIE ---
    if st.session_state.step == 0:
        st.markdown(f"## 🎓 {current_lesson['title']}")
        if not st.session_state.theory_content:
            with st.spinner("Příprava výkladu..."):
                st.session_state.theory_content = get_theory(current_lesson)
        
        st.info(st.session_state.theory_content)
        if st.button("Jdeme trénovat! 🚀", type="primary"):
            st.session_state.step = 1
            st.rerun()

    # --- KROKY 1-5: TRÉNINK ---
    elif st.session_state.step <= 5:
        step = st.session_state.step
        task_info = TASK_TYPES[step]
        
        # Progress bar
        st.progress(step/5, text=f"{task_info['name']}")

        # 1. Generování zadání (pokud není)
        if not st.session_state.task_data:
            with st.spinner("Vymýšlím úkol..."):
                data = generate_task_data(current_lesson, step)
                st.session_state.task_data = data
                st.session_state.feedback = None
                
                # Audio se generuje VŽDY u kroku 1 a 2, a volitelně u 4
                if data["type"] in ["listen", "imitate", "respond"]:
                    st.session_state.task_audio = asyncio.run(generate_audio_memory(data["primary"], "en"))
                else:
                    st.session_state.task_audio = None

        data = st.session_state.task_data
        
        # 2. Zobrazení úkolu (UI)
        st.markdown(f'<div class="task-box"><h3>{task_info["name"]}</h3><p style="color:gray">{task_info["instruction"]}</p>', unsafe_allow_html=True)
        
        # Specifické zobrazení podle typu
        if data["type"] == "listen":
            # Text je skrytý, jen audio
            if st.session_state.task_audio:
                st.audio(st.session_state.task_audio, format='audio/mp3')
            else:
                st.error("Chyba audia. Zkus restart.")
            st.write("❓ **Co tato věta znamená česky?**")
            
        elif data["type"] == "imitate":
            st.markdown(f"### 🗣️ {data['primary']}")
            if st.session_state.task_audio:
                st.audio(st.session_state.task_audio, format='audio/mp3')
                
        elif data["type"] == "translate":
            st.markdown(f"### 🇨🇿 {data['primary']}")
            
        elif data["type"] == "respond":
            st.markdown(f"### ❓ {data['primary']}")
            if st.session_state.task_audio:
                st.audio(st.session_state.task_audio, format='audio/mp3')
        
        elif data["type"] == "boss":
            st.markdown(f"### 🇨🇿 {data['primary']}")

        st.markdown('</div>', unsafe_allow_html=True)

        # 3. Sekce Odpovědi
        if st.session_state.feedback:
            # Zobrazení výsledku
            is_good = "Perfektní" in st.session_state.feedback or "Dobře" in st.session_state.feedback
            box_class = "feedback-box-success" if is_good else "feedback-box-error"
            
            st.markdown(f'<div class="{box_class}"><b>Hodnocení:</b><br>{st.session_state.feedback}</div>', unsafe_allow_html=True)
            
            if st.button("Další úkol ➡️", type="primary"):
                st.session_state.step += 1
                st.session_state.task_data = None
                st.rerun()
        else:
            # Nahrávání
            lang = task_info["lang_rec"]
            btn_label = f"🔴 Nahrát odpověď ({lang.upper()})"
            
            # Unikátní klíč pro rekordér
            audio_data = mic_recorder(start_prompt=btn_label, stop_prompt="⏹️ Odeslat", key=f"rec_{step}_{current_lesson['id']}")
            
            if audio_data:
                with st.spinner("Poslouchám..."):
                    bio = io.BytesIO(audio_data['bytes'])
                    bio.name = "audio.wav"
                    try:
                        transcript = client.audio.transcriptions.create(
                            file=(bio.name, bio.read()), model="whisper-large-v3-turbo", language=lang, response_format="text"
                        ).strip()
                        
                        st.info(f"Slyšel jsem: \"{transcript}\"")
                        
                        # Pokud Whisper nic neslyšel
                        if len(transcript) < 2:
                            st.warning("Nic jsem neslyšel, zkus to znovu.")
                        else:
                            st.session_state.feedback = evaluate_student(transcript, data, data["type"])
                            st.rerun()
                    except Exception as e:
                        st.error(f"Chyba: {e}")

    # --- KONEC ---
    else:
        st.balloons()
        st.success("🎉 Lekce dokončena! Jsi jednička!")
        if st.button("Zpět na začátek"):
            reset_lesson()
            st.rerun()

if __name__ == "__main__":
    main()
