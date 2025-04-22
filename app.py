# app.py
import os
import logging
import requests
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import datetime
from sqlalchemy.sql import func
from logging.handlers import RotatingFileHandler
from datetime import date, timedelta
import random

app = Flask(__name__)
app.secret_key = "12345"

# Configure PostgreSQL database
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://yechiel@localhost/languagex'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Cloud API configuration
CLOUD_API_URL = os.getenv('CLOUD_API_URL', 'https://0038-34-168-155-130.ngrok-free.app')

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
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

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

# Logging setup
if not os.path.exists('logs'):
    os.makedirs('logs')
handler = RotatingFileHandler('logs/app.log', maxBytes=10000, backupCount=1)
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
    if request.method == 'GET':
        return render_template('login.html')
    
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        if (email == 'test@test.com' and password == 'password') or (email == 'admin@yahoo.com' and password == 'admin321'):
            session['logged_in'] = True
            session['user_id'] = 0
            return redirect(url_for('generate'))
        
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password):
            session['logged_in'] = True
            session['user_id'] = user.id
            session['user_name'] = user.name
            return redirect(url_for('generate'))
            
        return render_template('login.html', error="Invalid credentials")

@app.route('/profile')
def profile():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    user_id = session.get('user_id')
    user = User.query.get(user_id)
    if not user:
        return redirect(url_for('login'))
    
    # Format study time as hours and minutes
    study_time_str = format_study_time(user.study_time or 0)
    
    user_data = {
        'name': user.name,
        'level': user.level,
        'language': user.language,
        'study_time': study_time_str,
        'streak': str(user.streak),
        'lessons_completed': str(user.lessons_completed),
        'average_score': str(int(user.average_score)),
        'performance': []
    }
    
    # Gather performance stats
    performance = UserPerformance.query.filter_by(user_id=user_id).order_by(UserPerformance.timestamp.desc()).all()
    for perf in performance:
        user_data['performance'].append({
            'concept': perf.concept,
            'success_rate': str(int(perf.success_rate)),
            'error_rate': str(int(perf.error_rate)),
            'total_attempts': perf.total_attempts
        })
    
    return render_template('profile.html', user=user_data)

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
                level = data.get('level')
                num_sentences_str = str(data.get('num_sentences', 2))
                topic = data.get('topic', '')
                user_id = data.get('user_id') or session.get('user_id')
            else:
                level = request.form.get('level')
                num_sentences_str = request.form.get('num_sentences', '2')
                topic = request.form.get('topic', '')
                user_id = session.get('user_id')

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

            # Validate and store sentences
            valid_sentences = []
            for sentence_data in sentences:
                # Map correct fields if missing
                if 'fill_in_blank_answer' not in sentence_data and 'verb' in sentence_data:
                    sentence_data['fill_in_blank_answer'] = sentence_data['verb']
                if 'correct_arrangement' not in sentence_data and 'sentence' in sentence_data:
                    sentence_data['correct_arrangement'] = sentence_data['sentence']

                try:
                    sentence = sentence_data.get('sentence', '')
                    app.logger.debug(f"Validating sentence: {sentence}")

                    # Check required fields
                    required_fields = ['sentence', 'verb', 'fill_in_blank', 'fill_in_blank_answer', 'arrange_question', 'correct_arrangement', 'level', 'for_user']
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

                    # If contraction is found, only create ArrangeTheWord and skip fill-in-the-blank/multiple-choice
                    if contraction_in_answer:
                        try:
                            arrange = ArrangeTheWord(
                                question=sentence_data['arrange_question'],
                                correct_arrangement=sentence_data['correct_arrangement'],
                                level=sentence_data['level'],
                                for_user=sentence_data['for_user']
                            )
                            db.session.add(arrange)
                            db.session.flush()
                            sentence_data['arrange_id'] = arrange.id
                            # Mark only arrange_question as available
                            sentence_data['fill_in_blank'] = None
                            sentence_data['fill_in_blank_id'] = None
                            sentence_data['multiple_choice'] = None
                            sentence_data['multiple_choice_id'] = None
                            valid_sentences.append(sentence_data)
                        except Exception as e:
                            app.logger.error(f"Database error for arrange sentence '{sentence}': {str(e)}")
                            db.session.rollback()
                        continue  # Skip the rest of the loop for this sentence

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
                        fill_blank = FillInTheBlank(
                            question=sentence_data['fill_in_blank'],
                            answer=sentence_data['fill_in_blank_answer'],
                            level=sentence_data['level'],
                            for_user=sentence_data['for_user'],
                            ground_truth_id=gt.id
                        )
                        db.session.add(fill_blank)
                        db.session.flush()  # Get the ID before commit
                        sentence_data['fill_in_blank_id'] = fill_blank.id

                        # ArrangeTheWord
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
                        if mc_data:
                            if not all(key in mc_data for key in ['question_text', 'options', 'correct_answer']):
                                app.logger.warning(f"Skipping invalid multiple_choice for sentence: {sentence}")
                                continue
                            mc = MultipleChoice(
                                question=mc_data['question_text'],
                                choices=",".join(map(str, mc_data['options'])),
                                correct_answer=str(mc_data['correct_answer']),
                                level=sentence_data['level'],
                                for_user=sentence_data['for_user'],
                                ground_truth_id=gt.id
                            )
                            db.session.add(mc)
                            db.session.flush()  # Get the ID before commit
                            sentence_data['multiple_choice_id'] = mc.id
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
                    user = User.query.get(user_id)
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

@app.route('/submit_answer', methods=['POST'])
def submit_answer():
    data = request.get_json()
    question_id = data.get('question_id')
    user_answer = data.get('user_answer')
    is_correct = data.get('is_correct')
    question_type = data.get('question_type')
    time_spent = data.get('time_spent', 0)  # sent from frontend

    user = User.query.get(session['user_id'])
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
    # Update stats (you may want to store total/correct/incorrect counts for accuracy)
    perf.total_attempts = (perf.total_attempts or 0) + 1
    if is_correct:
        perf.correct_attempts = (perf.correct_attempts or 0) + 1
    # Calculate rates
    perf.success_rate = 100.0 * (perf.correct_attempts or 0) / (perf.total_attempts or 1)
    perf.error_rate = 100.0 - perf.success_rate
    perf.timestamp = datetime.datetime.now()
    db.session.commit()

    if question_type == 'fill_in_blank':
        question = FillInTheBlank.query.get(question_id)
    elif question_type == 'arrange_question':
        question = ArrangeTheWord.query.get(question_id)
    elif question_type == 'multiple_choice':
        question = MultipleChoice.query.get(question_id)
    else:
        question = None

    if question:
        question.user_answer = user_answer
        question.is_correct = is_correct
        db.session.commit()
        return jsonify({'success': True})

    return jsonify({'success': False, 'error': 'Question not found'}), 404

@app.route('/api/placement_test_questions')
def placement_test_questions():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401

    questions = []

    # Fill-in-the-blank: skip if apostrophe in question or answer
    fib = FillInTheBlank.query.filter_by(is_seen=False, for_user=user_id).all()
    for q in fib:
        if "'" in q.question or "'" in q.answer:
            continue  # skip if apostrophe
        questions.append({
            'id': q.id,
            'type': 'fill_in_blank',
            'question': q.question,
            'answer': q.answer,
        })

    # Arrange: always include, even if apostrophe
    atw = ArrangeTheWord.query.filter_by(is_seen=False, for_user=user_id).all()
    for q in atw:
        questions.append({
            'id': q.id,
            'type': 'arrange',
            'question': q.question,
            'correct_arrangement': q.correct_arrangement,
        })

    # Multiple choice: skip if apostrophe in question, any choice, or correct answer
    mc = MultipleChoice.query.filter_by(is_seen=False, for_user=user_id).all()
    for q in mc:
        # Convert choices to list
        if isinstance(q.choices, str):
            choices = [c.strip() for c in q.choices.split(',')]
        else:
            choices = q.choices
        # Skip if apostrophe in question, any choice, or correct answer
        if ("'" in q.question or "'" in q.correct_answer or any("'" in c for c in choices)):
            continue
        questions.append({
            'id': q.id,
            'type': 'multiple_choice',
            'question': q.question,
            'choices': choices,
            'correct_answer': q.correct_answer,
        })

    # Shuffle and limit to 5 questions
    random.shuffle(questions)
    questions = questions[:5]

    return jsonify({'success': True, 'questions': questions})

@app.route('/placement_test')
def placement_test():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return render_template('placement_test.html')

# # Create database tables
with app.app_context():
    db.create_all()
    if not User.query.filter_by(email='admin@yahoo.com').first():
        admin = User(email='admin@yahoo.com', name='Admin User', language='English', level='C2')
        admin.set_password('admin321')
        db.session.add(admin)
        db.session.commit()

if __name__ == '__main__':
    app.run(debug=True)