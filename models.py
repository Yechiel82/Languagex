from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.sql import func

db = SQLAlchemy()

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

def init_db(app):
    """Initialize the database, creating tables and admin user if needed"""
    with app.app_context():
        db.create_all()
        
        # Create admin user if it doesn't exist
        from werkzeug.security import generate_password_hash
        admin_email = 'admin@yahoo.com'
        if not User.query.filter_by(email=admin_email).first():
            admin = User(
                email=admin_email, 
                name='Admin User', 
                language='English', 
                level='C2',
                password_hash=generate_password_hash('admin321')
            )
            db.session.add(admin)
            db.session.commit()