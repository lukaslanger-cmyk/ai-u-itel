import streamlit as st
import json
import asyncio
import edge_tts
from groq import Groq
import os
from st_audiorec import st_audiorec # Knihovna pro webové nahrávání

# --- KONFIGURACE ---
st.set_page_config(page_title="AI English Teacher", page_icon="🦁")

# Tajné heslo získáme ze systému Streamlit (vysvětlím níže)
GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
client = Groq(api_key=GROQ_API_KEY)

# --- FUNKCE ---
def load_syllabus():
    with open('syllabus.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def get_theory(lesson_data):
    comparison_text = ""
    if lesson_data['context_compare']:
        comparison_text = f"Srovnej s: {lesson_data['context_compare']}."

    prompt = f"""
    Jsi učitel pro děti. Téma: {lesson_data['topic']}. Cíl: {lesson_data['goal']}. {comparison_text}
    Vysvětli látku česky, jednoduše, s emoji. Dej 3 příklady (EN/CZ).
    """
    completion = client.chat.completions.create(
        model="llama3-70b-8192",
        messages=[{"role": "system", "content": prompt}],
        temperature=0.3
    )
    return completion.choices[0].message.content

def check_answer(student_text, expected_topic):
    prompt = f"""
    Téma: {expected_topic}. Student řekl: "{student_text}".
    Je to gramaticky správně? Pokud ne, oprav ho česky. Pokud ano, pochval anglicky.
    """
    completion = client.chat.completions.create(
        model="llama3-70b-8192",
        messages=[{"role": "system", "content": prompt}]
    )
    return completion.choices[0].message.content

async def text_to_audio_file(text, filename):
    communicate = edge_tts.Communicate(text, "cs-CZ-VlastaNeural")
    if "Good" in text or "Nice" in text or "Hello" in text:
         communicate = edge_tts.Communicate(text, "en-US-AnaNeural")
    await communicate.save(filename)

# --- HLAVNÍ STRÁNKA ---
def main():
    st.title("🦁 AI Učitel Angličtiny")
    
    syllabus = load_syllabus()
    lesson_titles = [l['title'] for l in syllabus]
    selected = st.sidebar.selectbox("Lekce:", lesson_titles)
    current_lesson = next(l for l in syllabus if l['title'] == selected)

    # Inicializace session state
    if 'current_lesson_id' not in st.session_state or st.session_state.current_lesson_id != current_lesson['id']:
        st.session_state.current_lesson_id = current_lesson['id']
        st.session_state.theory = None

    if st.button("📖 Otevřít učebnici"):
        st.session_state.theory = get_theory(current_lesson)

    if st.session_state.theory:
        st.markdown(st.session_state.theory)
        st.divider()
        st.subheader("🎙️ Teď ty!")
        st.info("Nahraj anglickou větu k tomuto tématu:")

        # WEBOVÉ NAHRÁVÁNÍ
        wav_audio_data = st_audiorec()

        if wav_audio_data is not None:
            # 1. Uložíme zvuk
            with open("input.wav", "wb") as f:
                f.write(wav_audio_data)
            
            # 2. Pošleme ho AI na přepis (Whisper přes Groq - je to free a ultra rychlé)
            with open("input.wav", "rb") as file:
                try:
                    transcription = client.audio.transcriptions.create(
                        file=(file.name, file.read()),
                        model="whisper-large-v3-turbo",
                        response_format="text"
                    )
                    st.write(f"🗣️ Slyšel jsem: **{transcription}**")

                    # 3. Kontrola
                    feedback = check_answer(transcription, current_lesson['topic'])
                    st.success(feedback)

                    # 4. Přečtení feedbacku
                    asyncio.run(text_to_audio_file(feedback, "response.mp3"))
                    st.audio("response.mp3", autoplay=True)
                    
                except Exception as e:
                    st.error(f"Chyba při zpracování: {e}")

if __name__ == "__main__":
    main()