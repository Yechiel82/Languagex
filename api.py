from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional, Any
import uvicorn
import time
from datetime import timedelta

# Import necessary components from llm.py
from unsloth import FastLanguageModel
import torch
import re
import joblib
import numpy as np
from sentence_transformers import SentenceTransformer
from huggingface_hub import snapshot_download
import random

# Initialize FastAPI app
app = FastAPI(
    title="LanguageX API",
    description="API for CEFR-based sentence generation and language evaluation",
    version="1.0.0"
)

# Models and global variables
model = None
tokenizer = None
eval_model = None
embedder = None
device = None

# Models configuration
levels = ["A1", "A2", "B1", "B2", "C1", "C2"]
cefr_to_score = {'A1': 1, 'A2': 2, 'B1': 3, 'B2': 4, 'C1': 5, 'C2': 6}

# Pydantic models for request/response
class SentenceRequest(BaseModel):
    level: str
    topic: str = "Food"
    num_sentences: int = 1

class SentimentRequest(BaseModel):
    text: str

class SentenceResponse(BaseModel):
    formatted: str
    fill_in_blank: str
    arrange_question: str
    multiple_choice: Dict[str, Any]
    verb: str
    sentence: str

class GenerationResponse(BaseModel):
    sentences: List[SentenceResponse]
    stats: Dict[str, Any]

class SentimentResponse(BaseModel):
    text: str
    level: str
    score: int


# Import prompt templates and functions from llm.py
prompt_templates = {
    "A1": """Generate ONE example sentence for CEFR level A1 in this EXACT format with the topic of '{topic}':
"The word is: '[verb]' and it is a verb. Example sentence: '[sentence]'."

Use basic verbs (go, eat, sleep) in simple present tense.
Example: "The word is: 'eat' and it is a verb. Example sentence: 'I eat bread.'"

Rules:
- Must use this exact format also with the topic of '{topic}'
- Sentence must have 3+ words
- Only include the formatted sentence""",

    "A2": """Generate ONE example sentence for CEFR level A2 in this EXACT format  with the topic of '{topic}':
"The word is: '[verb]' and it is a verb. Example sentence: '[sentence]'."

Use common verbs (understand, want, like) in simple tenses.
Example: "The word is: 'understand' and it is a verb. Example sentence: 'I understand English.'"

Rules:
- Must use this exact format also with the topic of '{topic}'
- Sentence must have 3+ words
- Only include the formatted sentence""",

    "B1": """Generate ONE example sentence for CEFR level B1 in this EXACT format  with the topic of '{topic}':
"The word is: '[verb]' and it is a verb. Example sentence: '[sentence]'."

Use everyday verbs (explain, decide, forget) in past/future tenses.
Example: "The word is: 'decide' and it is a verb. Example sentence: 'We decided to leave.'"

Rules:
- Must use this exact format also with the topic of '{topic}'
- Sentence must have 3+ words
- Only include the formatted sentence""",

    "B2": """Generate ONE example sentence for CEFR level B2 in this EXACT format  with the topic of '{topic}':
"The word is: '[verb]' and it is a verb. Example sentence: '[sentence]'."

Use more complex verbs (recognize, develop, influence).
Example: "The word is: 'recognize' and it is a verb. Example sentence: 'I recognized her immediately.'"

Rules:
- Must use this exact format also with the topic of '{topic}'
- Sentence must have 3+ words
- Only include the formatted sentence""",

    "C1": """Generate ONE example sentence for CEFR level C1 in this EXACT format  with the topic of '{topic}':
"The word is: '[verb]' and it is a verb. Example sentence: '[sentence]'."

Use advanced verbs (speculate, negotiate, comprehend).
Example: "The word is: 'speculate' and it is a verb. Example sentence: 'Experts speculate about market trends.'"

Rules:
- Must use this exact format also with the topic of '{topic}'
- Sentence must have 3+ words
- Only include the formatted sentence""",

    "C2": """Generate ONE example sentence for CEFR level C2 in this EXACT format  with the topic of '{topic}':
"The word is: '[verb]' and it is a verb. Example sentence: '[sentence]'."

Use sophisticated verbs (scrutinize, ameliorate, reciprocate).
Example: "The word is: 'scrutinize' and it is a verb. Example sentence: 'Researchers scrutinize the findings.'"

Rules:
- Must use this exact format also with the topic of '{topic}'
- Sentence must have 3+ words
- Only include the formatted sentence"""
}

# Helper functions from llm.py
def predict_sentiment(text):
    embedding = embedder.encode([text])
    probs = eval_model.predict_proba(embedding)[0]
    prediction = np.argmax(probs) + 1
    return max(1, min(6, int(prediction)))

def create_arrange_question(sentence, verb):
    clean_sentence = re.sub(r'[^\w\s]', '', sentence)
    words = [w for w in clean_sentence.split() if w]
    
    verb_form = None
    for word in words:
        if verb.lower() in word.lower():
            verb_form = word
            break
    
    if not verb_form:
        verb_form = verb
    
    words_to_shuffle = [w for w in words if w.lower() != verb_form.lower()]
    
    if len(words_to_shuffle) < 2:
        return None
    
    np.random.shuffle(words_to_shuffle)
    
    insert_pos = np.random.randint(1, len(words_to_shuffle))
    words_to_shuffle.insert(insert_pos, verb_form)
    
    return " / ".join(words_to_shuffle) + " (Arrange the words)"

def create_fill_in_blank(sentence, verb):
    pattern = rf"(\b{re.escape(verb)}[a-z]*\b)"
    
    match = re.search(pattern, sentence, re.IGNORECASE)
    if not match:
        return None
    
    actual_verb = match.group(1)
    
    if actual_verb[0].isupper():
        blank = f"__({verb.lower()})"
        blank = blank[0].upper() + blank[1:]
    else:
        blank = f"__({verb})"
    
    question = sentence[:match.start()] + blank + sentence[match.end():]
    
    return question

def generate_contextual_distractors(target_verb, sentence, num_distractors=3):
    prompt = f"""Generate {num_distractors} incorrect verb options for fill-in-the-blank questions.
Rules for good distractors:
        blank = blank[0].upper() + blank[1:]
    else:
        blank = f"__({verb})"

    # Replace only the first occurrence
    question = sentence[:match.start()] + blank + sentence[match.end():]

    return question

# This is the function I accidentally removed - adding it back
def generate_distractors(target_verb, sentence, num_distractors=3):
    """
    Generate simple distractors in case the contextual distractor generation fails
    """
    # Basic word lists by difficulty level
    basic_verbs = ["go", "eat", "walk", "run", "see", "like", "have", "do", "say", "get"]
    medium_verbs = ["speak", "think", "know", "make", "find", "take", "come", "put", "read", "work"]
    advanced_verbs = ["consider", "explain", "develop", "provide", "require", "suggest", "achieve", "maintain"]
    
    # Create distractors pool based on verb complexity
    if len(target_verb) <= 4:  # Simple verbs tend to be shorter
        pool = medium_verbs + advanced_verbs
    elif len(target_verb) <= 6:
        pool = basic_verbs + advanced_verbs
    else:
        pool = basic_verbs + medium_verbs
    
    # Filter out verbs too similar to target
    distractors = []
    for verb in random.sample(pool, min(num_distractors*2, len(pool))):
        if verb != target_verb and abs(len(verb) - len(target_verb)) < 4:
            distractors.append(verb)
            if len(distractors) >= num_distractors:
                break
    
    # If we don't have enough, add some simple defaults
    while len(distractors) < num_distractors:
        default_verbs = ["use", "try", "feel", "hear", "see", "keep"]
        for verb in default_verbs:
            if verb not in distractors and verb != target_verb:
                distractors.append(verb)
                if len(distractors) >= num_distractors:
                    break
    
    return distractors[:num_distractors]

def generate_contextual_distractors(target_verb, sentence, num_distractors=3):
    prompt = f"""Generate {num_distractors} incorrect verb options for fill-in-the-blank questions.
Rules for good distractors:
1. Must be grammatically correct in the sentence
2. Must create a clearly incorrect (but somewhat related) meaning
3. Should be at the same CEFR level as the original verb
4. Should not be synonyms or alternative correct answers

BAD EXAMPLE (too plausible):
Verb: "eat" | Sentence: "I ____ bread every morning."
Distractors: toast, bake, cook  # These could all be correct!

GOOD EXAMPLES:

Example 1:
Original verb: "eat"
Sentence: "I ____ bread every morning."
Good distractors: drive, sing, wear  # Clearly wrong but grammatically correct

Example 2:
Original verb: "understand"
Sentence: "She ____ the instructions quickly."
Good distractors: ate, slept, drove  # Physical verbs don't fit cognitive context

Example 3:
Original verb: "speculate"
Sentence: "Experts ____ about market trends."
Good distractors: swim, dance, sleep  # Clearly inappropriate for experts/markets

Now generate {num_distractors} CLEARLY INCORRECT but grammatically valid distractors for:
Original verb: "{target_verb}"
Sentence: "{sentence}"

Return ONLY the incorrect verbs as a comma-separated list:"""

    inputs = tokenizer(prompt, return_tensors="pt", padding=True).to(device)
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=50,
            do_sample=True,
            temperature=0.7,
            top_k=50,
            pad_token_id=tokenizer.pad_token_id
        )
    response = tokenizer.decode(outputs[0][inputs['input_ids'].shape[1]:], skip_special_tokens=True).strip()

    distractors = []
    for v in response.split(","):
        v = v.strip().lower()
        v = re.sub(r"[^a-zA-Z].*$", "", v)
        v = re.sub(r"[^a-zA-Z]", "", v)
        if v and v != target_verb.lower() and len(v) > 2:
            distractors.append(v)

    return list(set(distractors))[:num_distractors]

def create_mc_question(sentence, correct_verb, incorrect_verbs):
    blank_sentence = create_fill_in_blank(sentence, correct_verb)
    options = incorrect_verbs + [correct_verb]
    random.shuffle(options)

    cleaned_options = []
    for opt in options:
        opt = re.sub(r"[^a-zA-Z]", "", opt.lower()).strip()
        if opt:
            cleaned_options.append(opt)

    return {
        "question_text": blank_sentence,
        "options": cleaned_options,
        "correct_answer": correct_verb.lower()
    }

def extract_formatted_sentence(text, level):
    text = text.strip().replace('\n', ' ')
    
    pattern = r"The word is: ['\"]([^'\"]+)['\"] and it is a verb\. Example sentence: ['\"]([^'\"]+)['\"]"
    match = re.search(pattern, text)
    if not match:
        return None

    verb, sentence = match.group(1), match.group(2)

    if len(sentence.split()) < 3 or not sentence.endswith(('.', '!', '?')):
        return None

    fill_in_blank = create_fill_in_blank(sentence, verb)
    arrange_question = create_arrange_question(sentence, verb)

    if not fill_in_blank or not arrange_question:
        return None

    # Generate multiple choice options - now using both functions
    mc_options = generate_contextual_distractors(verb, sentence) or generate_distractors(verb, sentence)

    return {
        "formatted": f"The word is: '{verb}' and it is a verb. Example sentence: '{sentence}'",
        "fill_in_blank": fill_in_blank,
        "arrange_question": arrange_question,
        "multiple_choice": {
            "correct": verb,
            "incorrect": mc_options,
            "question": create_mc_question(sentence, verb, mc_options)
        },
        "verb": verb,
        "sentence": sentence
    }

def generate_sentence(level, topic="Food"):
    if level not in levels:
        raise ValueError(f"Invalid level: {level}. Must be one of {levels}")
    
    target_score = cefr_to_score[level]
    
    # Format the prompt with the topic
    prompt = prompt_templates[level].format(topic=topic)
    inputs = tokenizer(prompt, return_tensors="pt", padding=True).to(device)

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=150,
            do_sample=True,
            temperature=0.7,
            top_k=50,
            top_p=0.9,
            pad_token_id=tokenizer.pad_token_id
        )

    generated_text = tokenizer.decode(outputs[0][inputs['input_ids'].shape[1]:], skip_special_tokens=True).strip()
    
    # Process and validate
    extracted_data = extract_formatted_sentence(generated_text, level)
    if not extracted_data:
        return None

    # Evaluate
    predicted_score = predict_sentiment(extracted_data["sentence"])
    is_accepted = abs(predicted_score - target_score) <= 1

    if is_accepted:
        return extracted_data
    return None

# API endpoints
@app.on_event("startup")
async def startup_event():
    global model, tokenizer, eval_model, embedder, device
    
    print("Loading evaluator model...")
    eval_model_path = snapshot_download(repo_id="Mr-FineTuner/Eval_03_dup")
    eval_model = joblib.load(f'{eval_model_path}/text_classification_model.joblib')
    embedder = SentenceTransformer('all-mpnet-base-v2')
    
    print("\nLoading generator model...")
    gen_model_path = snapshot_download(repo_id="Mr-FineTuner/fullcomplete-01")
    model, tokenizer = FastLanguageModel.from_pretrained("Mr-FineTuner/fullcomplete-01", load_in_4bit=True)
    model = FastLanguageModel.for_inference(model)
    
    # Configure tokenizer
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    
    device = next(model.parameters()).device
    print("Models loaded successfully")

@app.get("/")
async def root():
    return {"message": "Welcome to LanguageX API", "version": "1.0.0"}

@app.post("/evaluate-text", response_model=SentimentResponse)
async def evaluate_text(request: SentimentRequest):
    """Evaluate the CEFR level of a text"""
    if not request.text:
        raise HTTPException(status_code=400, detail="Text cannot be empty")
    
    score = predict_sentiment(request.text)
    level = levels[score-1] if 1 <= score <= 6 else "Unknown"
    
    return {
        "text": request.text,
        "level": level,
        "score": score
    }

@app.post("/generate-sentences", response_model=GenerationResponse)
async def generate_sentences(request: SentenceRequest):
    """Generate sentences for a specific CEFR level and topic"""
    if request.level not in levels:
        raise HTTPException(status_code=400, detail=f"Invalid level: {request.level}. Must be one of {levels}")
    
    if request.num_sentences < 1 or request.num_sentences > 10:
        raise HTTPException(status_code=400, detail="Number of sentences must be between 1 and 10")
    
    # Track statistics
    start_time = time.time()
    valid_sentences = []
    generation_stats = {
        'total_generated': 0,
        'accepted': 0,
        'rejected': 0,
        'time_elapsed': 0
    }
    
    while len(valid_sentences) < request.num_sentences:
        generation_stats['total_generated'] += 1
        
        sentence_data = generate_sentence(request.level, request.topic)
        
        if sentence_data:
            valid_sentences.append(sentence_data)
            generation_stats['accepted'] += 1
        else:
            generation_stats['rejected'] += 1
        
        # Avoid infinite loops
        if generation_stats['total_generated'] >= request.num_sentences * 10:
            break
    
    generation_stats['time_elapsed'] = time.time() - start_time
    
    return {
        "sentences": valid_sentences,
        "stats": generation_stats
    }

if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)