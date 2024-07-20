# Import
from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_scss import Scss
import google.generativeai as genai
from google.api_core.exceptions import GoogleAPIError
from config import API_KEY



app = Flask(__name__)

import logging
from logging.handlers import RotatingFileHandler

# ... your Flask app setup ...

# Set up logging
handler = RotatingFileHandler('app.log', maxBytes=10000, backupCount=1)
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
app.logger.addHandler(handler)

# ... your routes ...


# Home Route
@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')


# # Generate Route
# @app.route('/generate', methods=['POST',"GET"])
# def generate():
#     if request.method == "POST":
#         try:
#             topic = request.form['topic']
#             language = request.form['language']
#             target = request.form['target']
#             level = request.form['level']

#             generated_content = generate_content(topic, language, target, level)
#             return jsonify({"content": generated_content, "success": True})
        
#         except Exception as e:
#             error_message = str(e)
#             return jsonify({"error": error_message, "success": False}), 500
#     else:
#         return render_template('generate.html')

# def generate_content(topic, language, target, level):
#     # Input validation
#     if not topic or not language or not target or not level:
#         raise ValueError("All fields are required.")

#     try:
#         # Gemini API Configuration
#         genai.configure(api_key=API_KEY) # Replace with your actual API key

#         # Model Selection
#         model = genai.GenerativeModel(model='gemini-pro')  # Or another suitable Gemini model

#         # Prompt Generation (You'll likely want to refine this further)
#         prompt = f"Write a document in {language} for {level} learners about {topic}, focusing on {target}."

#         # Generate Text
#         response = model.generate_text(
#             prompt=prompt,
#             temperature=0.7,  # Adjust temperature for creativity (0.0 to 1.0)
#             max_output_tokens=500,  # Adjust max output length as needed
#         )

#         # Error Handling for Gemini API Calls
#         if response.has_error:
#             raise Exception(f"Gemini API Error: {response.error}")

#         # Extract and Format Content
#         content = response.result

#         return content
#     except GoogleAPIError as e:
#         raise Exception(f"Gemini API Request Error: {e}")

@app.route('/generate', methods=['POST', 'GET'])
def generate():
    if request.method == "POST":
        try:
            topic = request.form['topic']
            language = request.form['language']
            target = request.form['target']
            level = request.form['level']

            generated_content = generate_content(topic, language, target, level)
            return jsonify({"content": generated_content, "success": True})

        except Exception as e:
            error_message = str(e)
            return jsonify({"error": error_message, "success": False}), 500

    else:
        return render_template('generate.html')  # Handle GET requests

def generate_content(topic, language, target, level):
    # Input validation (this looks good)
    if not topic or not language or not target or not level:
        raise ValueError("All fields are required.")

    try:
        # Gemini API Configuration (assuming API_KEY is defined elsewhere)
        genai.configure(api_key=API_KEY)
        app.logger.info(f"API Key Used: {API_KEY}")  
        app.logger.info(f"Parameter: {topic, language, target, level}")  

        # Model Selection
        model = genai.GenerativeModel('gemini-pro')

        # Prompt Generation (you can customize this further)
        prompt = f"Write a document in {language} for {level} learners about {topic}, focusing on {target}."

        # Generate Text (check if this call works correctly with Gemini)
        response = model.generate_text(
            prompt=prompt,
            temperature=0.7,
            max_output_tokens=500,
        )

        # Error Handling (good practice)
        if response.has_error:
            raise Exception(f"Gemini API Error: {response.error}")

        # Extract and Format Content
        content = response.result  # Ensure the Gemini API response structure matches this
        return content

    except GoogleAPIError as e:
        raise Exception(f"Gemini API Request Error: {e}")


# # Content Generation Function
# def generate_content(topic, language, target, level):
#     # Robust content generation logic (replace this placeholder)
#     # Example using dummy data:

#     # Input validation (optional)
#     if not topic or not language or not target or not level:
#         raise ValueError("All fields are required.")

#     content = f"""
#     <h1>{topic}</h1>
#     <p>This document is written in {language}, tailored for {level} learners, 
#        and focuses on the topic of {target}.</p>
    
#     <p>Add your generated content here based on the provided parameters.</p>
#     """

#     return content
# # Generate Route
# @app.route('/generate')
# def generate():
#     return render_template('generate.html')


# # Run the App
# if __name__ == "__main__":
#     app.run(debug=True)


# <a href="#generate" class="btn">Get Started</a>

# run this command
# 28:30 / 1:25:40
# flask --app app.py --debug run
# <link rel="stylesheet" href="{{ url_for('static', filename='styles.css') }}">
