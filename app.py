import streamlit as st
from groq import Groq
from streamlit_mic_recorder import mic_recorder
import io
from gtts import gTTS
import re
import random

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
    
    /* Sekundární tlačítka (šedá) */
    div[data-testid="column"] .stButton>button[kind="secondary"] {
        background-color: #f1f5f9; color: #334155; border: 1px solid #cbd5e1;
    }
    
    .task-card { background: linear-gradient(135deg, #ffffff 0%, #f0f9ff 100%); padding: 30px; border-radius: 20px; border: 1px solid #bae6fd; box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1); text-align: center; margin-bottom: 25px; }
    
    /* Feedback boxy */
    .feedback-container { padding: 20px; border-radius: 12px; margin-top: 15px; text-align: left; font-size: 1.05em; line-height: 1.6; }
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
    4: {"type": "respond", "name": "🗣️ Krok 4: Konverzace (Reakce)", "instruction": "Poslouchej otázku a odpověz na ni anglicky (podle pravdy nebo si vymýšlej).", "lang_rec": "en"},
    5: {"type": "boss", "name": "🏆 Krok 5: Boss Fight (Výzva)", "instruction": "Tohle je těžší věta. Přečti si ji česky a přelož do angličtiny.", "lang_rec": "en"}
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

def robust_text_cleaner(text):
    """Odstraní šipky, čísla, odrážky a jazykové prefixy z vygenerované věty."""
    if not text: return ""
    
    # Odstraní vše před dvojtečkou (např "Target: Hello")
    if ":" in text:
        text = text.split(":", 1)[1].strip()
    
    # NOVÉ: Odstraní jazykové prefixy i s mezerou "cz ", "en "
    text = re.sub(r'^(cz|en|cze|eng)\s+[:\->]*\s*', '', text, flags=re.IGNORECASE)
    
    # Odstraní šipky
    text = text.replace("->", "").replace(">", "").strip()
    
    # Odstraní čísla na začátku
    text = re.sub(r'^[\d\.\)\-\s]+', '', text)
    
    # Odstraní klíčová slova
    text = re.sub(r'^(Part|Task|Step|Listen|Question|Sentence|Target)\s*\d*\s*', '', text, flags=re.IGNORECASE)
    
    text = text.replace("*", "").replace("`", "").replace('"', "").replace("|||", "")
    return text.strip()

def generate_audio_google(text, lang="en"):
    """Generuje čisté audio."""
    try:
        tts = gTTS(text=text, lang=lang, slow=False)
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
    
    categories = ["zvířata", "emoce", "barvy", "rodina", "škola", "jídlo", "sport"]
    category = random.choice(categories)

    # Specifické instrukce pro různé typy
    specific_rules = ""
    if task_type == "respond":
        specific_rules = "VÝSTUP MUSÍ BÝT OTÁZKA KONČÍCÍ OTAZNÍKEM."
    elif task_type == "translate" or task_type == "boss":
        specific_rules = "PRVNÍ VĚTA MUSÍ BÝT ČESKY. DRUHÁ ANGLICKY."

    prompt = f"""
    Generuj KREATIVNÍ cvičení pro děti. Téma: {topic}. Typ: {task_type}.
    
    INSTRUKCE:
    1. Použij kategorii: {category}.
    2. Střídej osoby (I, You, We, They).
    3. Věty musí dávat smysl.
    4. {specific_rules}
    5. NEPOUŽÍVEJ ŽÁDNÉ PREFIXY jako "cz", "en".
    
    Formáty výstupu (přísně dodržuj oddělovač "|||"):
    LISTEN -> Anglická věta|||Český překlad
    IMITATE -> Anglická věta|||Český význam
    TRANSLATE -> Česká věta|||Anglický překlad
    RESPOND -> Anglická otázka?|||Open answer
    BOSS -> Česká složitější věta|||Anglický překlad
    """
    try:
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile", messages=[{"role": "system", "content": prompt}], temperature=0.9
        ).choices[0].message.content
        
        parts = resp.split('|||')
        
        # OKAMŽITÉ ČIŠTĚNÍ DAT
        primary = robust_text_cleaner(parts[0])
        secondary = robust_text_cleaner(parts[1]) if len(parts)>1 else ""
        
        return {"primary": primary, "secondary": secondary, "type": task_type}
    except: return {"primary": "Error", "secondary": "", "type": "error"}

def evaluate_student(student_text, task_data, task_type):
    lang_instruction = ""
    target_sentence = task_data['secondary'] # Default target (translation)
    primary_sentence = task_data['primary']
    
    # SPECIÁLNÍ LOGIKA PRO KONVERZACI (RESPOND)
    if task_type == "respond":
        prompt = f"""
        Jsi učitel angličtiny. Položil jsi dítěti otázku: "{primary_sentence}".
        Dítě odpovědělo: "{student_text}".
        
        ÚKOL: Zkontroluj, jestli odpověď DÁVÁ SMYSL v kontextu otázky a jestli je ANGLICKY.
        IGNORUJ, jestli je to gramaticky dokonalé. Hlavní je komunikace.
        NEPOROVNÁVEJ s žádnou "správnou odpovědí", protože odpověď je otevřená.
        
        Výstup:
        VERDIKT: (Výborně / Dobře / Zkus to znovu)
        VYSVĚTLENÍ: (Česky. Pokud je chyba, oprav ji jemně. Pokud je to OK, rozviň konverzaci.)
        CORRECT: (Pouze pokud byla velká chyba, napiš lepší verzi odpovědi)
        """
    
    # LOGIKA PRO OSTATNÍ TYPY
    else:
        if task_type == "listen":
            lang_instruction = "Dítě překládá do ČEŠTINY. Pokud význam sedí, je to SPRÁVNĚ."
            target_sentence = task_data['secondary']
        elif task_type == "translate" or task_type == "boss":
            lang_instruction = "Dítě překládá do ANGLIČTINY. Porovnej s: " + task_data['secondary']
            target_sentence = task_data['secondary']
        elif task_type == "imitate":
            lang_instruction = "Dítě opakuje anglickou větu. Porovnej s: " + task_data['primary']
            target_sentence = task_data['primary']

        prompt = f"""
        Jsi učitel. Úkol: {task_type}.
        Zadání: "{primary_sentence}".
        Správně má být (přibližně): "{target_sentence}".
        Dítě řeklo: "{student_text}".
        
        PRAVIDLA:
        1. {lang_instruction}
        2. Ignoruj interpunkci a velikost písmen.
        3. Nebuď puntičkář.
        4. NEVYMÝŠLEJ SI BÁCHORKY o psech a kočkách, pokud nejsou ve větě.
        
        Výstupní formát:
        VERDIKT: (Výborně / Dobře / Zkus to znovu)
        VYSVĚTLENÍ: (Stručně česky)
        CORRECT: (Správná verze, pokud byla chyba)
        """

    try:
        return client.chat.completions.create(
            model="llama-3.3-70b-versatile", messages=[{"role": "system", "content": prompt}]
        ).choices[0].message.content
    except: return "VERDIKT: Chyba\nVYSVĚTLENÍ: Zkus to znovu.\nCORRECT: -"

# --- 4. HLAVNÍ LOGIKA ---
def main():
    init_session()

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

    # HLAVNÍ OKNO
    current_lesson = SYLLABUS_DATA[st.session_state.current_lesson_index]

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

    elif st.session_state.step <= 5:
        step = st.session_state.step
        task_info = TASK_TYPES[step]
        
        st.caption(f"Lekce {current_lesson['id']} • Úkol {step} z 5")
        st.progress(step/5)

        if st.session_state.task_data is None:
            with st.spinner("Vymýšlím zadání..."):
                data = generate_task_data(current_lesson, step)
                st.session_state.task_data = data
                st.session_state.feedback = None
                
                # AUDIO JEN PRO LISTEN, IMITATE a RESPOND (otázka)
                if data["type"] in ["listen", "imitate", "respond"]:
                    audio_bytes = generate_audio_google(data["primary"], "en")
                    st.session_state.task_audio_bytes = audio_bytes
                else:
                    st.session_state.task_audio_bytes = None

        data = st.session_state.task_data

        st.markdown(f"""
        <div class="task-card">
            <h3>{task_info['name']}</h3>
            <p style="color:#555; font-style:italic;">{task_info['instruction']}</p>
        </div>
        """, unsafe_allow_html=True)
        
        col_c, col_content, col_d = st.columns([1, 4, 1])
        with col_content:
            
            # LISTEN - text skrytý
            if data["type"] == "listen":
                if st.session_state.task_audio_bytes:
                    st.audio(st.session_state.task_audio_bytes, format='audio/mp3')
                st.markdown("<h3 style='text-align:center'>❓ ???</h3>", unsafe_allow_html=True)
                
            # IMITATE a RESPOND - Angličtina
            elif data["type"] in ["imitate", "respond"]:
                st.markdown(f"<h2 style='text-align:center; color:#2563eb'>{data['primary']}</h2>", unsafe_allow_html=True)
                if st.session_state.task_audio_bytes:
                    st.audio(st.session_state.task_audio_bytes, format='audio/mp3')
            
            # TRANSLATE a BOSS - Čeština
            elif data["type"] in ["translate", "boss"]:
                # Tady zobrazujeme primary, který MUSÍ BÝT ČESKY (zajištěno v promptu)
                st.markdown(f"<h2 style='text-align:center; color:#2563eb'>🇨🇿 {data['primary']}</h2>", unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)
            if not st.session_state.feedback:
                cols = st.columns([1, 1])
                with cols[0]:
                    if st.button("🔄 Zkusit jinou větu"):
                        st.session_state.task_data = None
                        st.rerun()
            
            st.markdown("---")
            
            if st.session_state.feedback:
                text = st.session_state.feedback
                verdict = "Info"
                expl = text
                corr = ""
                
                if "VERDIKT:" in text:
                    verdict = text.split("VERDIKT:")[1].split("\n")[0].strip()
                if "VYSVĚTLENÍ:" in text:
                    expl = text.split("VYSVĚTLENÍ:")[1].split("CORRECT:")[0].strip()
                if "CORRECT:" in text:
                    corr_parts = text.split("CORRECT:")
                    if len(corr_parts) > 1:
                        corr = corr_parts[1].strip()

                is_good = "Výborně" in verdict or "Dobře" in verdict or "Perfektní" in verdict
                css_class = "fb-success" if is_good else "fb-error"
                icon = "✅" if is_good else "⚠️"
                
                st.markdown(f"""
                <div class="feedback-container {css_class}">
                    <strong>{icon} {verdict}</strong><br>
                    {expl}
                </div>
                """, unsafe_allow_html=True)
                
                # U konverzace nezobrazujeme "Správně", pokud to není nutné
                if corr and len(corr) > 2 and not is_good and data["type"] != "respond":
                    st.info(f"Správně: {corr}")
                
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    if st.button("🔄 Ještě jednu (trénink)"):
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
