# app.py
import os
import logging
import requests
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import datetime
from sqlalchemy.sql import func
from logging.handlers import RotatingFileHandler
from datetime import date, timedelta
import random
import json
import re

app = Flask(__name__)
app.secret_key = "7373"
# Configure PostgreSQL database
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://yechiel@localhost/languagex'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Cloud API configuration
CLOUD_API_URL = os.getenv('CLOUD_API_URL', 'https://51ce-103-119-147-234.ngrok-free.app')
# Grammar API configuration
CLOUD_API_Grammar_URL = os.getenv('CLOUD_API_Grammar_URL', 'https://51ce-103-119-147-234.ngrok-free.app')

# Add these configurations for file uploads
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static/uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB max upload size

# Make sure upload directory exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Define User model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    name = db.Column(db.String(100))
    language = db.Column(db.String(50))
    level = db.Column(db.String(10))
    study_time = db.Column(db.Integer, default=0)
    streak = db.Column(db.Integer, default=0)
    lessons_completed = db.Column(db.Integer, default=0)
    average_score = db.Column(db.Float, default=0.0)
    last_active_date = db.Column(db.Date, nullable=True)
    total_attempts = db.Column(db.Integer, default=0)
    correct_attempts = db.Column(db.Integer, default=0)
    placement_test_for_user = db.Column(db.Integer, nullable=True)  # User ID if used for placement test
    profile_picture = db.Column(db.String(255), nullable=True)  # Path or URL to profile picture
    is_deleted = db.Column(db.Boolean, default=False)  # New column to mark deleted accounts
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class SelectionQuestion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question_text = db.Column(db.Text, nullable=False)  # Note: field is question_text, not question
    sentences = db.Column(db.Text, nullable=False)
    correct_sentence = db.Column(db.Text, nullable=False)
    level = db.Column(db.String(10), nullable=False)
    generated_at = db.Column(db.DateTime, default=func.now())
    deleted_at = db.Column(db.DateTime, nullable=True)
    is_seen = db.Column(db.Boolean, default=False)
    for_user = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user_answer = db.Column(db.Text, nullable=True)
    is_correct = db.Column(db.Boolean, nullable=True)
    user_feedback = db.Column(db.Text, nullable=True)
    ground_truth_id = db.Column(db.Integer, db.ForeignKey('ground_truth.id'), nullable=True)

    user = db.relationship('User', backref=db.backref('selection_questions', lazy=True))
    ground_truth = db.relationship('GroundTruth', backref=db.backref('selection_questions', lazy=True))


class LabelingQuestion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question_text = db.Column(db.Text, nullable=False)
    instruction = db.Column(db.Text, nullable=False)
    correct_labels = db.Column(db.Text, nullable=False)  # Store as JSON string
    level = db.Column(db.String(10), nullable=False)
    generated_at = db.Column(db.DateTime, default=func.now())
    deleted_at = db.Column(db.DateTime, nullable=True)
    is_seen = db.Column(db.Boolean, default=False)
    for_user = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user_answer = db.Column(db.Text, nullable=True)
    is_correct = db.Column(db.Boolean, nullable=True)
    user_feedback = db.Column(db.Text, nullable=True)
    ground_truth_id = db.Column(db.Integer, db.ForeignKey('ground_truth.id'), nullable=True)

    user = db.relationship('User', backref=db.backref('labeling_questions', lazy=True))
    ground_truth = db.relationship('GroundTruth', backref=db.backref('labeling_questions', lazy=True))


# Define UserPerformance model
class UserPerformance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    concept = db.Column(db.String(100), nullable=False)
    success_rate = db.Column(db.Float, default=0.0)
    error_rate = db.Column(db.Float, default=0.0)
    timestamp = db.Column(db.DateTime, default=func.now())
    total_attempts = db.Column(db.Integer, default=0)
    correct_attempts = db.Column(db.Integer, default=0)

    user = db.relationship('User', backref=db.backref('performance', lazy=True))

# GroundTruth model
class GroundTruth(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    word = db.Column(db.String(100), nullable=False)
    pos = db.Column(db.String(50), nullable=False)
    sentence = db.Column(db.Text, nullable=False)
    level = db.Column(db.String(10), nullable=False)
    generated_at = db.Column(db.DateTime, default=func.now())
    deleted_at = db.Column(db.DateTime, nullable=True)
    is_seen = db.Column(db.Boolean, default=False)
    for_user = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user_answer = db.Column(db.Text, nullable=True)
    is_correct = db.Column(db.Boolean, nullable=True)
    
    user = db.relationship('User', backref=db.backref('ground_truths', lazy=True))

# FillInTheBlank model
class FillInTheBlank(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.Text, nullable=False)
    answer = db.Column(db.String(100), nullable=False)
    level = db.Column(db.String(10), nullable=False)
    generated_at = db.Column(db.DateTime, default=func.now())
    deleted_at = db.Column(db.DateTime, nullable=True)
    is_seen = db.Column(db.Boolean, default=False)
    for_user = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user_answer = db.Column(db.Text, nullable=True)
    is_correct = db.Column(db.Boolean, nullable=True)
    user_feedback = db.Column(db.Text, nullable=True)
    ground_truth_id = db.Column(db.Integer, db.ForeignKey('ground_truth.id'), nullable=True)

    user = db.relationship('User', backref=db.backref('fill_blanks', lazy=True))
    ground_truth = db.relationship('GroundTruth', backref=db.backref('fill_blanks', lazy=True))

# ArrangeTheWord model
class ArrangeTheWord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.Text, nullable=False)
    correct_arrangement = db.Column(db.Text, nullable=False)
    level = db.Column(db.String(10), nullable=False)
    generated_at = db.Column(db.DateTime, default=func.now())
    deleted_at = db.Column(db.DateTime, nullable=True)
    is_seen = db.Column(db.Boolean, default=False)
    for_user = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user_answer = db.Column(db.Text, nullable=True)
    is_correct = db.Column(db.Boolean, nullable=True)
    user_feedback = db.Column(db.Text, nullable=True)
    ground_truth_id = db.Column(db.Integer, db.ForeignKey('ground_truth.id'), nullable=True)

    user = db.relationship('User', backref=db.backref('arrange_words', lazy=True))
    ground_truth = db.relationship('GroundTruth', backref=db.backref('arrange_words', lazy=True))

# MultipleChoice model
class MultipleChoice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.Text, nullable=False)
    choices = db.Column(db.Text, nullable=False)
    correct_answer = db.Column(db.String(100), nullable=False)
    level = db.Column(db.String(10), nullable=False)
    generated_at = db.Column(db.DateTime, default=func.now())
    deleted_at = db.Column(db.DateTime, nullable=True)
    is_seen = db.Column(db.Boolean, default=False)
    for_user = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user_answer = db.Column(db.Text, nullable=True)
    is_correct = db.Column(db.Boolean, nullable=True)
    user_feedback = db.Column(db.Text, nullable=True)
    ground_truth_id = db.Column(db.Integer, db.ForeignKey('ground_truth.id'), nullable=True)

    user = db.relationship('User', backref=db.backref('multiple_choices', lazy=True))
    ground_truth = db.relationship('GroundTruth', backref=db.backref('multiple_choices', lazy=True))

# PlacementTestAttempt model
class PlacementTestAttempt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    started_at = db.Column(db.DateTime, default=func.now())
    completed_at = db.Column(db.DateTime, nullable=True)
    score = db.Column(db.Float, nullable=True)
    estimated_level = db.Column(db.String(10), nullable=True)
    user = db.relationship('User', backref=db.backref('placement_attempts', lazy=True))

class MakeASentence(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.Text, nullable=False)  # The question text
    words = db.Column(db.String(255), nullable=False)  # The 1-2 words used for the question
    level = db.Column(db.String(10), nullable=False)
    generated_at = db.Column(db.DateTime, default=func.now())
    deleted_at = db.Column(db.DateTime, nullable=True)
    is_seen = db.Column(db.Boolean, default=False)
    for_user = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user_answer = db.Column(db.Text, nullable=True)
    score = db.Column(db.Float, nullable=True)  # Ganti dari is_correct ke score (float/angka)

    user = db.relationship('User', backref=db.backref('make_a_sentence_questions', lazy=True))

class FinishTheSentence(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.Text, nullable=False)  # The sentence to be finished
    words = db.Column(db.String(255), nullable=False)
    level = db.Column(db.String(10), nullable=False)
    generated_at = db.Column(db.DateTime, default=func.now())
    deleted_at = db.Column(db.DateTime, nullable=True)
    is_seen = db.Column(db.Boolean, default=False)
    for_user = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user_answer = db.Column(db.Text, nullable=True)
    score = db.Column(db.Float, nullable=True)

    user = db.relationship('User', backref=db.backref('finish_sentences', lazy=True))

# Logging setup
if not os.path.exists('logs'):
    os.makedirs('logs')
handler = RotatingFileHandler('logs/app1.log', maxBytes=10000, backupCount=5)
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
app.logger.addHandler(handler)
app.logger.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(console_formatter)
app.logger.addHandler(console_handler)
app.logger.info("Flask app is starting up")

# Simple CEFR level validation
def is_sentence_appropriate_for_level(sentence, level):
    """Basic check for sentence validity without strict word count limitations."""
    if not sentence or not isinstance(sentence, str):
        app.logger.debug("Sentence rejected: empty or invalid")
        return False
        
    # The sentence exists and is a string - accept it
    # We're removing the word count restrictions since the API already validates content
    return True

def format_study_time(minutes):
    hours = int(minutes) // 60
    mins = int(minutes) % 60
    return f"{hours}h {mins}m" if hours else f"{mins}m"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'GET':
        return render_template('signup.html')
    
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        name = request.form.get('name', '')
        language = request.form.get('language', 'English')
        level = request.form.get('level', 'A1')
        
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            return render_template('signup.html', error="Email already registered")
        
        new_user = User(email=email, name=name, language=language, level=level)
        new_user.set_password(password)
        
        db.session.add(new_user)
        db.session.commit()
        
        # Redirect to login with a success message
        return redirect(url_for('login', signup='success'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        
        if user and check_password_hash(user.password_hash, password):
            session['logged_in'] = True
            session['user_id'] = user.id
            session['user_email'] = user.email
            session['user_name'] = user.name
            session['user_level'] = user.level
            
            # Add this line to specifically mark admin accounts
            if user.email == 'admin@yahoo.com':
                session['is_admin'] = True
            
            # Update last active date
            user.last_active_date = date.today()
            db.session.commit()
            
            return redirect(url_for('generate'))
        else:
            return render_template('login.html', error='Invalid email or password')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    # Clear the session
    session.clear()
    return redirect(url_for('login'))

@app.route('/profile')
def profile():
    # Debug log to help troubleshoot
    app.logger.info(f"Session data on profile access: {session}")
    
    if not session.get('logged_in'):
        app.logger.info("User not logged in, redirecting to login")
        return redirect(url_for('login'))
    
    user_id = session.get('user_id')
    app.logger.info(f"Profile access for user_id: {user_id}")
    
    user = User.query.get(user_id)
    
    if not user:
        app.logger.error(f"User {user_id} not found in database")
        return redirect(url_for('logout'))
    
    # Make sure admin flag is set for admin users
    if user.email == 'admin@yahoo.com':
        session['is_admin'] = True
        app.logger.info("Admin user confirmed, setting is_admin flag")
    
    # Get user performance data
    user_performance = UserPerformance.query.filter_by(user_id=user_id).all()
    performance_data = []
    
    for perf in user_performance:
        performance_data.append({
            'concept': perf.concept,
            'success_rate': perf.success_rate,
            'error_rate': perf.error_rate,
            'total_attempts': perf.total_attempts
        })
    
    # For admins, you might want to provide additional data
    admin_data = None
    if session.get('is_admin'):
        admin_data = {
            'user_count': User.query.filter(User.email != 'admin@yahoo.com').count(),
            'active_users': User.query.filter(User.last_active_date >= (date.today() - timedelta(days=7))).count()
        }
    
    return render_template('profile.html', user=user, performance_data=performance_data, admin_data=admin_data)


@app.route('/update_profile', methods=['POST'])
def update_profile():
    if not session.get('logged_in'):
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    
    user_id = session.get('user_id')
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'success': False, 'error': 'User not found'}), 404
    
    # Update name if provided
    new_name = request.form.get('name')
    if new_name and new_name.strip():
        user.name = new_name.strip()
        session['user_name'] = user.name
    
    # Update level if provided
    new_level = request.form.get('level')
    if new_level and new_level in ['A1', 'A2', 'B1', 'B2', 'C1', 'C2']:
        user.level = new_level
    
    # Handle profile picture upload
    if 'profile_picture' in request.files:
        file = request.files['profile_picture']
        if file and file.filename and allowed_file(file.filename):
            # Create unique filename to avoid overwrites
            filename = secure_filename(file.filename)
            unique_filename = f"{user_id}_{int(datetime.datetime.now().timestamp())}_{filename}"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            
            try:
                file.save(file_path)
                # Save the relative path to the database
                user.profile_picture = f"/static/uploads/{unique_filename}"
            except Exception as e:
                app.logger.error(f"Error saving profile picture: {str(e)}")
                return jsonify({'success': False, 'error': 'Failed to save image'}), 500
    
    # Save changes
    try:
        db.session.commit()
        return jsonify({
            'success': True, 
            'message': 'Profile updated successfully',
            'name': user.name,
            'level': user.level,
            'profile_picture': user.profile_picture
        })
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error updating profile: {str(e)}")
        return jsonify({'success': False, 'error': 'Database error'}), 500
    
    
@app.route('/generate', methods=['GET', 'POST'])
def generate():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
        
    if request.method == 'GET':
        return render_template('generate.html')
    
    elif request.method == 'POST':
        try:
            # Handle both JSON and form data
            if request.is_json:
                data = request.get_json()
                question_types = data.get("question_types") or []
                level = data.get('level')
                num_sentences_str = str(data.get('num_sentences', 2))
                topic = data.get('topic', '')
                user_id = data.get('user_id') or session.get('user_id')
            else:
                level = request.form.get('level')
                num_sentences_str = request.form.get('num_sentences', '2')
                topic = request.form.get('topic', '')
                user_id = session.get('user_id')
                question_types = request.form.getlist("question_types")

            app.logger.info(f"Received generate request: level={level}, topic={topic}, num_sentences={num_sentences_str}, user_id={user_id}")

            # Validate inputs
            if not level or level not in ["A1", "A2", "B1", "B2", "C1", "C2"]:
                app.logger.error(f"Invalid level: {level}")
                return jsonify({"error": "Invalid or missing level", "success": False}), 400
            
            try:
                num_sentences = int(num_sentences_str)
                if num_sentences < 1 or num_sentences > 10:
                    raise ValueError
            except ValueError:
                app.logger.error(f"Invalid num_sentences: {num_sentences_str}")
                return jsonify({"error": "Number of sentences must be an integer between 1 and 10", "success": False}), 400

            if user_id is None:
                app.logger.error("No user_id in session")
                return jsonify({"error": "User not authenticated", "success": False}), 401

            # Call cloud API
            headers = {
                "Content-Type": "application/json"
            }
            payload = {
                "level": level,
                "num_sentences": num_sentences,
                "user_id": user_id,
                "topic": topic
            }

            # Modify to add question_types if provided
    
            question_types = data.get('question_types')
            if question_types:
                payload["question_types"] = question_types

            if "make_a_sentence" in (payload.get("question_types") or []):
                payload["question_types"] = ["fill_in_blank"]

            if "finish_the_sentence" in (payload.get("question_types") or []):
                payload["question_types"] = ["fill_in_blank"]

            app.logger.info(f"Sending request to {CLOUD_API_URL}/generate_sentences with payload: {payload}")
            response = requests.post(f"{CLOUD_API_URL}/generate_sentences", json=payload, headers=headers, timeout=60)
            app.logger.info(f"API response status: {response.status_code}")
            response.raise_for_status()
            try:
                data = response.json()
            except ValueError as ve:
                app.logger.error(f"Failed to parse API response: {ve}")
                return jsonify({"error": "Invalid API response format", "success": False}), 500
            
            app.logger.info(f"Received API response: {data}")

            if not data.get("success"):
                app.logger.error(f"API error: {data.get('message', 'Unknown error')}")
                return jsonify({"error": data.get("message", "Cloud API error"), "success": False}), 500

            sentences = data.get("sentences", [])
            if not sentences:
                app.logger.warning("No sentences returned from API")
                return jsonify({"error": "No sentences generated", "success": False}), 400

            if "make_a_sentence" in question_types:
                make_a_sentence_questions = []
                for s in sentences:
                    sentence_text = s.get('sentence') or s.get('fill_in_blank') or s.get('arrange_question')
                    if not sentence_text:
                        continue
                    words = re.findall(r'\b\w+\b', sentence_text)
                    if len(words) < 2:
                        continue
                    selected_words = random.sample(words, k=2)
                    question_text = f"Make a sentence using these words: {', '.join(selected_words)}"
                    
                    # Create and save the question to the database
                    new_question = MakeASentence(
                        question=question_text,
                        words=','.join(selected_words),  # Store as comma-separated string
                        level=level,
                        for_user=user_id
                    )
                    db.session.add(new_question)
                    db.session.flush()  # To get the ID before final commit
                    
                    # Now include the database ID in the response
                    make_a_sentence_questions.append({
                        "id": new_question.id,  # Include the ID for the frontend
                        "question": question_text,
                        "words": selected_words,
                        "_chosenType": "make_a_sentence"
                    })
                
                # Commit all the questions to the database
                db.session.commit()
                return jsonify({"success": True, "sentences": make_a_sentence_questions})
            
            if "finish_the_sentence" in question_types:
                finish_sentence_questions = []
                for s in sentences:
                    sentence_text = s.get('sentence') or s.get('fill_in_blank') or s.get('arrange_question')
                    if not sentence_text:
                        continue
                        
                    # Bagi kalimat menjadi dua bagian berdasarkan tanda baca atau konjungsi
                    splits = re.split(r'[,.;]\s+|\s+(?:and|but|or|because|so|while|when|if|unless)\s+', sentence_text)
                    
                    if len(splits) < 2:
                        # Jika tidak ada pemisah alami, bagi kalimat berdasarkan spasi
                        words = sentence_text.split()
                        mid = len(words) // 2
                        # Gabungkan kata-kata menjadi dua bagian
                        splits = [' '.join(words[:mid]), ' '.join(words[mid:])]
                    
                    # Pilih secara random apakah menggunakan bagian depan atau belakang sebagai soal
                    use_first_part = random.choice([True, False])
                    if use_first_part:
                        question_part = splits[0]
                        # Tambahkan ellipsis (...) di akhir untuk menunjukkan bahwa kalimat berlanjut
                        question_text = f"{question_part}..."
                    else:
                        question_part = splits[-1]
                        # Tambahkan ellipsis (...) di awal untuk menunjukkan ada bagian sebelumnya
                        question_text = f"...{question_part}"

                    finish_sentence_questions.append({
                        "question": question_text,
                        "original_sentence": sentence_text,  # Simpan kalimat asli untuk referensi
                        "_chosenType": "finish_the_sentence"
                    })
                
                return jsonify({"success": True, "sentences": finish_sentence_questions})


            # Validate and store sentences
            valid_sentences = []
            for sentence_data in sentences:
                # Map correct fields if missing
                if 'fill_in_blank_answer' not in sentence_data and 'verb' in sentence_data:
                    sentence_data['fill_in_blank_answer'] = sentence_data['verb']
                if 'correct_arrangement' not in sentence_data and 'sentence' in sentence_data:
                    sentence_data['correct_arrangement'] = sentence_data['sentence']

                # Map selection_question fields
                sel = sentence_data.get('selection_question')
                if sel:
                    sentence_data['selection_question_text'] = sel.get('question_text')
                    sentence_data['selection_sentences'] = sel.get('sentences')
                    sentence_data['selection_correct_sentence'] = sel.get('correct_sentence')

                # Map labeling_question fields
                lab = sentence_data.get('labeling_question')
                if lab:
                    sentence_data['labeling_question_text'] = lab.get('question_text')
                    sentence_data['labeling_instruction'] = lab.get('instruction')
                    sentence_data['labeling_correct_labels'] = lab.get('correct_labels')

                # Map fill_in_blank_question fields
                fib = sentence_data.get('fill_in_blank_question')
                if fib:
                    sentence_data['fill_in_blank'] = fib.get('question_text')
                    sentence_data['fill_in_blank_options'] = fib.get('options')
                    sentence_data['fill_in_blank_answer'] = fib.get('correct_answer')

                # Map arrange_question fields
                arr = sentence_data.get('arrange_question')
                if arr:
                    sentence_data['arrange_question'] = arr.get('question_text')
                    sentence_data['arrange_words'] = arr.get('words')  # <-- This line ensures frontend gets the array
                    sentence_data['correct_arrangement'] = arr.get('correct_sentence')

                try:
                    sentence = sentence_data.get('sentence', '')
                    app.logger.debug(f"Validating sentence: {sentence}")

                    # Check required fields
                    # required_fields = ['sentence', 'verb', 'fill_in_blank', 'fill_in_blank_answer', 'arrange_question', 'correct_arrangement', 'level', 'for_user']
                    required_fields = ['sentence', 'verb', 'level', 'for_user']
                    missing_fields = [f for f in required_fields if f not in sentence_data or not sentence_data[f]]
                    if missing_fields:
                        app.logger.warning(f"Skipping sentence with missing fields {missing_fields}: {sentence}")
                        continue

                    # Validate sentence complexity
                    if not is_sentence_appropriate_for_level(sentence, level):
                        app.logger.warning(f"Skipping inappropriate sentence for {level}: {sentence}")
                        continue

                    # Detect contractions in the answer
                    contraction_in_answer = False
                    # For fill-in-the-blank
                    if "'" in str(sentence_data.get('fill_in_blank_answer', '')):
                        contraction_in_answer = True
                    # For multiple choice
                    mc_data = sentence_data.get('multiple_choice')
                    if mc_data and "'" in str(mc_data.get('correct_answer', '')):
                        contraction_in_answer = True

                    # If contraction is found, handle specially but don't skip multiple-choice completely
                    if contraction_in_answer:
                        # Only skip fill-in-the-blank, but still create multiple-choice if present
                        sentence_data['fill_in_blank'] = None
                        sentence_data['fill_in_blank_id'] = None

                    valid_sentences.append(sentence_data)
                    
                    # Store in database
                    try:
                        # Create GroundTruth first
                        gt = GroundTruth(
                            word=sentence_data['verb'],
                            pos='VERB',
                            sentence=sentence,
                            level=sentence_data['level'],
                            for_user=sentence_data['for_user']
                        )
                        db.session.add(gt)
                        db.session.flush()  # Get gt.id

                        # FillInTheBlank
                        fib_data = sentence_data.get('fill_in_blank_question')
                        if fib_data and 'question_text' in fib_data and 'correct_answer' in fib_data:
                            fill_blank = FillInTheBlank(
                                question=fib_data['question_text'],
                                answer=fib_data['correct_answer'],
                                level=sentence_data['level'],
                                for_user=sentence_data['for_user'],
                                ground_truth_id=gt.id
                            )
                            db.session.add(fill_blank)
                            db.session.flush()  # Get the ID before commit
                            sentence_data['fill_in_blank_id'] = fill_blank.id

                        # ArrangeTheWord
                        arr_data = sentence_data.get('arrange_question')
                        if arr_data and 'correct_arrangement' in sentence_data:
                            arrange = ArrangeTheWord(
                                question=sentence_data['arrange_question'],
                                correct_arrangement=sentence_data['correct_arrangement'],
                                level=sentence_data['level'],
                                for_user=sentence_data['for_user'],
                                ground_truth_id=gt.id
                            )
                            db.session.add(arrange)
                            db.session.flush()  # Get the ID before commit
                            sentence_data['arrange_id'] = arrange.id

                        # MultipleChoice
                        mc_data = sentence_data.get('multiple_choice')
                        if mc_data and all(key in mc_data for key in ['question_text', 'options', 'correct_answer']):
                            # Use the provided multiple choice data
                            mc = MultipleChoice(
                                question=mc_data['question_text'],
                                choices=",".join(map(str, mc_data['options'])),
                                correct_answer=str(mc_data['correct_answer']),
                                level=sentence_data['level'],
                                for_user=sentence_data['for_user'],
                                ground_truth_id=gt.id
                            )
                        else:
                            # Create default multiple choice data if none exists
                            # Generate simple options with the correct verb and some distractors
                            correct_verb = sentence_data['verb']
                            # Simple common verbs to use as distractors
                            distractors = ['have', 'do', 'go', 'make', 'take', 'see', 'come', 'know', 'get', 'give']
                            options = [correct_verb]
                            
                            # Add 3 distractors that aren't the correct answer
                            for verb in distractors:
                                if verb != correct_verb and len(options) < 4:
                                    options.append(verb)
                            
                            # If we don't have enough distractors, add some common variations
                            while len(options) < 4:
                                suffix = random.choice(['s', 'ed', 'ing'])
                                distractor = random.choice(distractors) + suffix
                                if distractor not in options:
                                    options.append(distractor)
                            
                            # Shuffle options
                            random.shuffle(options)
                            
                            # Create a simple question text
                            question_text = f"Choose the correct verb for: {sentence.replace(correct_verb, '____')}"
                            
                            mc = MultipleChoice(
                                question=question_text,
                                choices=",".join(options),
                                correct_answer=correct_verb,
                                level=sentence_data['level'],
                                for_user=sentence_data['for_user'],
                                ground_truth_id=gt.id
                            )

                        db.session.add(mc)
                        db.session.flush()  # Get the ID before commit
                        sentence_data['multiple_choice_id'] = mc.id
                        # Also add this line to ensure compatibility with frontend
                        sentence_data['multiple_choice_question_id'] = mc.id
                        
                        # Selection Question
                        sel_data = sentence_data.get('selection_question')
                        # In the generate function where selection questions are created:
                        if sel_data:
                            if not all(key in sel_data for key in ['question_text', 'sentences', 'correct_sentence']):
                                app.logger.warning(f"Skipping invalid selection_question for sentence: {sentence}")
                                continue
                                
                            # Ensure sentences are stored with pipe separator
                            sentences = sel_data['sentences']
                            if isinstance(sentences, list):
                                sentences = "|".join(map(str, sentences))
                            
                            sq = SelectionQuestion(
                                question_text=sel_data['question_text'],  # FIXED: use the correct field name
                                sentences=sentences,
                                correct_sentence=sel_data['correct_sentence'],
                                level=sentence_data['level'],
                                for_user=sentence_data['for_user'],
                                ground_truth_id=gt.id
                            )
                            db.session.add(sq)
                            db.session.flush()  # Get the ID before commit
                            sentence_data['selection_question_id'] = sq.id  # Changed to match the frontend's expected property name
                            
                        # Labeling Question
                        lab_data = sentence_data.get('labeling_question')
                        if lab_data:
                            if not all(key in lab_data for key in ['question_text', 'instruction', 'correct_labels']):
                                app.logger.warning(f"Skipping invalid labeling_question for sentence: {sentence}")
                                continue
                                
                            # Convert correct_labels to string if it's a dictionary/list
                            correct_labels = lab_data['correct_labels']
                            if isinstance(correct_labels, (dict, list)):
                                import json
                                correct_labels = json.dumps(correct_labels)
                                
                            lab = LabelingQuestion(
                                question_text=lab_data['question_text'],
                                instruction=lab_data['instruction'],
                                correct_labels=correct_labels,
                                level=sentence_data['level'],
                                for_user=sentence_data['for_user'],
                                ground_truth_id=gt.id
                            )
                            db.session.add(lab)
                            db.session.flush()  # Get the ID before commit
                            sentence_data['labeling_question_id'] = lab.id

                    except Exception as e:
                        app.logger.error(f"Database error for sentence '{sentence}': {str(e)}")
                        db.session.rollback()
                        continue

                except Exception as e:
                    app.logger.error(f"Error processing sentence data: {str(e)}")
                    continue

            # Commit valid sentences
            if valid_sentences:
                try:
                    db.session.commit()
                    # Increment lessons_completed ONCE per request
                    user = db.session.get(User, user_id)
                    if user:
                        user.lessons_completed = (user.lessons_completed or 0) + 1
                        db.session.commit()
                    app.logger.info(f"Stored {len(valid_sentences)} valid sentences for user {user_id}")
                except Exception as e:
                    app.logger.error(f"Database commit failed: {str(e)}")
                    db.session.rollback()
                    return jsonify({"error": f"Database error: {str(e)}", "success": False}), 500

            if not valid_sentences:
                app.logger.warning("No valid sentences after validation")
                return jsonify({
                    "error": "No sentences meet the complexity requirements for the requested level",
                    "success": False
                }), 400
            
            app.logger.info(f"Returning {len(valid_sentences)} sentences to client")
            return jsonify({
                "success": True,
                "sentences": valid_sentences,
                "message": f"Generated and stored {len(valid_sentences)} sentences for level {level}"
            })

        except requests.exceptions.Timeout:
            app.logger.error("Cloud API request timed out")
            return jsonify({"error": "Cloud API timed out", "success": False}), 504
        except requests.exceptions.RequestException as e:
            app.logger.error(f"Cloud API request failed: {str(e)}")
            return jsonify({"error": f"Failed to connect to cloud API: {str(e)}", "success": False}), 500
        except Exception as e:
            app.logger.error(f"Unexpected error in generate route: {str(e)}")
            return jsonify({"error": f"Server error: {str(e)}", "success": False}), 500

    else:
        return jsonify({"error": "Method not allowed", "success": False}), 405

@app.route('/admin_dashboard')
def admin_dashboard():
    # Check if user is logged in and is admin
    if not session.get('logged_in') or session.get('user_email') != 'admin@yahoo.com':
        return redirect(url_for('login'))
    
    # Set admin flag in session
    session['is_admin'] = True
    
    # Get all users except admin and deleted accounts
    users = User.query.filter(User.email != 'admin@yahoo.com', User.is_deleted == False).all()
    
    # For each user, gather question statistics
    user_data = []
    for user in users:
        # Calculate question stats
        question_stats = {
            'fill_blanks': FillInTheBlank.query.filter_by(for_user=user.id).count(),
            'multiple_choice': MultipleChoice.query.filter_by(for_user=user.id).count(),
            'arrange_words': ArrangeTheWord.query.filter_by(for_user=user.id).count(),
            'selection': SelectionQuestion.query.filter_by(for_user=user.id).count(),
            'labeling': LabelingQuestion.query.filter_by(for_user=user.id).count(),
            'make_sentence': MakeASentence.query.filter_by(for_user=user.id).count(),
            'finish_sentence': FinishTheSentence.query.filter_by(for_user=user.id).count()
        }
        question_stats['total'] = sum(question_stats.values())
        
        # Get performance data
        performance_data = []
        user_performance = UserPerformance.query.filter_by(user_id=user.id).all()
        for perf in user_performance:
            performance_data.append({
                'concept': perf.concept,
                'success_rate': perf.success_rate,
                'error_rate': perf.error_rate,
                'total_attempts': perf.total_attempts
            })
        
        # Create a dictionary with user info and stats, DON'T modify the User model
        # Use a default datetime if join_date doesn't exist
        user_data.append({
            'id': user.id,
            'name': user.name,
            'email': user.email,
            'level': user.level,
            # Use getattr with default to safely handle missing attributes
            'join_date': getattr(user, 'join_date', datetime.datetime.now()),
            'last_active_date': user.last_active_date,
            'question_stats': question_stats,
            'performance': performance_data
        })
    
    return render_template('admin_dashboard.html', users=user_data)

@app.route('/api/submit_placement_test', methods=['POST'])
def submit_placement_test():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    
    data = request.get_json()
    if not data or 'answers' not in data:
        return jsonify({'success': False, 'error': 'Invalid request data'}), 400
    
    user_answers = data['answers']
    
    # Calculate level based on answers
    level_results = {'A1': [], 'A2': [], 'B1': [], 'B2': [], 'C1': [], 'C2': []}
    
    for ans in user_answers:
        question_id = ans.get('id')
        question_type = ans.get('type')
        user_answer = ans.get('answer', '')
        
        if not question_id or not question_type:
            continue
            
        question = None
        level = None
        correct = False
        
        if question_type == 'fill_in_blank':
            question = db.session.get(FillInTheBlank, question_id)
            if question:
                level = question.level
                # Normalize answers by removing trailing punctuation and lowercasing
                def normalize_answer(ans):
                    return ans.strip().lower().rstrip('.,!?;:')
                correct = (normalize_answer(question.answer) == normalize_answer(user_answer))
                question.is_seen = True
                question.user_answer = user_answer
                question.is_correct = correct
                
        elif question_type == 'arrange':
            question = db.session.get(ArrangeTheWord, question_id)
            if question:
                level = question.level
                # Normalize spacing and punctuation for comparison
                correct_arr = ' '.join(question.correct_arrangement.split()).lower()
                user_arr = ' '.join(user_answer.split()).lower()
                correct = (correct_arr == user_arr)
                question.is_seen = True
                question.user_answer = user_answer
                question.is_correct = correct
                
        elif question_type == 'multiple_choice':
            question = db.session.get(MultipleChoice, question_id)
            if question:
                level = question.level
                correct = (question.correct_answer.strip().lower() == user_answer.strip().lower())
                question.is_seen = True
                question.user_answer = user_answer
                question.is_correct = correct
                
        # In the submit_placement_test function, update the selection_question block:
        # Update the selection_question block in submit_placement_test function
        elif question_type == 'selection_question':
            # Check if question_id is valid before querying
            if not question_id or not isinstance(question_id, int):
                app.logger.warning(f"Invalid question_id for selection_question: {question_id}")
                continue
                
            # Use the session.get() method instead of query.get()
            question = db.session.get(SelectionQuestion, question_id)
            if question:
                level = question.level
                # Normalize and compare user answer and correct answer
                def normalize_answer(ans):
                    return ans.strip().lower().rstrip('.,!?;:')
                user_answer_clean = normalize_answer(user_answer)
                correct_answer_clean = normalize_answer(question.correct_sentence)
                correct = (correct_answer_clean == user_answer_clean)
                question.is_seen = True
                question.user_answer = user_answer
                question.is_correct = correct
                
        elif question_type == 'labeling_question':
            question = db.session.get(LabelingQuestion, question_id)
            if question:
                user_labels = {}
                try:
                    # Parse user answer - handle both string and dict formats
                    if isinstance(user_answer, str):
                        if user_answer.startswith('{'):
                            user_labels = json.loads(user_answer)
                        else:
                            # Handle "label:value; label2:value2" format
                            pairs = [p.strip() for p in user_answer.split(';') if p.strip()]
                            for pair in pairs:
                                if ':' in pair:
                                    label, value = pair.split(':', 1)
                                    user_labels[label.strip().lower()] = value.strip().lower()
                    elif isinstance(user_answer, dict):
                        user_labels = {k.lower(): str(v).lower() for k, v in user_answer.items()}
                except Exception as e:
                    app.logger.error(f"Error parsing user answer: {str(e)}")
                    user_labels = {}

                # Get correct labels
                correct_labels = {}
                if isinstance(question.correct_labels, str):
                    try:
                        if question.correct_labels.startswith('{'):
                            correct_labels = json.loads(question.correct_labels)
                        else:
                            # Handle "label:value; label2:value2" format
                            pairs = [p.strip() for p in question.correct_labels.split(';') if p.strip()]
                            for pair in pairs:
                                if ':' in pair:
                                    label, value = pair.split(':', 1)
                                    correct_labels[label.strip().lower()] = value.strip().lower()
                    except json.JSONDecodeError:
                        correct_labels = {}
                else:
                    correct_labels = question.correct_labels

            # Normalize and compare
            def normalize_value(val):
                return str(val).lower().replace("'", "").replace(".", "").strip()

            # Add debug logging for user_labels and correct_labels
            app.logger.debug(f"Labeling Question ID: {question_id}")
            app.logger.debug(f"User Labels Parsed: {user_labels}")
            app.logger.debug(f"Correct Labels Parsed: {correct_labels}")

            # Compare ignoring order
            user_normalized = {k: normalize_value(v) for k, v in user_labels.items()}
            correct_normalized = {k: normalize_value(v) for k, v in correct_labels.items()}

            app.logger.debug(f"User Normalized: {user_normalized}")
            app.logger.debug(f"Correct Normalized: {correct_normalized}")

            is_correct = (user_normalized == correct_normalized)
            app.logger.debug(f"Labeling Question is_correct: {is_correct}")

            question.is_seen = True
            question.user_answer = str(user_answer)
            question.is_correct = is_correct
    
    # Save all question updates
    try:
        db.session.commit()
    except Exception as e:
        app.logger.error(f"Error updating question status: {str(e)}")
        db.session.rollback()
    
    # Determine user's level - the highest level with at least 60% correct answers and minimum 2 questions
    assigned_level = 'A1'  # Default
    level_messages = {
        'A1': "You're at the beginner level. We'll help you build a solid foundation.",
        'A2': "You have basic knowledge. Let's expand your vocabulary and grammar.",
        'B1': "You're at an intermediate level. We'll work on more complex structures.",
        'B2': "You have upper-intermediate skills. Let's refine your language use.",
        'C1': "You're at an advanced level. We'll focus on nuance and fluency.",
        'C2': "You've reached proficiency level. We'll help you master the subtleties."
    }
    
    for level in ['C2', 'C1', 'B2', 'B1', 'A2', 'A1']:
        results = level_results[level]
        if len(results) >= 2 and sum(results) / max(len(results), 1) >= 0.6:
            assigned_level = level
            break
    
    # Record the placement test attempt
    try:
        test_attempt = PlacementTestAttempt(
            user_id=user_id,
            completed_at=datetime.datetime.now(),
            estimated_level=assigned_level
        )
        db.session.add(test_attempt)
        
        # Update user's level
        user = db.session.get(User, user_id)
        if user:
            user.level = assigned_level
        
        db.session.commit()
    except Exception as e:
        app.logger.error(f"Error saving placement test results: {str(e)}")
        db.session.rollback()
    
    return jsonify({
        'success': True,
        'level': assigned_level,
        'message': level_messages.get(assigned_level, "Thank you for completing the placement test.")
    })

@app.route('/submit_answer', methods=['POST'])
def submit_answer():
    data = request.get_json()
    
    # Add debug logging to see what's being received
    app.logger.info(f"Received submit_answer data: {data}")
    
    question_id = data.get('question_id')
    user_answer = data.get('user_answer')
    question_type = data.get('question_type')
    time_spent = data.get('time_spent', 0)

    app.logger.info(f"submit_answer called with question_id={question_id}, question_type={question_type}")

    if not question_id:
        # Try to get the ID from another field that might be used
        question_id = data.get('id')
        if not question_id:
            app.logger.error("submit_answer: Missing question_id")
            return jsonify({'success': False, 'error': 'Missing question_id'}), 400

    # Convert question_id to int if it's a string
    try:
        question_id = int(question_id)
    except (TypeError, ValueError):
        app.logger.error(f"submit_answer: Invalid question_id format: {question_id}")
        return jsonify({'success': False, 'error': 'Invalid question_id format'}), 400

    user = db.session.get(User, session.get('user_id'))
    if not user:
        app.logger.error("submit_answer: User not found or not logged in")
        return jsonify({'success': False, 'error': 'User not authenticated'}), 401

    today = date.today()
    if user.last_active_date == today - timedelta(days=1):
        user.streak += 1
    elif user.last_active_date != today:
        user.streak = 1
    user.last_active_date = today
    if time_spent and int(time_spent) > 0:
        user.study_time = (user.study_time or 0) + int(time_spent)
    user.total_attempts = (user.total_attempts or 0) + 1
    n = user.total_attempts - 1

    is_correct = False

    def normalize_answer(ans):
        if not ans:
            return ''
        return ans.strip().lower()

    question = None
    try:
        if question_type == 'make_a_sentence':
            question = db.session.get(MakeASentence, question_id)
            if question:
                # Split and normalize each word
                if isinstance(question.words, str):
                    # Split by commas first (primary), then spaces as fallback
                    if ',' in question.words:
                        required_words = [w.strip().lower() for w in question.words.split(',')]
                    else:
                        required_words = [w.strip().lower() for w in question.words.split()]
                else:
                    required_words = []
                
                # Extract words from user answer - properly handle punctuation and case
                user_answer_lower = user_answer.lower() if user_answer else ""
                # Use regex to extract just words, ignoring punctuation
                user_words = re.findall(r'\b\w+\b', user_answer_lower)
                
                # Debug logging
                app.logger.info(f"Required words: {required_words}")
                app.logger.info(f"Words in answer: {user_words}")
                
                # Check if ALL required words are in the user's answer
                is_correct = all(word in user_words for word in required_words)
                
                question.user_answer = user_answer
                question.score = 100 if is_correct else 0
                question.is_seen = True
                # Ensure is_correct is set for make_a_sentence questions
                if not hasattr(question, 'is_correct'):
                    # Add the attribute dynamically if it doesn't exist
                    setattr(question, 'is_correct', is_correct)
                else:
                    question.is_correct = is_correct

        elif question_type == 'finish_the_sentence':
            question = db.session.get(FinishTheSentence, question_id)
            if question:
                required_text = question.words or question.question.replace("Finish the sentence:", "").strip()
                # Split by commas first (primary), then spaces as fallback
                if ',' in required_text:
                    required_words = [w.strip().lower() for w in required_text.split(',')]
                else:
                    # Extract just the words using regex
                    required_words = re.findall(r'\b\w+\b', required_text.lower())
                
                # Extract words from user answer
                user_answer_lower = user_answer.lower() if user_answer else ""
                user_words = re.findall(r'\b\w+\b', user_answer_lower)
                
                # Debug logging
                app.logger.info(f"Required words: {required_words}")
                app.logger.info(f"Words in answer: {user_words}")
                
                is_correct = all(word in user_words for word in required_words)
                question.user_answer = user_answer
                question.score = 100 if is_correct else 0
                question.is_seen = True
                # Ensure is_correct is set for finish_the_sentence questions
                if not hasattr(question, 'is_correct'):
                    # Add the attribute dynamically if it doesn't exist
                    setattr(question, 'is_correct', is_correct)
                else:
                    question.is_correct = is_correct
                
        elif question_type == 'fill_in_blank':
            question = db.session.get(FillInTheBlank, question_id)
            if question:
                is_correct = normalize_answer(question.answer) == normalize_answer(user_answer)
                question.user_answer = user_answer
                question.is_correct = is_correct
                
        elif question_type == 'multiple_choice':
            question = db.session.get(MultipleChoice, question_id)
            if question:
                is_correct = normalize_answer(question.correct_answer) == normalize_answer(user_answer)
                question.user_answer = user_answer
                question.is_correct = is_correct
                
        elif question_type == 'selection_question':
            question = db.session.get(SelectionQuestion, question_id)
            if question:
                is_correct = normalize_answer(question.correct_sentence) == normalize_answer(user_answer)
                question.user_answer = user_answer
                question.is_correct = is_correct
                
        elif question_type == 'arrange_question':
            question = db.session.get(ArrangeTheWord, question_id)
            if question:
                # Normalize both strings for comparison
                def normalize_for_arrange(text):
                    if not text:
                        return ''
                    # Remove punctuation, normalize spaces, and convert to lowercase
                    normalized = re.sub(r'[.,!?;:]', '', text)
                    normalized = re.sub(r'\s+', ' ', normalized)
                    return normalized.strip().lower()
                    
                correct_normalized = normalize_for_arrange(question.correct_arrangement)
                user_normalized = normalize_for_arrange(user_answer)
                is_correct = (correct_normalized == user_normalized)
                question.user_answer = user_answer
                question.is_correct = is_correct
                
        elif question_type == 'labeling_question':
            question = db.session.get(LabelingQuestion, question_id)
            if question:
                # Parse user answer
                user_labels = {}
                try:
                    if isinstance(user_answer, str):
                        if user_answer.startswith('{'):
                            user_labels = json.loads(user_answer)
                        else:
                            # Handle "label:value; label2:value2" format
                            pairs = [p.strip() for p in user_answer.split(';') if p.strip()]
                            for pair in pairs:
                                if ':' in pair:
                                    label, value = pair.split(':', 1)
                                    user_labels[label.strip().lower()] = value.strip().lower()
                    elif isinstance(user_answer, dict):
                        user_labels = {k.lower(): str(v).lower() for k, v in user_answer.items()}
                except Exception as e:
                    app.logger.error(f"Error parsing user answer: {str(e)}")
                    user_labels = {}

                # Get correct labels
                correct_labels = {}
                if isinstance(question.correct_labels, str):
                    try:
                        correct_labels = json.loads(question.correct_labels)
                    except json.JSONDecodeError:
                        correct_labels = {}
                else:
                    correct_labels = question.correct_labels

                # Normalize and compare
                def normalize_value(val):
                    return str(val).lower().replace("'", "").replace(".", "").strip()

                # Compare ignoring order
                user_normalized = {k: normalize_value(v) for k, v in user_labels.items()}
                correct_normalized = {k: normalize_value(v) for k, v in correct_labels.items()}
                is_correct = (user_normalized == correct_normalized)
                
                question.user_answer = str(user_answer)
                question.is_correct = is_correct
        else:
            app.logger.error(f"Unsupported question_type: {question_type}")
            return jsonify({'success': False, 'error': f'Unsupported question type: {question_type}'}), 400

        if not question:
            app.logger.error(f"Question not found: id={question_id}, type={question_type}")
            return jsonify({'success': False, 'error': 'Question not found'}), 404

        user.average_score = ((user.average_score * n) + (100 if is_correct else 0)) / (n + 1)
        db.session.commit()

        concept = data.get('concept')
        if concept:
            concept = concept.strip().lower()
        else:
            concept = 'unknown'

        perf = UserPerformance.query.filter_by(user_id=user.id, concept=concept).first()
        if not perf:
            perf = UserPerformance(user_id=user.id, concept=concept)
            db.session.add(perf)
        perf.total_attempts = (perf.total_attempts or 0) + 1
        if is_correct:
            perf.correct_attempts = (perf.correct_attempts or 0) + 1
        perf.success_rate = 100.0 * (perf.correct_attempts or 0) / (perf.total_attempts or 1)
        perf.error_rate = 100.0 - perf.success_rate
        perf.timestamp = datetime.datetime.now()
        db.session.commit()

        return jsonify({
            'success': True,
            'is_correct': is_correct,
            'message': 'Correct!' if is_correct else 'Incorrect.'
        })

    except Exception as e:
        app.logger.error(f"Exception in submit_answer: {str(e)}")
        # Add more detailed error logging
        import traceback
        app.logger.error(f"Exception details: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500

@app.route('/api/placement_test_questions')
def placement_test_questions():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401

    levels = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2']
    questions = []

    for level in levels:
        level_questions = []

        # Fill-in-the-blank: skip if apostrophe in question or answer
        fib = FillInTheBlank.query.filter_by(is_seen=False, for_user=user_id, level=level).all()
        for q in fib:
            if "'" in q.question or "'" in q.answer:
                continue
            level_questions.append({
                'id': q.id,
                'type': 'fill_in_blank',
                'question': q.question,
                'answer': q.answer,
                'level': level
            })

        # Arrange: always include, even if apostrophe
        atw = ArrangeTheWord.query.filter_by(is_seen=False, for_user=user_id, level=level).all()
        for q in atw:
            level_questions.append({
                'id': q.id,
                'type': 'arrange',
                'question': q.question,
                'correct_arrangement': q.correct_arrangement,
                'level': level
            })

        # Multiple choice: skip if apostrophe in question, any choice, or correct answer
        mc = MultipleChoice.query.filter_by(is_seen=False, for_user=user_id, level=level).all()
        for q in mc:
            if isinstance(q.choices, str):
                choices = [c.strip() for c in q.choices.split(',')]
            else:
                choices = q.choices
            if ("'" in q.question or "'" in q.correct_answer or any("'" in c for c in choices)):
                continue
            level_questions.append({
                'id': q.id,
                'type': 'multiple_choice',
                'question': q.question,
                'choices': choices,
                'correct_answer': q.correct_answer,
                'level': level
            })
            
        # Selection questions
        # In the API that returns placement test questions, update the selection_question block:
# Selection questions
        sq = SelectionQuestion.query.filter_by(is_seen=False, for_user=user_id, level=level).all()
        for q in sq:
            # Handle sentence splitting properly based on the pipe separator
            if isinstance(q.sentences, str):
                sentences = q.sentences.split('|')
            else:
                sentences = q.sentences
                
            level_questions.append({
                'id': q.id,
                'type': 'selection_question',
                'question': q.question_text,  # Use consistent field name
                'sentences': sentences,
                'correct_sentence': q.correct_sentence,
                'level': level
            })
            
        # Labeling questions
        lq = LabelingQuestion.query.filter_by(is_seen=False, for_user=user_id, level=level).all()
        for q in lq:
            import json
            correct_labels = q.correct_labels
            if isinstance(correct_labels, str):
                try:
                    correct_labels = json.loads(correct_labels)
                except:
                    pass  # Keep as string if not valid JSON
                    
            level_questions.append({
                'id': q.id,
                'type': 'labeling_question',
                'question': q.question_text,
                'instruction': q.instruction,
                'correct_labels': correct_labels,
                'level': level
            })

        random.shuffle(level_questions)
        questions.extend(level_questions[:3])  # Take up to 3 per level

    random.shuffle(questions)
    # Optionally, limit to a max number if needed, e.g. questions = questions[:18]

    return jsonify({'success': True, 'questions': questions})

@app.route('/placement_test')
def placement_test():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return render_template('placement_test.html')

@app.route('/delete_account', methods=['POST'])
def delete_account():
    if not session.get('logged_in'):
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    
    user_id = session.get('user_id')
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'success': False, 'error': 'User not found'}), 404
    
    try:
        # Mark the user as deleted instead of actually removing from the database
        user.is_deleted = True
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': 'Account deleted successfully'
        })
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error deleting account: {str(e)}")
        return jsonify({'success': False, 'error': 'Database error'}), 500

@app.route('/generate_make_a_sentence', methods=['POST'])
def generate_make_a_sentence():
    if not session.get('logged_in'):
        return jsonify({'success': False, 'error': 'Not logged in'}), 401

    user_id = session.get('user_id')
    level = request.json.get('level', 'A1')

    # Ambil beberapa soal FillInTheBlank milik user & level terkait
    fib_questions = FillInTheBlank.query.filter_by(for_user=user_id, level=level).all()
    if not fib_questions:
        return jsonify({'success': False, 'error': 'No FillInTheBlank questions found'}), 404

    created_questions = []
    for fib in fib_questions:
        # Ambil kata unik dari kalimat (hilangkan tanda baca)
        words = re.findall(r'\b\w+\b', fib.question)
        if len(words) < 2:
            continue
        # Pilih 1 atau 2 kata acak
        selected_words = random.sample(words, k=random.choice([1, 2]))
        question_text = f"Make a sentence using these words: {', '.join(selected_words)}"

        # Simpan ke database
        mas = MakeASentence(
            question=question_text,
            words=",".join(selected_words),
            level=level,
            for_user=user_id
        )
        db.session.add(mas)
        created_questions.append({
            'id': mas.id,  # Tambahkan ID untuk referensi
            'question': question_text,
            'words': selected_words
        })

    # Commit semua soal ke database
    db.session.commit()
    return jsonify({'success': True, 'questions': created_questions})

def fix_correction_format(correction):
    """
    Memperbaiki format string koreksi dengan menambahkan spasi yang diperlukan:
    Dari: "Changed'schuool' to'school' - Replace spelling"
    Menjadi: "Changed 'schuool' to 'school' - Replace spelling"
    """
    # Tambahkan spasi setelah 'Changed' dan sebelum/sesudah 'to'
    correction = correction.replace("Changed'", "Changed '") \
                          .replace("to'", "to '") \
                          .replace("' -", "' - ")
    return correction

def generate_natural_explanation(correction):
    """Generate natural-sounding grammar correction explanations from text format"""
    if not correction:
        return "No corrections needed"
    
    if "no operation" in correction.lower() or "no correction" in correction.lower():
        return "No grammatical errors found"
        
    # Clean the correction string
    correction = str(correction).strip()
    
    # Remove numbering if present (e.g., "1. Changed X to Y")
    if correction.startswith(('1. ', '2. ', '3. ', '4. ')):
        correction = correction[3:]
    
    # Define error type mappings
    error_type_mappings = {
        'other': 'grammar',
        'orthographic': 'spelling',
        'morphological': 'word form'
    }
    
    # Common patterns to extract information
    patterns = [
        # Pattern for replacements: "Changed 'X' to 'Y' - Error type"
        (r"Changed\s+'([^']*)'\s+to\s+'([^']*)'\s*-\s*(Replace|Missing|Unnecessary)\s*(.*)", 
         lambda m: (
             m[3].lower(),  # operation (replace/missing/unnecessary)
             m[4].lower(),  # error type
             m[1],         # before
             m[2]          # after
         )),
         
        # Alternative pattern without "Changed"
        (r"(Replace|Missing|Unnecessary)\s+'([^']*)'(\s+to\s+'([^']*)')?\s*-\s*(.*)", 
         lambda m: (
             m[1].lower(),
             m[5].lower(),
             m[2] if m[1].lower() != 'missing' else '',
             m[4] if m[1].lower() == 'replace' else m[2]
         ))
    ]
    
    # Try to extract components from the correction
    operation, error_type, before, after = None, None, None, None
    
    for pattern, extractor in patterns:
        match = re.match(pattern, correction)
        if match:
            operation, error_type, before, after = extractor(match)
            break
    
    # If we couldn't parse, return the original with basic cleaning
    if not operation:
        return correction.replace("Changed'", "Changed '") \
                       .replace("to'", "to '") \
                       .replace("' -", "' - ") \
                       .replace("  ", " ")
    
    # Clean and map the error type
    error_type = error_type.strip().lower()
    error_type = error_type_mappings.get(error_type, error_type)
    
    # Capitalize and add "error" if it's not already there
    if not error_type.endswith(' error'):
        error_type = error_type + ' error'
    error_type = error_type.capitalize()
    
    # Generate the explanation based on operation type
    if operation == 'replace':
        explanation = f"{error_type}, replacing '{before}' with '{after}'"
    elif operation == 'missing':
        explanation = f"{error_type}, missing '{after}'"
    elif operation == 'unnecessary':
        explanation = f"{error_type}, '{before}' is unnecessary"
    else:
        explanation = correction
    
    return explanation

@app.route('/submit_make_a_sentence', methods=['POST'])
def submit_make_a_sentence():
    if not session.get('logged_in'):
        return jsonify({'success': False, 'error': 'Not logged in'}), 401

    data = request.get_json()
    user_id = session.get('user_id')
    sentence = data.get('sentence', '').strip()
    question_id = data.get('question_id')  # Pastikan frontend mengirimkan ID soal

    if not sentence:
        return jsonify({'success': False, 'error': 'No sentence provided'}), 400

    # Kirim ke API grammar correction
    grammar_url = f"{CLOUD_API_Grammar_URL}/grammar_correction"
    payload = {
        "user_id": user_id,
        "sentence": sentence
    }

    try:
        response = requests.post(grammar_url, json=payload, timeout=15)
        response.raise_for_status()
        
        grammar_result = response.json()
        app.logger.info(f"Raw API response: {grammar_result}")

        # Validate response structure
        if not isinstance(grammar_result, dict):
            return jsonify({'success': False, 'error': 'Invalid API response format'}), 500

        # Ensure we have the corrected text
        if 'corrected' not in grammar_result:
            grammar_result['corrected'] = sentence  # Fallback to original if no correction

        # Process corrections to ensure consistent format
        corrections = grammar_result.get('corrections', [])
        if isinstance(corrections, str):
            corrections = [corrections]
        elif not isinstance(corrections, list):
            corrections = []
        
        processed_corrections = []
        for corr in corrections:
            if not corr:
                continue
            if isinstance(corr, str) and '. ' in corr:
                corr = corr.split('. ', 1)[1]

            if "no operation" in corr.lower() or "no correction" in corr.lower():
                processed_corrections.append("No grammatical errors found")
            else:
                # Apply formatting fixes
                formatted_corr = fix_correction_format(str(corr))
                # Generate natural language explanation
                natural_explanation = generate_natural_explanation(formatted_corr)
                processed_corrections.append(natural_explanation)

        # Calculate score
        if not processed_corrections or "No grammatical errors found" in processed_corrections:
            score = 1
        else:
            score = max(0, 1 - (len(processed_corrections) * 0.1))
        
        # Simpan jawaban dan skor ke database
        question = db.session.get(MakeASentence, question_id)
        if question and question.for_user == user_id:
            question.user_answer = sentence
            question.score = score
            db.session.commit()

        return jsonify({
            'success': True,
            'result': {
                'original': sentence,
                'corrected': grammar_result.get('corrected', sentence),
                'corrections': processed_corrections,
                'score': score
            }
        })
        
    except requests.exceptions.Timeout:
        app.logger.error("Grammar API timeout")
        return jsonify({'success': False, 'error': 'Grammar check timed out'}), 504
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Grammar API error: {str(e)}")
        return jsonify({'success': False, 'error': f'Grammar API error: {str(e)}'}), 500
    except Exception as e:
        app.logger.error(f"Unexpected error: {str(e)}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500

@app.route('/generate_finish_the_sentence', methods=['POST'])
def generate_finish_the_sentence():
    if not session.get('logged_in'):
        return jsonify({'success': False, 'error': 'Not logged in'}), 401

    user_id = session.get('user_id')
    level = request.json.get('level', 'A1')

    # Ambil beberapa soal FillInTheBlank milik user & level terkait
    fib_questions = FillInTheBlank.query.filter_by(for_user=user_id, level=level).all()
    if not fib_questions:
        return jsonify({'success': False, 'error': 'No FillInTheBlank questions found'}), 404

    created_questions = []
    for fib in fib_questions:
        sentence_text = fib.question
        if not sentence_text:
            continue
            
        # Bagi kalimat menjadi dua bagian berdasarkan tanda baca atau konjungsi
        splits = re.split(r'[,.;]\s+|\s+(?:and|but|or|because|so|while|when|if|unless)\s+', sentence_text)
        
        if len(splits) < 2:
            # Jika tidak ada pemisah alami, bagi kalimat berdasarkan spasi
            words = sentence_text.split()
            mid = len(words) // 2
            # Gabungkan kata-kata menjadi dua bagian
            splits = [' '.join(words[:mid]), ' '.join(words[mid:])]
        
        # Pilih secara random apakah menggunakan bagian depan atau belakang sebagai soal
        use_first_part = random.choice([True, False])
        if use_first_part:
            question_part = splits[0]
            # Tambahkan ellipsis (...) di akhir untuk menunjukkan bahwa kalimat berlanjut
            partial_sentence = f"{question_part}..."
        else:
            question_part = splits[-1]
            # Tambahkan ellipsis (...) di awal untuk menunjukkan ada bagian sebelumnya
            partial_sentence = f"...{question_part}"

        # Format pertanyaan dengan "Finish the sentence:"
        question_text = f"Finish the sentence: {partial_sentence}"

        # Simpan ke database dengan format yang benar
        fts = FinishTheSentence(
            question=question_text,  # Pertanyaan lengkap dengan "Finish the sentence:"
            words=partial_sentence,  # Bagian kalimat yang ditampilkan dengan ...
            level=level,
            for_user=user_id
        )
        db.session.add(fts)
        created_questions.append({
            'id': fts.id,
            'question': question_text,  # Pertanyaan lengkap
            'words': partial_sentence,  # Bagian kalimat yang ditampilkan
            'original_sentence': sentence_text,  # Kalimat asli untuk referensi
            '_chosenType': 'finish_the_sentence'
        })

    # Commit semua soal ke database
    db.session.commit()
    return jsonify({'success': True, 'questions': created_questions})

@app.route('/submit_finish_the_sentence', methods=['POST'])
def submit_finish_the_sentence():
    if not session.get('logged_in'):
        return jsonify({'success': False, 'error': 'Not logged in'}), 401

    data = request.get_json()
    user_id = session.get('user_id')
    sentence = data.get('sentence', '').strip()
    question_id = data.get('question_id')  # Pastikan frontend mengirimkan ID soal

    if not sentence:
        return jsonify({'success': False, 'error': 'No sentence provided'}), 400

    # Kirim ke API grammar correction
    grammar_url = f"{CLOUD_API_Grammar_URL}/grammar_correction"
    payload = {
        "user_id": user_id,
        "sentence": sentence
    }

    try:
        response = requests.post(grammar_url, json=payload, timeout=15)
        response.raise_for_status()
        
        grammar_result = response.json()
        app.logger.info(f"Raw API response: {grammar_result}")

        # Validate response structure
        if not isinstance(grammar_result, dict):
            return jsonify({'success': False, 'error': 'Invalid API response format'}), 500

        # Ensure we have the corrected text
        if 'corrected' not in grammar_result:
            grammar_result['corrected'] = sentence  # Fallback to original if no correction

        # Process corrections to ensure consistent format
        corrections = grammar_result.get('corrections', [])
        if isinstance(corrections, str):
            corrections = [corrections]
        elif not isinstance(corrections, list):
            corrections = []
        
        processed_corrections = []
        for corr in corrections:
            if not corr:
                continue
            if isinstance(corr, str) and '. ' in corr:
                corr = corr.split('. ', 1)[1]

            if "no operation" in corr.lower() or "no correction" in corr.lower():
                processed_corrections.append("No grammatical errors found")
            else:
                # Apply formatting fixes
                formatted_corr = fix_correction_format(str(corr))
                # Generate natural language explanation
                natural_explanation = generate_natural_explanation(formatted_corr)
                processed_corrections.append(natural_explanation)

        # Calculate score
        if not processed_corrections or "No grammatical errors found" in processed_corrections:
            score = 100
        else:
            score = max(0, 100 - (len(processed_corrections) * 10))
        
        # Simpan jawaban dan skor ke database
        question = db.session.get(FinishTheSentence, question_id)
        if question and question.for_user == user_id:
            question.user_answer = sentence
            question.score = score
            db.session.commit()

        return jsonify({
            'success': True,
            'result': {
                'original': sentence,
                'corrected': grammar_result.get('corrected', sentence),
                'corrections': processed_corrections,
                'score': score
            }
        })
        
    except requests.exceptions.Timeout:
        app.logger.error("Grammar API timeout")
        return jsonify({'success': False, 'error': 'Grammar check timed out'}), 504
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Grammar API error: {str(e)}")
        return jsonify({'success': False, 'error': f'Grammar API error: {str(e)}'}), 500
    except Exception as e:
        app.logger.error(f"Unexpected error: {str(e)}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500
    
# # Create database tables
with app.app_context():
    db.create_all()
    if not User.query.filter_by(email='admin@yahoo.com').first():
        admin = User(email='admin@yahoo.com', name='Admin User', language='English', level='C2')
        admin.set_password('admin321')
        db.session.add(admin)
        db.session.commit()

if __name__ == '__main__':
    app.run()
    
       
# flask shell

# # In the Flask shell, run:
# from app import db
# db.drop_all()
# db.create_all()
# exit()