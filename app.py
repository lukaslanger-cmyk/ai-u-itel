import streamlit as st
from groq import Groq
from streamlit_mic_recorder import mic_recorder
import io
from gtts import gTTS
import re

# --- 1. KONFIGURACE APLIKACE & CSS ---
st.set_page_config(page_title="AI English Teacher Pro", page_icon="🎓", layout="wide")

st.markdown("""
<style>
    .main { background-color: #ffffff; }
    section[data-testid="stSidebar"] { background-color: #f7f9fc; border-right: 1px solid #e0e0e0; }
    .sidebar-header { font-size: 1.2em; font-weight: bold; color: #1e3a8a; margin-bottom: 10px; border-bottom: 2px solid #1e3a8a; padding-bottom: 5px; }
    
    /* Tlačítka */
    .stButton>button { width: 100%; border-radius: 8px; height: 3em; font-weight: 600; border: none; background-color: #2563eb; color: white; transition: all 0.2s; }
    .stButton>button:hover { background-color: #1d4ed8; transform: translateY(-2px); box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
    
    /* Speciální styl pro tlačítko "Jiná věta" (šedé) */
    div[data-testid="column"] .stButton>button[kind="secondary"] {
        background-color: #f1f5f9; 
        color: #334155; 
        border: 1px solid #cbd5e1;
    }
    div[data-testid="column"] .stButton>button[kind="secondary"]:hover {
        background-color: #e2e8f0;
        border-color: #94a3b8;
    }

    .task-card { background: linear-gradient(135deg, #ffffff 0%, #f0f9ff 100%); padding: 30px; border-radius: 20px; border: 1px solid #bae6fd; box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1); text-align: center; margin-bottom: 25px; }
    
    /* Feedback boxy - čisté CSS bez HTML chyb */
    .feedback-container {
        padding: 20px;
        border-radius: 12px;
        margin-top: 15px;
        text-align: left;
        font-size: 1.05em;
        line-height: 1.6;
    }
    .fb-success { background-color: #dcfce7; border-left: 5px solid #22c55e; color: #14532d; }
    .fb-error { background-color: #fee2e2; border-left: 5px solid #ef4444; color: #7f1d1d; }
    
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

# --- 2. SYLABUS ---
SYLLABUS_DATA = [
  {"id": 1, "title": "1. Být či nebýt? (TO BE)", "topic": "Verb TO BE (Singular: I am, You are, He is / Plural: We are, They are) + Negatives (I am not)", "goal": "Umět používat sloveso BÝT v jednotném i množném čísle a v záporu."},
  {"id": 2, "title": "2. Kde co leží? (Předložky)", "topic": "Prepositions (in, on, under, next to, behind)", "goal": "Určit polohu věcí (jedné i více)."},
  {"id": 3, "title": "3. Mít či nemít? (HAVE GOT)", "topic": "Verb HAVE GOT (Singular & Plural) + Questions (Have you got?)", "goal": "Mluvit o vlastnictví věcí a zvířat."},
  {"id": 4, "title": "4. Superman (CAN / CAN'T)", "topic": "Modal verb CAN (Schopnosti)", "goal": "Říct, co umíme a co neumíme my i ostatní."},
  {"id": 5, "title": "5. Moje rodina (MY, YOUR...)", "topic": "Possessives (My, Your, Our, Their) + Family members", "goal": "Představit členy rodiny a čí co je."}
]

TASK_TYPES = {
    1: {"type": "listen", "name": "👂 Krok 1: Porozumění (Poslech)", "instruction": "Poslouchej a nahrej český překlad.", "lang_rec": "cs"},
    2: {"type": "imitate", "name": "🦜 Krok 2: Výslovnost (Papoušek)", "instruction": "Poslouchej a nahrej, jak to vyslovuješ (anglicky).", "lang_rec": "en"},
    3: {"type": "translate", "name": "✍️ Krok 3: Překlad (Dril)", "instruction": "Přečti si českou větu a nahrej anglický překlad.", "lang_rec": "en"},
    4: {"type": "respond", "name": "🗣️ Krok 4: Konverzace (Reakce)", "instruction": "Poslouchej otázku a nahrej anglickou odpověď.", "lang_rec": "en"},
    5: {"type": "boss", "name": "🏆 Krok 5: Boss Fight (Výzva)", "instruction": "Těžší věta. Dej si pozor na gramatiku!", "lang_rec": "en"}
}

# --- 3. FUNKCE ---

def init_session():
    defaults = {
        'step': 0,
        'current_lesson_index': 0,
        'theory_content': None,
        'task_data': None,
        'feedback': None,
        'task_audio_bytes': None
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

def generate_audio_google(text, lang="en"):
    """Generuje audio pomocí Google TTS."""
    try:
        # Čištění textu od AI balastu (např. "PART1: Hello")
        clean_text = text
        if ":" in clean_text:
            clean_text = clean_text.split(":")[-1].strip()
        clean_text = clean_text.replace("*", "").replace("`", "").replace('"', "")
        
        tts = gTTS(text=clean_text, lang=lang, slow=False)
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        return fp.getvalue()
    except Exception as e:
        print(f"Chyba zvuku: {e}")
        return None

def get_theory(lesson_data):
    prompt = f"""
    Jsi učitel. Téma: {lesson_data['topic']}.
    Vysvětli látku dětem (8-12 let).
    POŽADAVKY:
    1. Vysvětli jednotné číslo (Já/Ty) I množné číslo (My/Vy/Oni).
    2. Vysvětli zápor.
    3. Uveď 4 jasné příklady.
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
    
    # Zvýšená teplota (0.7) pro větší náhodnost vět
    prompt = f"""
    Generuj náhodné cvičení. Téma: {topic}. Typ: {task_type}.
    INSTRUKCE: Používej slovní zásobu A1/A2. 
    DŮLEŽITÉ: NEPOUŽÍVEJ ŽÁDNÉ UVOZOVIKY ANI NÁZVY PRO ČÁSTI. JEN ČISTÝ TEXT S ODDĚLOVAČEM "|||".
    
    Formáty výstupu (přísně dodržuj):
    LISTEN -> Anglická věta|||Český překlad
    IMITATE -> Anglická věta|||Český význam
    TRANSLATE -> Česká věta|||Anglický překlad
    RESPOND -> Anglická otázka|||Typ odpovědi
    BOSS -> Česká složitější věta|||Anglický překlad
    
    Příklad výstupu:
    They are happy|||Oni jsou šťastní
    """
    try:
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile", messages=[{"role": "system", "content": prompt}], temperature=0.7
        ).choices[0].message.content
        parts = resp.split('|||')
        return {"primary": parts[0].strip(), "secondary": parts[1].strip() if len(parts)>1 else "", "type": task_type}
    except: return {"primary": "Error", "secondary": "", "type": "error"}

def evaluate_student(student_text, task_data, task_type):
    prompt = f"""
    Jsi učitel. Úkol: {task_type}. Cíl: "{task_data['primary']}" (nebo "{task_data['secondary']}").
    Dítě řeklo: "{student_text}".
    
    Pravidla:
    1. Ignoruj interpunkci a velikost písmen.
    2. Uznej zkrácené tvary (I'm = I am).
    3. U poslechových cvičení kontroluj význam (ne doslovnost).
    
    Výstupní formát (přesně):
    VERDIKT: (Výborně / Dobře / Pozor)
    VYSVĚTLENÍ: (Vysvětlení česky)
    CORRECT: (Správná anglická věta - jen pokud dává smysl ji uvést)
    """
    try:
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile", messages=[{"role": "system", "content": prompt}]
        ).choices[0].message.content
        return resp
    except: return "VERDIKT: Chyba\nVYSVĚTLENÍ: Zkus to znovu.\nCORRECT: -"

# --- 4. HLAVNÍ LOGIKA ---
def main():
    init_session()

    # --- LEVÝ PANEL ---
    with st.sidebar:
        st.markdown("""<div class="sidebar-header">🦁 Můj profil</div>""", unsafe_allow_html=True)
        st.caption("Student: **Začátečník**")
        st.progress(st.session_state.current_lesson_index / len(SYLLABUS_DATA), text="Celkový postup")
        
        st.markdown("---")
        st.markdown("""<div class="sidebar-header">📚 Učebnice</div>""", unsafe_allow_html=True)
        
        titles = [l['title'] for l in SYLLABUS_DATA]
        selected_title = st.radio(
            "Vyber lekci:", titles, 
            index=st.session_state.current_lesson_index,
            label_visibility="collapsed"
        )
        
        new_index = titles.index(selected_title)
        if new_index != st.session_state.current_lesson_index:
            st.session_state.current_lesson_index = new_index
            reset_lesson()
            st.rerun()

        st.markdown("---")
        if st.button("🔄 Restartovat tuto lekci"):
            reset_lesson()
            st.rerun()

    # --- HLAVNÍ OKNO ---
    current_lesson = SYLLABUS_DATA[st.session_state.current_lesson_index]

    # KROK 0: TEORIE
    if st.session_state.step == 0:
        st.markdown(f"# 🎓 {current_lesson['title']}")
        
        if not st.session_state.theory_content:
            with st.spinner("Paní učitelka píše na tabuli..."):
                st.session_state.theory_content = get_theory(current_lesson)
        
        st.info(st.session_state.theory_content)
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("Jdeme trénovat! 🚀"):
                st.session_state.step = 1
                st.rerun()

    # KROKY 1-5: CVIČENÍ
    elif st.session_state.step <= 5:
        step = st.session_state.step
        task_info = TASK_TYPES[step]
        
        st.caption(f"Lekce {current_lesson['id']} • Úkol {step} z 5")
        st.progress(step/5)

        # GENERUJ DATA
        if st.session_state.task_data is None:
            with st.spinner("Vymýšlím zadání..."):
                data = generate_task_data(current_lesson, step)
                st.session_state.task_data = data
                st.session_state.feedback = None
                
                # AUDIO
                if data["type"] in ["listen", "imitate", "respond"]:
                    audio_bytes = generate_audio_google(data["primary"], "en")
                    st.session_state.task_audio_bytes = audio_bytes
                else:
                    st.session_state.task_audio_bytes = None

        data = st.session_state.task_data

        # VIZUÁL KARTY
        st.markdown(f"""
        <div class="task-card">
            <h3>{task_info['name']}</h3>
            <p style="color:#555; font-style:italic;">{task_info['instruction']}</p>
        </div>
        """, unsafe_allow_html=True)
        
        col_c, col_content, col_d = st.columns([1, 4, 1])
        with col_content:
            
            # --- ZOBRAZENÍ OBSAHU ---
            if data["type"] == "listen":
                if st.session_state.task_audio_bytes:
                    st.audio(st.session_state.task_audio_bytes, format='audio/mp3')
                st.markdown("<h3 style='text-align:center'>❓ ???</h3>", unsafe_allow_html=True)
                
            elif data["type"] in ["imitate", "respond"]:
                st.markdown(f"<h2 style='text-align:center; color:#2563eb'>{data['primary']}</h2>", unsafe_allow_html=True)
                if st.session_state.task_audio_bytes:
                    st.audio(st.session_state.task_audio_bytes, format='audio/mp3')
            
            elif data["type"] in ["translate", "boss"]:
                st.markdown(f"<h2 style='text-align:center; color:#2563eb'>🇨🇿 {data['primary']}</h2>", unsafe_allow_html=True)

            # TLAČÍTKO "JINÁ VĚTA"
            st.markdown("<br>", unsafe_allow_html=True)
            if not st.session_state.feedback:
                cols = st.columns([1, 1])
                with cols[0]:
                    # Toto je to tlačítko, co jsi chtěl
                    if st.button("🔄 Zkusit jinou větu"):
                        st.session_state.task_data = None
                        st.rerun()
            
            st.markdown("---")
            
            # --- FEEDBACK / NAHRÁVÁNÍ ---
            if st.session_state.feedback:
                # Robustní parsování textu
                text = st.session_state.feedback
                verdict = "Info"
                expl = text
                corr = ""
                
                if "VERDIKT:" in text:
                    verdict = text.split("VERDIKT:")[1].split("\n")[0].strip()
                if "VYSVĚTLENÍ:" in text:
                    expl = text.split("VYSVĚTLENÍ:")[1].split("CORRECT:")[0].strip()
                if "CORRECT:" in text:
                    corr = text.split("CORRECT:")[1].strip()

                is_good = "Výborně" in verdict or "Dobře" in verdict or "Perfektní" in verdict
                css_class = "fb-success" if is_good else "fb-error"
                icon = "✅" if is_good else "⚠️"
                
                # Čisté HTML bez rozbitých divů
                st.markdown(f"""
                <div class="feedback-container {css_class}">
                    <strong>{icon} {verdict}</strong><br>
                    {expl}
                </div>
                """, unsafe_allow_html=True)
                
                if corr and len(corr) > 2 and not is_good:
                    st.info(f"Správně: {corr}")
                
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    if st.button("🔄 Ještě jednu větu (trénink)"):
                        st.session_state.task_data = None
                        st.rerun()
                with col_btn2:
                    if st.button("Další úkol ➡️", type="primary"):
                        st.session_state.step += 1
                        st.session_state.task_data = None
                        st.rerun()
            else:
                lang = task_info["lang_rec"]
                audio_data = mic_recorder(
                    start_prompt=f"🎙️ Nahrát ({lang.upper()})", 
                    stop_prompt="⏹️ Odeslat", 
                    key=f"rec_{step}_{current_lesson['id']}"
                )
                
                if audio_data:
                    with st.spinner("Poslouchám..."):
                        bio = io.BytesIO(audio_data['bytes'])
                        bio.name = "audio.wav"
                        try:
                            txt = client.audio.transcriptions.create(
                                file=(bio.name, bio.read()), model="whisper-large-v3-turbo", language=lang, response_format="text"
                            ).strip()
                            st.caption(f"Slyšel jsem: {txt}")
                            if len(txt) < 1: st.warning("Mluvte hlasitěji.")
                            else:
                                st.session_state.feedback = evaluate_student(txt, data, data["type"])
                                st.rerun()
                        except Exception as e: st.error(str(e))

    else:
        st.canvas_balloons()
        st.markdown(f"""
        <div class="task-card" style="background-color:#dcfce7;">
            <h1>🎉 Gratuluji!</h1>
            <p>Lekce {current_lesson['title']} je hotová.</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Zpět na přehled"):
            reset_lesson()
            st.rerun()

if __name__ == "__main__":
    main()
