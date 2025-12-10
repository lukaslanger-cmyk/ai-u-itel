import streamlit as st
import json
import asyncio
import edge_tts
from groq import Groq
from streamlit_mic_recorder import mic_recorder

# --- KONFIGURACE ---
st.set_page_config(page_title="AI English Buddy", page_icon="🦁")

# CSS styly pro skrytí zbytečností a hezčí vzhled
st.markdown("""
<style>
    .stButton>button {
        width: 100%;
        border-radius: 10px;
        height: 3em;
        font-weight: bold;
    }
    div[data-testid="stMarkdownContainer"] p {
        font-size: 1.1em;
    }
</style>
""", unsafe_allow_html=True)

# Načtení klíče
try:
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
except:
    st.error("⚠️ Chybí API klíč! Nastav ho v Streamlit Secrets.")
    st.stop()

client = Groq(api_key=GROQ_API_KEY)

# --- FUNKCE: LOGIKA ---

def load_syllabus():
    try:
        with open('syllabus.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        st.error("Chybí soubor syllabus.json! Nahraj ho na GitHub.")
        return []

def get_lesson_content(lesson_data):
    # Prompt pro vytvoření lekce s opakováním
    review_instruction = ""
    if lesson_data.get('review_topic'):
        review_instruction = f"ZÁROVEŇ do vět zakomponuj opakování z minula: {lesson_data['review_topic']}."

    prompt = f"""
    Jsi zábavný učitel angličtiny pro české děti. 
    Téma: {lesson_data['topic']}. 
    Cíl: {lesson_data['goal']}. 
    {review_instruction}

    Tvůj úkol:
    1. Krátce a vtipně vysvětli novou látku (česky).
    2. Dej 3 příklady (Anglicky + Český překlad).
    3. Na konci dej dítěti KONKRÉTNÍ úkol, co má říct. Např: "A teď zkus říct anglicky: To je modrý pes."
    
    Nepoužívej složité formátování (žádné hvězdičky **).
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
    1. Zhodnotit, jestli to dává smysl.
    2. Pokud je to správně: Pochval ho ČESKY.
    3. Pokud je tam chyba: Vysvětli ji ČESKY a jednoduše.
    4. DŮLEŽITÉ: Na úplný konec napiš SPRÁVNOU anglickou větu do hranatých závorek, např: [It is a red car].
    
    Mluv na dítě jako kamarád. Nepoužívej složitá slova.
    """
    completion = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "system", "content": prompt}]
    )
    return completion.choices[0].message.content

# --- FUNKCE: AUDIO ---

async def generate_audio(text, filename, lang="cs"):
    # lang: 'cs' pro Vlastu, 'en' pro Anu
    voice = "cs-CZ-VlastaNeural"
    if lang == "en":
        voice = "en-US-AnaNeural"
    
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(filename)

# --- HLAVNÍ STRÁNKA ---
def main():
    st.title("🦁 AI English Buddy")
    
    syllabus = load_syllabus()
    if not syllabus:
        st.stop()

    # Výběr lekce v postranním panelu
    lesson_titles = [l['title'] for l in syllabus]
    selected_index = 0
    if 'selected_lesson_index' in st.session_state:
        selected_index = st.session_state.selected_lesson_index

    selected_lesson_name = st.sidebar.selectbox("Vyber lekci:", lesson_titles, index=selected_index)
    current_lesson = next(l for l in syllabus if l['title'] == selected_lesson_name)

    # Inicializace stavu lekce
    if 'current_lesson_id' not in st.session_state or st.session_state.current_lesson_id != current_lesson['id']:
        st.session_state.current_lesson_id = current_lesson['id']
        st.session_state.lesson_content = None
        st.session_state.feedback = None
        st.session_state.feedback_audio_cs = None
        st.session_state.feedback_audio_en = None

    # Tlačítko START
    if st.button("🚀 Začít lekci"):
        with st.spinner("Příprava učitele..."):
            content = get_lesson_content(current_lesson)
            st.session_state.lesson_content = content
            st.session_state.feedback = None # Reset feedbacku při nové lekci

    # 1. Zobrazení teorie a úkolu
    if st.session_state.lesson_content:
        st.info("👇 Přečti si zadání od učitele:")
        st.markdown(st.session_state.lesson_content)
        st.divider()

        # 2. Instrukce a Nahrávání
        st.subheader("🎤 Teď jsi na řadě ty!")
        
        # Žlutý rámeček s jasnou instrukcí
        st.warning("""
        **INSTRUKCE:**
        1. Klikni na **🔴 Nahrát odpověď**.
        2. Řekni větu anglicky (např. 'It is a red dog').
        3. Klikni na **⏹️ Stop**.
        4. Čekej na hodnocení.
        """)

        # Komponenta pro nahrávání (Česká tlačítka!)
        # key='recorder' zajistí, že se to nepřemazává
        audio_data = mic_recorder(
            start_prompt="🔴 Nahrát odpověď",
            stop_prompt="⏹️ Stop (Odeslat)",
            just_once=True,
            use_container_width=True,
            format="wav",
            key="recorder"
        )

        # 3. Zpracování nahrávky
        if audio_data:
            st.success("Odesílám učiteli...")
            
            # Uložení a přepis
            with open("input.wav", "wb") as f:
                f.write(audio_data['bytes'])
            
            with open("input.wav", "rb") as file:
                try:
                    # Přepis (STT)
                    transcription = client.audio.transcriptions.create(
                        file=(file.name, file.read()),
                        model="whisper-large-v3-turbo",
                        response_format="text"
                    )
                    st.write(f"🗣️ Slyšel jsem: **{transcription}**")

                    # Kontrola (AI Teacher)
                    raw_feedback = check_student_response(transcription, current_lesson['topic'])
                    
                    # Rozparsování feedbacku (hledáme [Větu v závorce])
                    import re
                    match = re.search(r'\[(.*?)\]', raw_feedback)
                    
                    feedback_text_cs = raw_feedback.replace('[', '').replace(']', '') # Vyčistíme text pro zobrazení
                    correct_sentence_en = match.group(1) if match else None
                    
                    # Pokud máme anglickou větu, odstraníme ji z českého textu, aby se nečetla dvakrát
                    if correct_sentence_en:
                        feedback_text_cs = feedback_text_cs.replace(correct_sentence_en, "")

                    # Uložení do session state
                    st.session_state.feedback = feedback_text_cs
                    st.session_state.correct_en = correct_sentence_en

                    # Generování audia (vytvoříme 2 soubory: český pokec a anglický vzor)
                    asyncio.run(generate_audio(feedback_text_cs, "feedback_cs.mp3", "cs"))
                    if correct_sentence_en:
                        asyncio.run(generate_audio(correct_sentence_en, "correct_en.mp3", "en"))

                except Exception as e:
                    st.error(f"Chyba: {e}")

    # 4. Zobrazení Feedbacku (Odděleně, aby nezmizel při překreslení)
    if st.session_state.get('feedback'):
        st.divider()
        st.markdown(f"### 👨‍🏫 Hodnocení:")
        st.write(st.session_state.feedback)
        
        # Přehrát české hodnocení
        st.audio("feedback_cs.mp3", format='audio/mp3', autoplay=True)

        # Pokud existuje oprava/vzor v angličtině
        if st.session_state.get('correct_en'):
            st.markdown(f"**👂 Poslechni si správnou výslovnost:**")
            st.success(f"🇬🇧 {st.session_state.correct_en}")
            st.audio("correct_en.mp3", format='audio/mp3')

if __name__ == "__main__":
    main()
