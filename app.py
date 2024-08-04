# from flask import Flask, render_template, request, jsonify
# import google.generativeai as genai
# from google.api_core.exceptions import GoogleAPIError
# from config import API_KEY
# import logging
# from logging.handlers import RotatingFileHandler
# import os
from flask import Flask, render_template, request, jsonify, send_file
import google.generativeai as genai
from google.api_core.exceptions import GoogleAPIError
from config import API_KEY
import logging
from logging.handlers import RotatingFileHandler
import os
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from docx import Document
import tempfile

app = Flask(__name__)

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

# # Gemini API Configuration
# genai.configure(api_key=API_KEY)

# @app.route('/', methods=['GET'])
# def index():
#     app.logger.info("Index route accessed")
#     return render_template('index.html')

# @app.route('/generate', methods=['POST', 'GET'])
# def generate():
#     if request.method == "POST":
#         try:
#             topic = request.form['topic']
#             language = request.form['language']
#             target = request.form['target']
#             level = request.form['level']
            
#             generated_content = generate_content(topic, language, target, level)
#             app.logger.info(f"Generated content: {generated_content}")
#             return jsonify({"content": generated_content, "success": True})
        
#         except Exception as e:
#             error_message = str(e)
#             app.logger.error(f"Error in generate route: {error_message}")
#             return jsonify({"error": error_message, "success": False}), 500
#     else:
#         return render_template('generate.html')

genai.configure(api_key=API_KEY)

@app.route('/', methods=['GET'])
def index():
    app.logger.info("Index route accessed")
    return render_template('index.html')

@app.route('/generate', methods=['POST', 'GET'])
def generate():
    if request.method == "POST":
        try:
            topic = request.form['topic']
            language = request.form['language']
            target = request.form['target']
            level = request.form['level']
            
            generated_content = generate_content(topic, language, target, level)
            app.logger.info(f"Generated content: {generated_content}")
            
            # Check if export is requested
            export_format = request.form.get('export_format')
            if export_format:
                return export_content(generated_content, export_format)
            
            return jsonify({"content": generated_content, "success": True})
        
        except Exception as e:
            error_message = str(e)
            app.logger.error(f"Error in generate route: {error_message}")
            return jsonify({"error": error_message, "success": False}), 500
    else:
        return render_template('generate.html')

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
    elif format == 'docx':
        return export_to_docx(content)
    elif format == 'gdoc':
        return export_to_gdoc(content)
    else:
        raise ValueError("Unsupported export format")

def export_to_pdf(content):
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    textobject = p.beginText()
    textobject.setTextOrigin(50, 750)
    for line in content.split('\n'):
        textobject.textLine(line)
    p.drawText(textobject)
    p.showPage()
    p.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name='generated_content.pdf', mimetype='application/pdf')

def export_to_docx(content):
    doc = Document()
    doc.add_paragraph(content)
    with tempfile.NamedTemporaryFile(delete=False, suffix='.docx') as tmp:
        doc.save(tmp.name)
        tmp.seek(0)
        return send_file(tmp.name, as_attachment=True, download_name='generated_content.docx', mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document')

def export_to_gdoc(content):
    # Note: This function doesn't actually create a Google Doc.
    # It creates a text file that can be easily imported into Google Docs.
    buffer = BytesIO()
    buffer.write(content.encode())
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name='generated_content.txt', mimetype='text/plain')

if __name__ == '__main__':
    app.run(debug=True)

    
# from flask import Flask, render_template, request, jsonify
# import google.generativeai as genai
# from google.api_core.exceptions import GoogleAPIError
# from config import API_KEY
# import logging
# from logging.handlers import RotatingFileHandler
# import os

# app = Flask(__name__)

# # Ensure the logs directory exists
# if not os.path.exists('logs'):
#     os.makedirs('logs')

# # Set up logging
# handler = RotatingFileHandler('logs/app.log', maxBytes=10000, backupCount=1)
# handler.setLevel(logging.INFO)
# formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
# handler.setFormatter(formatter)

# # Add the handler to Flask's logger
# app.logger.addHandler(handler)
# app.logger.setLevel(logging.INFO)

# # Also log to console
# console_handler = logging.StreamHandler()
# console_handler.setLevel(logging.INFO)
# console_formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
# console_handler.setFormatter(console_formatter)
# app.logger.addHandler(console_handler)

# # Immediate log to check if logging is working
# app.logger.info("Flask app is starting up")

# # Gemini API Configuration
# genai.configure(api_key=API_KEY)

# @app.route('/', methods=['GET'])
# def index():
#     app.logger.info("Index route accessed")
#     return render_template('index.html')

# @app.route('/generate', methods=['POST', 'GET'])
# def generate():
#     if request.method == "POST":
#         app.logger.info("Generate route accessed with POST method")
#         try:
#             topic = request.form['topic']
#             language = request.form['language']
#             target = request.form['target']
#             level = request.form['level']
            
#             generated_content = generate_content(topic, language, target, level)
#             return jsonify({"content": generated_content, "success": True})
        
#         except Exception as e:
#             error_message = str(e)
#             app.logger.error(f"Error in generate route: {error_message}")
#             return jsonify({"error": error_message, "success": False}), 500
#     else:
#         app.logger.info("Generate route accessed with GET method")
#         return render_template('generate.html')

# def generate_content(topic, language, target, level):
#     if not all([topic, language, target, level]):
#         raise ValueError("All fields are required.")
    
#     try:
#         app.logger.info(f"Parameters: topic={topic}, language={language}, target={target}, level={level}")
        
#         # Model Selection
#         model = genai.GenerativeModel('gemini-pro')
        
#         # Prompt Generation
#         prompt = f"Write a document in {language} for {level} learners about {topic}, focusing on {target}."
        
#         app.logger.info(f"Sending prompt to Gemini API: {prompt}")
#         app.logger.info("Sending request to Gemini API...")
        
#         # Generate Text
#         response = model.generate_content(prompt)
#         app.logger.info("Received response from Gemini API")
        
#         # Log the raw response
#         app.logger.info(f"Raw API response: {response}")
        
#         # Error Handling
#         if response.parts:
#             content = response.parts[0].text
#             app.logger.info(f"Generated content: {content[:100]}...")  # Log the first 100 characters
#             return content
#         else:
#             raise Exception("No content generated")
    
#     except GoogleAPIError as e:
#         app.logger.error(f"Gemini API Request Error: {e}")
#         raise Exception(f"Gemini API Request Error: {e}")

# if __name__ == '__main__':
#     app.run(debug=True)
# # from flask import Flask, render_template, request, jsonify
# # import google.generativeai as genai
# # from google.api_core.exceptions import GoogleAPIError
# # from config import API_KEY
# # import logging
# # from logging.handlers import RotatingFileHandler

# # app = Flask(__name__)

# # # Set up logging
# # logger = logging.getLogger(__name__)
# # logger.setLevel(logging.INFO)

# # # File handler
# # file_handler = RotatingFileHandler('app.log', maxBytes=10000, backupCount=1)
# # file_handler.setLevel(logging.INFO)
# # file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
# # file_handler.setFormatter(file_formatter)

# # # Console handler
# # console_handler = logging.StreamHandler()
# # console_handler.setLevel(logging.INFO)
# # console_formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
# # console_handler.setFormatter(console_formatter)

# # # Add both handlers to the logger
# # logger.addHandler(file_handler)
# # logger.addHandler(console_handler)

# # # Gemini API Configuration
# # genai.configure(api_key=API_KEY)

# # @app.route('/', methods=['GET'])
# # def index():
# #     return render_template('index.html')

# # @app.route('/generate', methods=['POST', 'GET'])
# # def generate():
# #     if request.method == "POST":
# #         try:
# #             topic = request.form['topic']
# #             language = request.form['language']
# #             target = request.form['target']
# #             level = request.form['level']
            
# #             generated_content = generate_content(topic, language, target, level)
# #             return jsonify({"content": generated_content, "success": True})
        
# #         except Exception as e:
# #             error_message = str(e)
# #             logger.error(f"Error in generate route: {error_message}")
# #             return jsonify({"error": error_message, "success": False}), 500
# #     else:
# #         return render_template('generate.html')

# # def generate_content(topic, language, target, level):
# #     if not all([topic, language, target, level]):
# #         raise ValueError("All fields are required.")
    
# #     try:
# #         logger.info(f"Parameters: topic={topic}, language={language}, target={target}, level={level}")
        
# #         # Model Selection
# #         model = genai.GenerativeModel('gemini-pro')
        
# #         # Prompt Generation
# #         prompt = f"Write a document in {language} for {level} learners about {topic}, focusing on {target}."
        
# #         logger.info(f"Sending prompt to Gemini API: {prompt}")
# #         logger.info("Sending request to Gemini API...")
        
# #         # Generate Text
# #         response = model.generate_content(prompt)
# #         logger.info("Received response from Gemini API")
        
# #         # Log the raw response
# #         logger.info(f"Raw API response: {response}")
        
# #         # Error Handling
# #         if response.parts:
# #             content = response.parts[0].text
# #             logger.info(f"Generated content: {content[:100]}...")  # Log the first 100 characters
# #             return content
# #         else:
# #             raise Exception("No content generated")
    
# #     except GoogleAPIError as e:
# #         logger.error(f"Gemini API Request Error: {e}")
# #         raise Exception(f"Gemini API Request Error: {e}")

# # if __name__ == '__main__':
# #     app.run(debug=True)
# # # from flask import Flask, render_template, request, jsonify
# # # from flask_sqlalchemy import SQLAlchemy
# # # from flask_scss import Scss
# # # import google.generativeai as genai
# # # from google.api_core.exceptions import GoogleAPIError
# # # from config import API_KEY
# # # import logging
# # # from logging.handlers import RotatingFileHandler

# # # app = Flask(__name__)

# # # # Set up logging
# # # handler = RotatingFileHandler('app.log', maxBytes=10000, backupCount=1)
# # # handler.setLevel(logging.INFO)
# # # formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
# # # handler.setFormatter(formatter)
# # # app.logger.addHandler(handler)

# # # # Gemini API Configuration
# # # genai.configure(api_key=API_KEY)

# # # @app.route('/', methods=['GET'])
# # # def index():
# # #     return render_template('index.html')

# # # @app.route('/generate', methods=['POST', 'GET'])
# # # def generate():
# # #     if request.method == "POST":
# # #         try:
# # #             topic = request.form['topic']
# # #             language = request.form['language']
# # #             target = request.form['target']
# # #             level = request.form['level']
            
# # #             generated_content = generate_content(topic, language, target, level)
# # #             return jsonify({"content": generated_content, "success": True})
        
# # #         except Exception as e:
# # #             error_message = str(e)
# # #             app.logger.error(f"Error in generate route: {error_message}")
# # #             return jsonify({"error": error_message, "success": False}), 500
# # #     else:
# # #         return render_template('generate.html')

# # # def generate_content(topic, language, target, level):
# # #     if not all([topic, language, target, level]):
# # #         raise ValueError("All fields are required.")
    
# # #     try:
# # #         app.logger.info(f"Parameters: topic={topic}, language={language}, target={target}, level={level}")
        
# # #         # Model Selection
# # #         model = genai.GenerativeModel('gemini-pro')
        
# # #         # Prompt Generation
# # #         prompt = f"Write a document in {language} for {level} learners about {topic}, focusing on {target}."
        
# # #         # Generate Text
# # #         response = model.generate_content(prompt)
        
# # #         # Error Handling
# # #         if response.parts:
# # #             content = response.parts[0].text
# # #             return content
# # #         else:
# # #             raise Exception("No content generated")
    
# # #     except GoogleAPIError as e:
# # #         app.logger.error(f"Gemini API Request Error: {e}")
# # #         raise Exception(f"Gemini API Request Error: {e}")

# # # if __name__ == '__main__':
# # #     app.run(debug=True)
# # # # # Import
# # # # from flask import Flask, render_template, request, redirect, url_for, jsonify
# # # # from flask_sqlalchemy import SQLAlchemy
# # # # from flask_scss import Scss
# # # # import google.generativeai as genai
# # # # from google.api_core.exceptions import GoogleAPIError
# # # # from config import API_KEY



# # # # app = Flask(__name__)

# # # # import logging
# # # # from logging.handlers import RotatingFileHandler

# # # # # ... your Flask app setup ...

# # # # # Set up logging
# # # # handler = RotatingFileHandler('app.log', maxBytes=10000, backupCount=1)
# # # # handler.setLevel(logging.INFO)
# # # # formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
# # # # handler.setFormatter(formatter)
# # # # app.logger.addHandler(handler)

# # # # # ... your routes ...


# # # # # Home Route
# # # # @app.route('/', methods=['GET'])
# # # # def index():
# # # #     return render_template('index.html')

# # # # @app.route('/generate', methods=['POST', 'GET'])
# # # # def generate():
# # # #     if request.method == "POST":
# # # #         try:
# # # #             topic = request.form['topic']
# # # #             language = request.form['language']
# # # #             target = request.form['target']
# # # #             level = request.form['level']

# # # #             generated_content = generate_content(topic, language, target, level)
# # # #             return jsonify({"content": generated_content, "success": True})

# # # #         except Exception as e:
# # # #             error_message = str(e)
# # # #             return jsonify({"error": error_message, "success": False}), 500

# # # #     else:
# # # #         return render_template('generate.html')  # Handle GET requests

# # # # def generate_content(topic, language, target, level):
# # # #     # Input validation (this looks good)
# # # #     if not topic or not language or not target or not level:
# # # #         raise ValueError("All fields are required.")

# # # #     try:
# # # #         # Gemini API Configuration (assuming API_KEY is defined elsewhere)
# # # #         genai.configure(api_key=API_KEY)
# # # #         app.logger.info(f"API Key Used: {API_KEY}")  
# # # #         app.logger.info(f"Parameter: {topic, language, target, level}")  

# # # #         # Model Selection
# # # #         model = genai.GenerativeModel('gemini-pro')

# # # #         # Prompt Generation (you can customize this further)
# # # #         prompt = f"Write a document in {language} for {level} learners about {topic}, focusing on {target}."

# # # #         # Generate Text (check if this call works correctly with Gemini)
# # # #         response = model.generate_text(
# # # #             prompt=prompt,
# # # #             temperature=0.7,
# # # #             max_output_tokens=500,
# # # #         )

# # # #         # Error Handling (good practice)
# # # #         if response.has_error:
# # # #             raise Exception(f"Gemini API Error: {response.error}")

# # # #         # Extract and Format Content
# # # #         content = response.result  # Ensure the Gemini API response structure matches this
# # # #         return content

# # # #     except GoogleAPIError as e:
# # # #         raise Exception(f"Gemini API Request Error: {e}")

# # # # # # Generate Route
# # # # # @app.route('/generate', methods=['POST',"GET"])
# # # # # def generate():
# # # # #     if request.method == "POST":
# # # # #         try:
# # # # #             topic = request.form['topic']
# # # # #             language = request.form['language']
# # # # #             target = request.form['target']
# # # # #             level = request.form['level']

# # # # #             generated_content = generate_content(topic, language, target, level)
# # # # #             return jsonify({"content": generated_content, "success": True})
        
# # # # #         except Exception as e:
# # # # #             error_message = str(e)
# # # # #             return jsonify({"error": error_message, "success": False}), 500
# # # # #     else:
# # # # #         return render_template('generate.html')

# # # # # def generate_content(topic, language, target, level):
# # # # #     # Input validation
# # # # #     if not topic or not language or not target or not level:
# # # # #         raise ValueError("All fields are required.")

# # # # #     try:
# # # # #         # Gemini API Configuration
# # # # #         genai.configure(api_key=API_KEY) # Replace with your actual API key

# # # # #         # Model Selection
# # # # #         model = genai.GenerativeModel(model='gemini-pro')  # Or another suitable Gemini model

# # # # #         # Prompt Generation (You'll likely want to refine this further)
# # # # #         prompt = f"Write a document in {language} for {level} learners about {topic}, focusing on {target}."

# # # # #         # Generate Text
# # # # #         response = model.generate_text(
# # # # #             prompt=prompt,
# # # # #             temperature=0.7,  # Adjust temperature for creativity (0.0 to 1.0)
# # # # #             max_output_tokens=500,  # Adjust max output length as needed
# # # # #         )

# # # # #         # Error Handling for Gemini API Calls
# # # # #         if response.has_error:
# # # # #             raise Exception(f"Gemini API Error: {response.error}")

# # # # #         # Extract and Format Content
# # # # #         content = response.result

# # # # #         return content
# # # # #     except GoogleAPIError as e:
# # # # #         raise Exception(f"Gemini API Request Error: {e}")

# # # # # # Content Generation Function
# # # # # def generate_content(topic, language, target, level):
# # # # #     # Robust content generation logic (replace this placeholder)
# # # # #     # Example using dummy data:

# # # # #     # Input validation (optional)
# # # # #     if not topic or not language or not target or not level:
# # # # #         raise ValueError("All fields are required.")

# # # # #     content = f"""
# # # # #     <h1>{topic}</h1>
# # # # #     <p>This document is written in {language}, tailored for {level} learners, 
# # # # #        and focuses on the topic of {target}.</p>
    
# # # # #     <p>Add your generated content here based on the provided parameters.</p>
# # # # #     """

# # # # #     return content
# # # # # # Generate Route
# # # # # @app.route('/generate')
# # # # # def generate():
# # # # #     return render_template('generate.html')


# # # # # # Run the App
# # # # # if __name__ == "__main__":
# # # # #     app.run(debug=True)


# # # # # <a href="#generate" class="btn">Get Started</a>

# # # # # run this command
# # # # # 28:30 / 1:25:40
# # # # # flask --app app.py --debug run
# # # # # <link rel="stylesheet" href="{{ url_for('static', filename='styles.css') }}">
