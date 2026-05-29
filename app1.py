from flask import Flask, render_template, request, jsonify, send_from_directory, redirect, url_for, session
import os
from werkzeug.utils import secure_filename
import mysql.connector
from mysql.connector import Error
import docx
import pdfplumber
import speech_recognition as sr
import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import tempfile
from moviepy.editor import VideoFileClip
import hashlib

# 🌍 NEW IMPORTS
from deep_translator import GoogleTranslator
from langdetect import detect

# ====== Configurations ======
UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
ALLOWED_DOCS = {'pdf', 'doc', 'docx'}
ALLOWED_VIDEOS = {'mp4', 'mov', 'avi', 'mkv'}

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.secret_key = "your_secret_key"

# ====== Translator (Cleaned) ======
def detect_and_translate(text):
    try:
        if not text or not text.strip():
            return ""
        
        # Detect language
        lang = detect(text)
        if lang != "en":
            # deep-translator syntax
            translated = GoogleTranslator(source='auto', target='en').translate(text)
            return translated
        return text
    except Exception as e:
        print("Translation error:", e)
        return text

# ====== MySQL Connection ======
def get_db_connection():
    try:
        return mysql.connector.connect(
            host="localhost",
            user="root",
            password="tanzila@123",
            database="ai_resume_system"
        )
    except Error as e:
        print("Database connection error:", e)
        return None

# ====== Initialize Tables ======
def init_db():
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(100) UNIQUE NOT NULL,
                email VARCHAR(100) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS resumes (
                id INT AUTO_INCREMENT PRIMARY KEY,
                job VARCHAR(255),
                email VARCHAR(255),
                file VARCHAR(255),
                type VARCHAR(50),
                score FLOAT
            )
        """)
        conn.commit()
        cursor.close()
        conn.close()

init_db()

# ====== Skills ======
DEFAULT_SKILLS = [
    "python","java","c++","sql","machine learning","nlp",
    "deep learning","django","flask","html","css","javascript",
    "react","node","aws","azure","docker","kubernetes",
    "git","pandas","numpy","opencv","tensorflow","keras"
]

# ====== Helpers ======
def extract_text_from_resume(file_path):
    text = ""
    ext = file_path.rsplit('.', 1)[1].lower()
    try:
        if ext == "pdf":
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    t = page.extract_text()
                    if t: text += t + " "
        elif ext in ["docx", "doc"]:
            doc = docx.Document(file_path)
            for para in doc.paragraphs:
                text += para.text + " "
    except Exception as e:
        print("Text extraction error:", e)
    return text.strip()

def extract_skills(text):
    text = text.lower()
    return [skill for skill in DEFAULT_SKILLS if skill in text]

def extract_experience(text):
    matches = re.findall(r"(\d{1,2})\s*(years|yrs|year)", text.lower())
    return int(matches[0][0]) if matches else 0

def transcribe_video(video_path):
    try:
        clip = VideoFileClip(video_path)
        if clip.audio is None: return ""
        audio_path = tempfile.NamedTemporaryFile(delete=False, suffix=".wav").name
        clip.audio.write_audiofile(audio_path, verbose=False, logger=None)
        r = sr.Recognizer()
        with sr.AudioFile(audio_path) as source:
            audio = r.record(source)
        return r.recognize_google(audio)
    except:
        return ""

def calculate_similarity(resume_text, job_text):
    if not resume_text or not job_text: return 0.0
    vectorizer = TfidfVectorizer()
    tfidf = vectorizer.fit_transform([resume_text, job_text])
    return cosine_similarity(tfidf[0:1], tfidf[1:2])[0][0]

# ====== UPDATED SMART SCORE (MAX 10) ======
def calculate_score(similarity, skills, exp_resume, exp_job):
    # 1. Similarity Score (Weight: 50% -> Max 5 points)
    sim_points = similarity * 5
    
    # 2. Skills Score (Weight: 30% -> Max 3 points)
    # 0.5 points per skill, max 6 skills count
    skill_points = min(len(skills) * 0.5, 3)
    
    # 3. Experience Score (Weight: 20% -> Max 2 points)
    # Ratio relative to job requirement
    exp_ratio = exp_resume / (exp_job + 1)
    exp_points = min(exp_ratio * 2, 2)

    final_score = sim_points + skill_points + exp_points
    return round(min(final_score, 10), 1)

# ====== AUTH ======
@app.route('/')
def login():
    if session.get("logged_in"):
        return redirect(url_for('home'))
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login_user():
    username = request.form['username']
    password = hashlib.sha256(request.form['password'].encode()).hexdigest()
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE username=%s AND password=%s", (username, password))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    if user:
        session['logged_in'] = True
        session['username'] = user['username']
        return redirect(url_for('home'))
    return render_template('login.html', error="Invalid credentials")

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ====== HOME ======
@app.route('/home')
def home():
    if not session.get("logged_in"):
        return redirect(url_for('login'))
    return render_template('index.html', username=session.get('username'))

# ====== ANALYZE ======
@app.route('/analyze', methods=['POST'])
def analyze():
    if not session.get("logged_in"):
        return redirect(url_for('login'))

    job_desc = request.form.get('job_description', '')
    resume_file = request.files.get('resume')
    video_file = request.files.get('video')

    resume_text = ""
    transcript_text = ""

    if resume_file:
        path = os.path.join(UPLOAD_FOLDER, secure_filename(resume_file.filename))
        resume_file.save(path)
        resume_text = extract_text_from_resume(path)

    if video_file:
        v_path = os.path.join(UPLOAD_FOLDER, secure_filename(video_file.filename))
        video_file.save(v_path)
        transcript_text = transcribe_video(v_path)

    # Multi-language handling
    resume_en = detect_and_translate(resume_text)
    job_en = detect_and_translate(job_desc)
    transcript_en = detect_and_translate(transcript_text)

    combined = resume_en + " " + transcript_en
    similarity = calculate_similarity(combined, job_en)
    skills = extract_skills(combined)
    exp_resume = extract_experience(combined)
    exp_job = extract_experience(job_en)

    # Score calculation capped at 10
    score = calculate_score(similarity, skills, exp_resume, exp_job)

    return jsonify({
        "similarity": round(similarity * 100, 2),
        "skills": skills,
        "exp_resume": exp_resume,
        "exp_job": exp_job,
        "score": score,
        "resume_en": resume_en,
        "job_en": job_en,
        "transcript_en": transcript_en
    })

# ====== UPLOAD & SAVE ======
@app.route('/upload', methods=['POST'])
def upload_file():
    if not session.get("logged_in"):
        return redirect(url_for('login'))

    job_title = request.form.get('job')
    email = request.form.get('email')
    resume_file = request.files.get('resume')
    video_file = request.files.get('video')

    text = ""
    file_name = ""
    file_type = ""

    if resume_file:
        path = os.path.join(UPLOAD_FOLDER, secure_filename(resume_file.filename))
        resume_file.save(path)
        raw = extract_text_from_resume(path)
        text += detect_and_translate(raw)
        file_name = resume_file.filename
        file_type = "Document"

    if video_file:
        v_path = os.path.join(UPLOAD_FOLDER, secure_filename(video_file.filename))
        video_file.save(v_path)
        raw_v = transcribe_video(v_path)
        text += " " + detect_and_translate(raw_v)
        if not file_name: 
            file_name = video_file.filename
            file_type = "Video"

    skills = extract_skills(text)
    exp = extract_experience(text)

    # Simplified Score for DB capped at 10
    # (1 point per skill + 2 points per year of exp)
    db_score = min((len(skills) * 1) + (exp * 2), 10)

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO resumes (job, email, file, type, score)
        VALUES (%s, %s, %s, %s, %s)
    """, (job_title, email, file_name, file_type, db_score))
    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"message": "Upload successful", "score": db_score})

@app.route('/delete/<int:id>', methods=['DELETE'])
def delete_resume(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM resumes WHERE id=%s", (id,))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"message": "Deleted"})

@app.route('/dashboard')
def dashboard():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, job, email, file, type, score FROM resumes')
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify([
        {"id": r[0], "job": r[1], "email": r[2], "file": r[3], "type": r[4], "score": r[5]}
        for r in rows
    ])

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

if __name__ == "__main__":
    app.run(debug=True)