import os
import logging
from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for, session
from flask import session
import google.generativeai as genai
from google.api_core.exceptions import GoogleAPIError
from config import API_KEY
from logging.handlers import RotatingFileHandler
import os
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.fonts import addMapping
import secrets
import tempfile
import re
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import datetime
from sqlalchemy.sql import func

app = Flask(__name__)
app.secret_key = "12345"

# Configure PostgreSQL database with explicit username
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://yechiel@localhost/languagex'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

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
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# Define UserPerformance model for tracking user progress
class UserPerformance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    concept = db.Column(db.String(100), nullable=False)
    success_rate = db.Column(db.Float, default=0.0)
    error_rate = db.Column(db.Float, default=0.0)
    
    user = db.relationship('User', backref=db.backref('performance', lazy=True))

# GroundTruth model
class GroundTruth(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    word = db.Column(db.String(100), nullable=False)
    pos = db.Column(db.String(50), nullable=False)  # part of speech
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
    answer = db.Column(db.String(100), nullable=False)  # Added answer field
    level = db.Column(db.String(10), nullable=False)
    generated_at = db.Column(db.DateTime, default=func.now())
    deleted_at = db.Column(db.DateTime, nullable=True)
    is_seen = db.Column(db.Boolean, default=False)
    for_user = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user_answer = db.Column(db.Text, nullable=True)
    is_correct = db.Column(db.Boolean, nullable=True)
    user_feedback = db.Column(db.Text, nullable=True)
    
    user = db.relationship('User', backref=db.backref('fill_blanks', lazy=True))

# ArrangeTheWord model
class ArrangeTheWord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.Text, nullable=False)
    correct_arrangement = db.Column(db.Text, nullable=False)  # Added correct answer
    level = db.Column(db.String(10), nullable=False)
    generated_at = db.Column(db.DateTime, default=func.now())
    deleted_at = db.Column(db.DateTime, nullable=True)
    is_seen = db.Column(db.Boolean, default=False)
    for_user = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user_answer = db.Column(db.Text, nullable=True)
    is_correct = db.Column(db.Boolean, nullable=True)
    user_feedback = db.Column(db.Text, nullable=True)
    
    user = db.relationship('User', backref=db.backref('arrange_words', lazy=True))

# MultipleChoice model
class MultipleChoice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.Text, nullable=False)
    choices = db.Column(db.Text, nullable=False)  # Store as JSON or serialized list
    correct_answer = db.Column(db.String(100), nullable=False)  # Added correct answer
    level = db.Column(db.String(10), nullable=False)
    generated_at = db.Column(db.DateTime, default=func.now())
    deleted_at = db.Column(db.DateTime, nullable=True)
    is_seen = db.Column(db.Boolean, default=False)
    for_user = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user_answer = db.Column(db.Text, nullable=True)
    is_correct = db.Column(db.Boolean, nullable=True)
    user_feedback = db.Column(db.Text, nullable=True)
    
    user = db.relationship('User', backref=db.backref('multiple_choices', lazy=True))

# Ensure the logs directory exists
if not os.path.exists('logs'):
    os.makedirs('logs')

# Set up logging
handler = RotatingFileHandler('logs/app.log', maxBytes=10000, backupCount=1)
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)

# Add the handler to Flask's logger
app.logger.addHandler(handler)
app.logger.setLevel(logging.INFO)

# Also log to console
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(console_formatter)
app.logger.addHandler(console_handler)

# Immediate log to check if logging is working
app.logger.info("Flask app is starting up")

# Gemini API Configuration
genai.configure(api_key=API_KEY)

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
        language = request.form.get('language', '')
        level = request.form.get('level', 'A1')
        
        # Check if user already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            return render_template('signup.html', error="Email already registered")
        
        # Create new user
        new_user = User(email=email, name=name, language=language, level=level)
        new_user.set_password(password)
        
        # Add and commit to database
        db.session.add(new_user)
        db.session.commit()
        
        session['logged_in'] = True
        session['user_id'] = new_user.id
        
        return redirect(url_for('generate'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')
    
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        # For development, keep hardcoded credentials
        if (email == 'test@test.com' and password == 'password') or (email == 'admin@yahoo.com' and password == 'admin321'):
            session['logged_in'] = True
            session['user_id'] = 0  # Special ID for hardcoded users
            return redirect(url_for('generate'))
        
        # Check database for user
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password):
            session['logged_in'] = True
            session['user_id'] = user.id
            return redirect(url_for('generate'))
            
        return render_template('login.html', error="Invalid credentials")

@app.route('/profile')
def profile():
    # Check if user is logged in
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    user_id = session.get('user_id')
    
    # If using hardcoded credentials (user_id = 0), show mock data
    if user_id == 0:
        user_data = {
            'name': 'John Doe',
            'level': 'A1',
            'language': 'Spanish',
            'study_time': '28',
            'streak': '15',
            'lessons_completed': '45',
            'average_score': '76',
            'performance': [
                {'concept': 'basic_greetings', 'success_rate': '0', 'error_rate': '100'},
                {'concept': 'irregular_verbs', 'success_rate': '75', 'error_rate': '25'},
                {'concept': 'past_tense', 'success_rate': '25', 'error_rate': '75'},
                {'concept': 'present_simple', 'success_rate': '44', 'error_rate': '56'}
            ]
        }
        return render_template('profile.html', user=user_data)
    
    # Fetch real user data from database
    user = User.query.get(user_id)
    if not user:
        return redirect(url_for('login'))
    
    # Format user data for template
    user_data = {
        'name': user.name,
        'level': user.level,
        'language': user.language,
        'study_time': str(user.study_time),
        'streak': str(user.streak),
        'lessons_completed': str(user.lessons_completed),
        'average_score': str(int(user.average_score)),
        'performance': []
    }
    
    # Get performance data
    performance = UserPerformance.query.filter_by(user_id=user_id).all()
    for perf in performance:
        user_data['performance'].append({
            'concept': perf.concept,
            'success_rate': str(int(perf.success_rate)),
            'error_rate': str(int(perf.error_rate))
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
            # Ensure all required fields are present
            required_fields = ['topic', 'language', 'target', 'level']
            if not all(field in request.form for field in required_fields):
                raise ValueError("Missing required fields in the form data")

            topic = request.form['topic']
            language = request.form['language']
            target = request.form['target']
            level = request.form['level']
            
            # Check if we're exporting or generating new content
            export_format = request.form.get('export_format')
            
            if export_format:
                # Use stored content for export
                generated_content = session.get('generated_content')
                if not generated_content:
                    return jsonify({"error": "No content to export. Please generate content first.", "success": False}), 400
                return export_content(generated_content, export_format)
            else:
                # Generate new content
                generated_content = generate_content(topic, language, target, level)
                
                # Convert Markdown to HTML
                html_content = markdown_to_html(generated_content)
                
                # Store the original Markdown content for potential export
                session['generated_content'] = generated_content
                
                return jsonify({"content": html_content, "success": True})
        
        except ValueError as ve:
            error_message = str(ve)
            app.logger.error(f"ValueError in generate route: {error_message}")
            return jsonify({"error": error_message, "success": False}), 400
        except Exception as e:
            error_message = str(e)
            app.logger.error(f"Error in generate route: {error_message}")
            return jsonify({"error": error_message, "success": False}), 500

    else:
        return jsonify({"error": "Method not allowed", "success": False}), 405

def generate_content(topic, language, target, level):
    if not all([topic, language, target, level]):
        raise ValueError("All fields are required.")
    
    try:
        app.logger.info(f"Parameters: topic={topic}, language={language}, target={target}, level={level}")
        
        # Model Selection
        model = genai.GenerativeModel('gemini-pro')
        Language = language
        Level = level
        Topic = topic
        Target = target
        # Prompt Generation
        prompt = f"""
        You are an {Language} language teacher creating a worksheet for {Level} {Language} learners.
        1. Generate 5 fill-in-the-blank sentences about {Topic} with a focus on {Target}. Include hint words in the context to help learners correctly use and conjugate the target word.
        Leave the blanks empty and provide the correct answers separately.
        Example format:
        Sentence: I ______ (to come back) home yesterday. 
 

        2. Give me 5 {Level} multiple-choice questions to test my understanding of {Target} vocabulary.


        3.  You are a {Level} {Language} language teacher creating a "find the mistake" activity.

        Instructions:
        1.  Write a natural-sounding sentence in {Language} about {Topic} that is grammatically correct.
        2. Make one small, subtle change to the sentence to introduce an error related to {Topic}.
        3. Present both versions of the sentence:

        Example:
        [First Sentence]
        [Second sentence]

        4. Invent 5 "Would You Rather" scenario in {Language} suitable for {Level} language learners.
        - The two options should require the use of different grammatical structures or vocabulary.
        - Focus on {Topic}.

        Example:
        매운 음식을 매일 먹겠어요, 아니면 단 음식을 매일 먹겠어요?
        (Would you rather eat spicy food every day or eat sweet food every day?)
        don't explain please

        5. Generate 5 {Level} sentences in {Language}, each paired with its translation in {Language}.
        The sentences should practice translating between English and {Language}.
        Ensure that the sentences cover various aspects of the {Topic} with the focus on {Target}.
        Include a mix of simple, compound, and complex sentences.

        Provide the correct answer for each list at the very bottom of the last prompt. Please write "Answers will vary" if it true
        """
        
        app.logger.info(f"Sending prompt to Gemini API: {prompt}")
        
        # Generate Text
        response = model.generate_content(prompt)
        
        # Log the raw response
        app.logger.info(f"Raw API response: {response}")
        
        # Error Handling
        if response.parts:
            content = response.parts[0].text
            app.logger.info(f"Generated content: {content}")
            return content
        else:
            raise Exception("No content generated")
    
    except GoogleAPIError as e:
        app.logger.error(f"Gemini API Request Error: {e}")
        raise Exception(f"Gemini API Request Error: {e}")

def export_content(content, format):
    if format == 'pdf':
        return export_to_pdf(content)

    else:
        raise ValueError("Unsupported export format")

# Register fonts
pdfmetrics.registerFont(TTFont('NanumGothic', 'NanumGothic-Regular.ttf'))
pdfmetrics.registerFont(TTFont('NanumGothic-Bold', 'NanumGothic-Bold.ttf'))

# Add font mappings
addMapping('NanumGothic', 0, 0, 'NanumGothic')  # normal
addMapping('NanumGothic', 1, 0, 'NanumGothic-Bold')  # bold

def export_to_pdf(content):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    
    # Create custom styles with the Korean-compatible font
    styles.add(ParagraphStyle(name='KoreanNormal',
                              fontName='NanumGothic',
                              fontSize=12,
                              leading=14))
    styles.add(ParagraphStyle(name='KoreanBold',
                              fontName='NanumGothic-Bold',
                              fontSize=12,
                              leading=14))
    
    flowables = []

    # Add logo to the first page
    logo_path = os.path.join(app.static_folder, 'images', 'logo.png')
    if os.path.exists(logo_path):
        logo = Image(logo_path, width=100, height=100)  # Adjust size as needed
        logo.hAlign = 'CENTER'  # Center align the logo
        flowables.append(logo)
        flowables.append(Spacer(1, 20))  # Add some space after the logo
    else:
        app.logger.warning(f"Logo file not found at {logo_path}")

    paragraphs = content.split('\n\n')  # Split content into paragraphs
    for paragraph in paragraphs:
        lines = paragraph.split('\n')
        for line in lines:
            if line.startswith('**') and line.endswith('**'):
                para = Paragraph(line.strip('*'), styles['KoreanBold'])
            else:
                para = Paragraph(line, styles['KoreanNormal'])
            flowables.append(para)
        flowables.append(Spacer(1, 12))  # Add space between paragraphs

    doc.build(flowables)
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name='generated_content.pdf', mimetype='application/pdf')

def markdown_to_html(text):
    # Convert **bold** to <strong>bold</strong>
    text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)
    
    # Convert newlines to <br> tags
    text = text.replace('\n', '<br>')
    
    return text
                     
# Create database tables if they don't exist
with app.app_context():
    db.create_all()
    
    # Add sample data for development if needed
    if not User.query.filter_by(email='admin@yahoo.com').first():
        admin = User(email='admin@yahoo.com', name='Admin User', language='English', level='C2')
        admin.set_password('admin321')
        db.session.add(admin)
        db.session.commit()

if __name__ == '__main__':
    app.run(debug=True)


# python -m venv venv
# source venv/bin/activate

# brew services stop postgresql
# brew services start postgresql
# brew services list | grep postgresql
# brew services restart postgresql
# psql -d languagex
# psql -l
# pg_dump languagex > languagex_backup.sql  BACKUP
# psql -d languagex -f languagex_backup.sql  RESTORE FROM BACKUP