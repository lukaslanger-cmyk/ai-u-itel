import streamlit as st
from groq import Groq
from streamlit_mic_recorder import mic_recorder
import io
from gtts import gTTS
import re
import random
import json

# --- 1. KONFIGURACE ---
st.set_page_config(page_title="AI English Teacher Pro", page_icon="🎓", layout="wide")

st.markdown("""
<style>
    .main { background-color: #ffffff; }
    section[data-testid="stSidebar"] { background-color: #f7f9fc; border-right: 1px solid #e0e0e0; }
    .sidebar-header { font-size: 1.2em; font-weight: bold; color: #1e3a8a; margin-bottom: 10px; border-bottom: 2px solid #1e3a8a; padding-bottom: 5px; }
    .stButton>button { width: 100%; border-radius: 8px; height: 3em; font-weight: 600; border: none; background-color: #2563eb; color: white; transition: all 0.2s; }
    .stButton>button:hover { background-color: #1d4ed8; transform: translateY(-2px); box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
    div[data-testid="column"] .stButton>button[kind="secondary"] { background-color: #f1f5f9; color: #334155; border: 1px solid #cbd5e1; }
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

# --- 2. SYLABUS ---
SYLLABUS_DATA = [
  {"id": 1, "title": "1. Být či nebýt? (TO BE)", "topic": "Verb TO BE (I am, You are, We are...)", "goal": "Sloveso BÝT."},
  {"id": 2, "title": "2. Kde co leží? (Předložky)", "topic": "Prepositions (in, on, under)", "goal": "Předložky."},
  {"id": 3, "title": "3. Mít či nemít? (HAVE GOT)", "topic": "Verb HAVE GOT", "goal": "Mít."},
  {"id": 4, "title": "4. Superman (CAN / CAN'T)", "topic": "Modal verb CAN", "goal": "Umět."},
  {"id": 5, "title": "5. Moje rodina", "topic": "Family members", "goal": "Rodina."}
]

TASK_TYPES = {
    1: {"type": "listen", "name": "👂 Krok 1: Porozumění (Poslech)", "instruction": "Poslouchej anglickou větu a řekni česky, co znamená.", "lang_rec": "cs"},
    2: {"type": "imitate", "name": "🦜 Krok 2: Výslovnost (Papoušek)", "instruction": "Poslouchej a zopakuj to anglicky.", "lang_rec": "en"},
    3: {"type": "translate", "name": "✍️ Krok 3: Překlad (Dril)", "instruction": "Přečti si českou větu a řekni ji anglicky.", "lang_rec": "en"},
    4: {"type": "respond", "name": "🗣️ Krok 4: Konverzace (Reakce)", "instruction": "Poslouchej otázku a odpověz na ni anglicky.", "lang_rec": "en"},
    5: {"type": "boss", "name": "🏆 Krok 5: Boss Fight (Výzva)", "instruction": "Přelož tuto těžší větu do angličtiny.", "lang_rec": "en"}
}

# --- 3. FUNKCE ---

def init_session():
    defaults = {
        'step': 0,
        'current_lesson_index': 0,
        'theory_content': None,
        'task_data': None,
        'feedback': None,
        'task_audio_bytes': None,
        'last_transcript': None
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
    st.session_state.last_transcript = None

def generate_audio_google(text, lang="en"):
    try:
        clean_text = re.sub(r'[^\w\s,.?!]', '', text)
        tts = gTTS(text=clean_text, lang=lang, slow=False)
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        return fp.getvalue()
    except Exception as e:
        return None

def get_theory(lesson_data):
    prompt = f"""
    Jsi učitel angličtiny pro děti. Téma: {lesson_data['topic']}.
    Vysvětli látku česky, stručně. Uveď 3 příklady.
    """
    try:
        return client.chat.completions.create(
            model="llama-3.3-70b-versatile", messages=[{"role": "system", "content": prompt}]
        ).choices[0].message.content
    except: return "Chyba teorie."

def generate_task_data(lesson_data, step_number):
    task_type = TASK_TYPES[step_number]["type"]
    topic = lesson_data['topic']
    category = random.choice(["zvířata", "barvy", "rodina", "škola", "jídlo"])

    prompt = f"""
    Generuj cvičení pro děti. Téma: {topic}. Typ: {task_type}. Kategorie: {category}.
    
    Vrať POUZE validní JSON:
    {{ "english_text": "Anglická věta", "czech_text": "Český překlad" }}

    PRAVIDLA:
    1. Typ LISTEN, IMITATE, RESPOND: 'english_text' je hlavní.
    2. Typ TRANSLATE, BOSS: 'czech_text' je hlavní.
    3. Typ RESPOND: 'english_text' musí být OTÁZKA.
    4. Používej jednoduchá slova.
    """
    try:
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile", 
            messages=[{"role": "system", "content": prompt}],
            response_format={"type": "json_object"}
        ).choices[0].message.content
        data = json.loads(resp)
        
        if task_type in ["listen", "imitate", "respond"]:
            return {"primary": data.get("english_text", ""), "secondary": data.get("czech_text", ""), "type": task_type}
        else:
            return {"primary": data.get("czech_text", ""), "secondary": data.get("english_text", ""), "type": task_type}
    except Exception as e: 
        return {"primary": "Error", "secondary": str(e), "type": "error"}

def evaluate_student(student_text, task_data, task_type):
    if not student_text or len(student_text.strip()) < 2:
        return "VERDIKT: Zkus to znovu\nVYSVĚTLENÍ: Nic jsem neslyšel.\nCORRECT: -"

    # DYNAMICKÁ INSTRUKCE PRO AI
    system_prompt = "Jsi kamarádský učitel. Mluvíš s dítětem. NIKDY nepoužívej 3. osobu (on/ona/dítě). Vždy používej TY (tykání). Hodnoť laskavě."
    
    if task_type == "listen":
        user_task = f"Tvůj úkol: Poslechnout si anglickou větu '{task_data['primary']}' a říct ČESKY, co znamená."
        evaluation_logic = "Pokud uživatel mluví ČESKY a význam sedí, je to SPRÁVNĚ. Pokud mluví anglicky, upozorni ho, ať to přeloží."
    elif task_type == "respond":
        user_task = f"Tvůj úkol: Odpovědět anglicky na otázku '{task_data['primary']}'."
        evaluation_logic = "Odpověď je volná. Pokud dává smysl a je anglicky, je to SPRÁVNĚ. Neřeš drobné chyby."
    else:
        target = task_data['secondary']
        user_task = f"Tvůj úkol: Přeložit/říct anglicky větu. Cíl je: '{target}'."
        evaluation_logic = "Porovnej význam. Ignoruj interpunkci. Buď milý."

    prompt = f"""
    {user_task}
    Uživatel řekl: "{student_text}"
    
    {evaluation_logic}
    
    VÝSTUPNÍ FORMÁT (přesně):
    VERDIKT: (Výborně / Dobře / Zkus to znovu)
    VYSVĚTLENÍ: (Tvoje reakce na uživatele - česky)
    CORRECT: (Správná verze, pokud byla chyba, jinak prázdné)
    """

    try:
        return client.chat.completions.create(
            model="llama-3.3-70b-versatile", 
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ]
        ).choices[0].message.content
    except: return "VERDIKT: Chyba\nVYSVĚTLENÍ: Zkus to znovu.\nCORRECT: -"

# --- 4. HLAVNÍ LOGIKA ---
def main():
    init_session()

    with st.sidebar:
        st.markdown("""<div class="sidebar-header">🦁 Můj profil</div>""", unsafe_allow_html=True)
        st.progress(st.session_state.current_lesson_index / len(SYLLABUS_DATA), text="Postup")
        st.markdown("---")
        titles = [l['title'] for l in SYLLABUS_DATA]
        selected_title = st.radio("Lekce:", titles, index=st.session_state.current_lesson_index, label_visibility="collapsed")
        new_index = titles.index(selected_title)
        if new_index != st.session_state.current_lesson_index:
            st.session_state.current_lesson_index = new_index
            reset_lesson()
            st.rerun()
        if st.button("🔄 Restartovat"):
            reset_lesson()
            st.rerun()

    current_lesson = SYLLABUS_DATA[st.session_state.current_lesson_index]

    if st.session_state.step == 0:
        st.markdown(f"# 🎓 {current_lesson['title']}")
        if not st.session_state.theory_content:
            with st.spinner("Načítám učebnici..."):
                st.session_state.theory_content = get_theory(current_lesson)
        
        if "ERROR" in str(st.session_state.theory_content):
            st.error("Chyba načítání.")
            if st.button("Zkusit znovu"): 
                st.session_state.theory_content = None
                st.rerun()
        else:
            st.info(st.session_state.theory_content)
            if st.button("Jdeme trénovat! 🚀", type="primary"):
                st.session_state.step = 1
                st.rerun()

    elif st.session_state.step <= 5:
        step = st.session_state.step
        task_info = TASK_TYPES[step]
        st.caption(f"Úkol {step} z 5")
        st.progress(step/5)

        if st.session_state.task_data is None:
            with st.spinner("Generuji zadání..."):
                data = generate_task_data(current_lesson, step)
                if data['type'] == 'error':
                    st.error("Chyba spojení.")
                    st.stop()
                st.session_state.task_data = data
                st.session_state.feedback = None
                if data["type"] in ["listen", "imitate", "respond"]:
                    st.session_state.task_audio_bytes = generate_audio_google(data["primary"], "en")
                else:
                    st.session_state.task_audio_bytes = None

        data = st.session_state.task_data

        st.markdown(f"""
        <div class="task-card">
            <h3>{task_info['name']}</h3>
            <p>{task_info['instruction']}</p>
        </div>
        """, unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns([1, 4, 1])
        with col2:
            if data["type"] == "listen":
                if st.session_state.task_audio_bytes: st.audio(st.session_state.task_audio_bytes, format='audio/mp3')
                if st.button("🔊 Zvuk nejde? Zobrazit text"): st.info(f"Věta je: **{data['primary']}**")
                st.markdown("<h3 style='text-align:center'>❓ ???</h3>", unsafe_allow_html=True)

            elif data["type"] in ["imitate", "respond"]:
                st.markdown(f"<h2 style='text-align:center; color:#2563eb'>{data['primary']}</h2>", unsafe_allow_html=True)
                if st.session_state.task_audio_bytes: st.audio(st.session_state.task_audio_bytes, format='audio/mp3')
            
            elif data["type"] in ["translate", "boss"]:
                st.markdown(f"<h2 style='text-align:center; color:#2563eb'>🇨🇿 {data['primary']}</h2>", unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)
            if not st.session_state.feedback:
                if st.button("🔄 Jinou větu"):
                    st.session_state.task_data = None
                    st.rerun()
                if data["type"] == "respond" and st.button("🆘 Nápověda"): st.info(f"Česky: {data['secondary']}")
            
            if st.session_state.feedback:
                parts = st.session_state.feedback.split('|')
                verdict = parts[0] if len(parts) > 0 else "Info"
                expl = parts[1] if len(parts) > 1 else str(st.session_state.feedback)
                corr = parts[2] if len(parts) > 2 else ""
                
                is_good = "Výborně" in verdict or "Dobře" in verdict
                css = "fb-success" if is_good else "fb-error"
                
                st.markdown(f"""<div class="feedback-box {css}"><strong>{verdict}</strong><br>{expl}</div>""", unsafe_allow_html=True)
                
                if st.session_state.last_transcript:
                    st.caption(f"Slyšel jsem: *{st.session_state.last_transcript}*")

                if corr and len(corr) > 2 and not is_good:
                    st.info(f"Správně: {corr}")
                
                col_a, col_b = st.columns(2)
                with col_a:
                    if st.button("🔄 Ještě jednu"):
                        st.session_state.task_data = None
                        st.rerun()
                with col_b:
                    if st.button("Další úkol ➡️", type="primary"):
                        st.session_state.step += 1
                        st.session_state.task_data = None
                        st.rerun()
            else:
                lang = task_info["lang_rec"]
                audio_data = mic_recorder(start_prompt=f"🎙️ Nahrát ({lang.upper()})", stop_prompt="⏹️ Odeslat", key=f"mic_{step}")
                
                if audio_data:
                    with st.spinner("Poslouchám..."):
                        bio = io.BytesIO(audio_data['bytes'])
                        bio.name = "audio.wav"
                        try:
                            txt = client.audio.transcriptions.create(
                                file=(bio.name, bio.read()), model="whisper-large-v3-turbo", language=lang, response_format="text"
                            ).strip()
                            st.session_state.last_transcript = txt
                            st.session_state.feedback = evaluate_student(txt, data, data["type"])
                            st.rerun()
                        except Exception as e: st.error(str(e))

    else:
        st.balloons()
        st.success("HOTOVO!")
        if st.button("Zpět"):
            reset_lesson()
            st.rerun()

if __name__ == "__main__":
    main()
