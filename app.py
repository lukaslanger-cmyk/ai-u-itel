import streamlit as st
from groq import Groq
from streamlit_mic_recorder import mic_recorder
import io
from gtts import gTTS

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
    """Generuje audio pomocí Google TTS (Stabilní verze)."""
    try:
        # Odstranění markdownu pro čisté čtení
        clean_text = text.replace("**", "").replace("*", "").replace("`", "")
        # Google TTS
        tts = gTTS(text=clean_text, lang=lang, slow=False)
        # Uložení do paměti
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        return fp.getvalue()
    except Exception as e:
        print(f"Chyba zvuku: {e}")
        return None

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
                
                # AUDIO GENERUJEME PŘES GOOGLE (STABILNÍ)
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
            
            # --- ZOBRAZENÍ AUDIA ---
            if data["type"] in ["listen", "imitate", "respond"]:
                if st.session_state.task_audio_bytes:
                    st.audio(st.session_state.task_audio_bytes, format='audio/mp3')
                else:
                    st.warning("Zvuk se nenačetl.")
                    if st.button("🔄 Zkusit načíst zvuk znovu"):
                        st.session_state.task_data = None
                        st.rerun()

            # --- ZOBRAZENÍ TEXTU ---
            if data["type"] == "listen":
                st.markdown("<h3 style='text-align:center'>❓ ???</h3>", unsafe_allow_html=True)
                
            elif data["type"] == "imitate":
                st.markdown(f"<h2 style='text-align:center; color:#2563eb'>{data['primary']}</h2>", unsafe_allow_html=True)
                
            elif data["type"] == "translate":
                st.markdown(f"<h2 style='text-align:center; color:#2563eb'>🇨🇿 {data['primary']}</h2>", unsafe_allow_html=True)
                
            elif data["type"] == "respond":
                st.markdown(f"<h2 style='text-align:center; color:#2563eb'>❓ {data['primary']}</h2>", unsafe_allow_html=True)
            
            elif data["type"] == "boss":
                st.markdown(f"<h3 style='text-align:center; color:#b91c1c'>😈 {data['primary']}</h3>", unsafe_allow_html=True)

            st.markdown("---")
            
            # --- FEEDBACK / NAHRÁVÁNÍ ---
            if st.session_state.feedback:
                parts = st.session_state.feedback.split('|')
                verdict = parts[0] if len(parts) > 0 else "Info"
                expl = parts[1] if len(parts) > 1 else ""
                corr = parts[2] if len(parts) > 2 else ""
                
                is_good = "Výborně" in verdict or "Dobře" in verdict or "Perfektní" in verdict
                css_class = "fb-success" if is_good else "fb-error"
                icon = "✅" if is_good else "⚠️"
                
                st.markdown(f"""
                <div class="feedback-box {css_class}">
                    <strong>{icon} {verdict}</strong><br>
                    {expl}
                </div>
                """, unsafe_allow_html=True)
                
                if corr and len(corr) > 2 and not is_good:
                    st.info(f"Správně: {corr}")
                
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
