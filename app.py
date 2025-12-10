import streamlit as st
import json
import asyncio
import edge_tts
from groq import Groq
from streamlit_mic_recorder import mic_recorder
import io

# --- KONFIGURACE ---
st.set_page_config(page_title="AI English Buddy", page_icon="🦁", layout="centered")

# CSS styly pro hezčí vzhled (Barvy, tlačítka)
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
    .instruction-box {
        background-color: #f0f8ff;
        padding: 20px;
        border-radius: 10px;
        border-left: 5px solid #1e90ff;
        margin-bottom: 20px;
    }
    h1 { color: #2E86C1; }
    div[data-testid="stMarkdownContainer"] p { font-size: 1.15em; line-height: 1.6; }
</style>
""", unsafe_allow_html=True)

# Načtení klíče
try:
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
except:
    st.error("⚠️ Chybí API klíč! Nastav ho v Streamlit Secrets.")
    st.stop()

client = Groq(api_key=GROQ_API_KEY)

# --- FUNKCE: AUDIO V PAMĚTI (Bez ukládání na disk) ---
async def generate_audio_memory(text, lang="cs"):
    """Vygeneruje MP3 přímo do RAM paměti, aby nepadal Streamlit Cloud."""
    voice = "cs-CZ-VlastaNeural"
    if lang == "en":
        voice = "en-US-AnaNeural" # Ana mluví hezky anglicky
    
    # ČIŠTĚNÍ TEXTU PRO AUDIO (Oči vidí **, uši slyší čistě)
    clean_text = text.replace("**", "").replace("*", "").replace("🔴", "").replace("👇", "").replace("#", "")
    
    communicate = edge_tts.Communicate(clean_text, voice)
    mp3_fp = io.BytesIO() # Virtuální soubor v paměti
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            mp3_fp.write(chunk["data"])
    
    mp3_fp.seek(0)
    return mp3_fp

# --- FUNKCE: LOGIKA UČITELE ---
def load_syllabus():
    try:
        with open('syllabus.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        st.error("Chybí soubor syllabus.json!")
        return []

def get_lesson_content(lesson_data):
    review_instruction = ""
    if lesson_data.get('review_topic'):
        review_instruction = f"Zapoj i opakování: {lesson_data['review_topic']}."

    prompt = f"""
    Jsi nadšený učitel angličtiny.
    Téma: {lesson_data['topic']}. 
    Typ úkolu: {lesson_data.get('task_type', 'practice')}.
    {review_instruction}

    Tvůj úkol:
    1. Vysvětli látku česky, jednoduše, používej **tučné písmo** pro důležité věci.
    2. Dej 3 příklady (Anglicky - Česky).
    3. Na konci dej jasný úkol: "Řekni anglicky: [věta na překlad]".
    
    Používej emoji 🦁, 🇬🇧, ✨. Formátuj text přehledně.
    """
    
    completion = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "system", "content": prompt}],
        temperature=0.4
    )
    return completion.choices[0].message.content

def check_student_response(student_text, expected_topic):
    prompt = f"""
    Jsi laskavý učitel. Téma: {expected_topic}.
    Dítě řeklo: "{student_text}"

    Tvůj úkol:
    1. Pokud je to správně: Pochval ho ČESKY (nadšeně).
    2. Pokud je chyba: Vysvětli ji ČESKY a jednoduše.
    3. Na úplný konec napiš SPRÁVNOU anglickou větu do hranatých závorek, např: [It is a red car].
    
    Používej **tučné písmo** pro zvýraznění oprav.
    """
    completion = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "system", "content": prompt}]
    )
    return completion.choices[0].message.content

# --- HLAVNÍ STRÁNKA ---
def main():
    st.title("🦁 AI English Buddy")
    
    syllabus = load_syllabus()
    if not syllabus:
        st.stop()

    # Sidebar s výběrem lekce
    with st.sidebar:
        st.header("📚 Učebnice")
        lesson_titles = [f"{l['title']}" for l in syllabus]
        selected_lesson_name = st.selectbox("Kam půjdeme dnes?", lesson_titles)
    
    current_lesson = next(l for l in syllabus if l['title'] in selected_lesson_name)

    # Session State
    if 'current_lesson_id' not in st.session_state or st.session_state.current_lesson_id != current_lesson['id']:
        st.session_state.current_lesson_id = current_lesson['id']
        st.session_state.lesson_content = None
        st.session_state.feedback = None
        st.session_state.feedback_audio_cs = None
        st.session_state.feedback_audio_en = None

    # Tlačítko START
    if st.button("🚀 Začít lekci", type="primary"):
        with st.spinner("Paní učitelka připravuje tabuli..."):
            content = get_lesson_content(current_lesson)
            st.session_state.lesson_content = content
            st.session_state.feedback = None
            
            # Přednačtení audia k teorii (volitelné, zatím necháme jen text ať je to rychlé)

    # 1. Zobrazení teorie
    if st.session_state.lesson_content:
        st.markdown(st.session_state.lesson_content)
        st.markdown("---")

        # 2. Instrukce
        st.markdown('<div class="instruction-box"><h5>🎤 Tvůj úkol:</h5><ol><li>Klikni na <b>Nahrát odpověď</b></li><li>Řekni větu anglicky</li><li>Klikni na <b>Stop</b></li></ol></div>', unsafe_allow_html=True)

        # 3. Nahrávání
        col1, col2 = st.columns([1, 4]) # Zarovnání
        with col1:
             st.write(" ") # Spacer
        
        audio_data = mic_recorder(
            start_prompt="🔴 Nahrát odpověď",
            stop_prompt="⏹️ Stop (Odeslat)",
            just_once=True,
            use_container_width=True,
            format="wav",
            key="recorder"
        )

        # 4. Vyhodnocení
        if audio_data:
            with st.spinner("Poslouchám a opravuji..."):
                # Uložení do RAM pro whisper
                audio_bytes = audio_data['bytes']
                # Trik pro Whisper API (potřebuje 'name')
                audio_file = io.BytesIO(audio_bytes)
                audio_file.name = "audio.wav"
                
                try:
                    # A) Přepis
                    transcription = client.audio.transcriptions.create(
                        file=(audio_file.name, audio_file.read()),
                        model="whisper-large-v3-turbo",
                        response_format="text"
                    )
                    st.info(f"🗣️ Slyšel jsem: **{transcription}**")

                    # B) Kontrola
                    raw_feedback = check_student_response(transcription, current_lesson['topic'])
                    
                    # C) Analýza odpovědi (Hledáme [EN])
                    import re
                    match = re.search(r'\[(.*?)\]', raw_feedback)
                    
                    feedback_text_cs = raw_feedback.replace('[', '').replace(']', '') 
                    correct_sentence_en = match.group(1) if match else None
                    
                    if correct_sentence_en:
                        feedback_text_cs = feedback_text_cs.replace(correct_sentence_en, "")

                    st.session_state.feedback = feedback_text_cs
                    st.session_state.correct_en = correct_sentence_en
                    
                    # D) Generování audia do RAM (Asyncio run)
                    st.session_state.audio_cs = asyncio.run(generate_audio_memory(feedback_text_cs, "cs"))
                    if correct_sentence_en:
                        st.session_state.audio_en = asyncio.run(generate_audio_memory(correct_sentence_en, "en"))

                except Exception as e:
                    st.error(f"Chybička se vloudila: {e}")

    # 5. Zobrazení Feedbacku
    if st.session_state.get('feedback'):
        st.markdown("### 👩‍🏫 Hodnocení:")
        st.success(st.session_state.feedback) # Zelený rámeček, podporuje formátování
        
        if st.session_state.get('audio_cs'):
            st.audio(st.session_state.audio_cs, format='audio/mp3', autoplay=True)

        if st.session_state.get('correct_en'):
            st.markdown("---")
            st.markdown(f"**👂 Poslechni si správnou výslovnost:**")
            st.info(f"🇬🇧 **{st.session_state.correct_en}**")
            
            if st.session_state.get('audio_en'):
                st.audio(st.session_state.audio_en, format='audio/mp3')

if __name__ == "__main__":
    main()
