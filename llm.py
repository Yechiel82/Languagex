# Import necessary libraries
from unsloth import FastLanguageModel
import torch
import re
import joblib
import numpy as np
import time
from datetime import timedelta
from sentence_transformers import SentenceTransformer
from huggingface_hub import snapshot_download
import random

# Step 1: Load the evaluator model
print("Loading evaluator model...")
# eval_model_path = snapshot_download(repo_id="Mr-FineTuner/Eval_01_dup")
eval_model_path = snapshot_download(repo_id="Mr-FineTuner/Eval_03_dup")
eval_model = joblib.load(f'{eval_model_path}/text_classification_model.joblib')
embedder = SentenceTransformer('all-mpnet-base-v2')

# Step 2: Prediction function
def predict_sentiment(text):
    embedding = embedder.encode([text])
    probs = eval_model.predict_proba(embedding)[0]
    prediction = np.argmax(probs) + 1
    return max(1, min(6, int(prediction)))

# Step 3: Load the generator model
print("\nLoading generator model...")
gen_model_path = snapshot_download(repo_id="Mr-FineTuner/fullcomplete-01")
model, tokenizer = FastLanguageModel.from_pretrained("Mr-FineTuner/fullcomplete-01", load_in_4bit=True)
model = FastLanguageModel.for_inference(model)

# Configure tokenizer
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token

# Configuration
levels = ["A1", "A2", "B1", "B2", "C1", "C2"]
cefr_to_score = {'A1': 1, 'A2': 2, 'B1': 3, 'B2': 4, 'C1': 5, 'C2': 6}
num_sentences_per_level = 1
device = next(model.parameters()).device
all_sentences = {}
topic = "Food"  # Change this value to set the topic for sentence generation

# Statistics tracking
generation_stats = {
    level: {
        'total_generated': 0,
        'accepted': 0,
        'rejected': 0,
        'reasons': {
            'format_mismatch': 0,
            'score_out_of_range': 0,
            'duplicate': 0,
            'verb_not_found': 0
        },
        'start_time': None,
        'end_time': None,
        'time_elapsed': None
    } for level in levels
}

# Verb-only prompt templates
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

def create_arrange_question(sentence, verb):
    """
    Create an arrange-the-sentence question where each / contains exactly one word
    while preserving the original verb form and proper sentence structure
    """
    # Remove punctuation and clean the sentence
    clean_sentence = re.sub(r'[^\w\s]', '', sentence)
    words = [w for w in clean_sentence.split() if w]  # Get all words and filter empty strings

    # Find the verb form actually used in the sentence (case sensitive)
    verb_form = None
    for word in words:
        if verb.lower() in word.lower():
            verb_form = word
            break

    # If verb not found (shouldn't happen with our extraction), use base form
    if not verb_form:
        verb_form = verb

    # Create the word list to shuffle (all individual words)
    words_to_shuffle = [w for w in words if w.lower() != verb_form.lower()]

    # Ensure we have enough words to make it meaningful
    if len(words_to_shuffle) < 2:  # Need at least 2 words besides the verb
        return None

    # Shuffle while ensuring verb isn't first/last (for better challenge)
    np.random.shuffle(words_to_shuffle)

    # Insert the verb at random position (not first or last)
    insert_pos = np.random.randint(1, len(words_to_shuffle))
    words_to_shuffle.insert(insert_pos, verb_form)

    # Format with single words separated by /
    return " / ".join(words_to_shuffle) + " (Arrange the words)"


def create_fill_in_blank(sentence, verb):
    """
    Perfect fill-in-the-blank creator that handles:
    - All verb forms (diver, coos, hustled)
    - Capitalization
    - Punctuation
    - Only replaces the first occurrence
    """
    # Create regex pattern that matches the verb with any suffix
    pattern = rf"(\b{re.escape(verb)}[a-z]*\b)"

    # Find the verb (case insensitive)
    match = re.search(pattern, sentence, re.IGNORECASE)
    if not match:
        return None

    # Get the actual verb form used in the sentence
    actual_verb = match.group(1)

    # Replace with our blank format, keeping original capitalization
    if actual_verb[0].isupper():
        blank = f"__({verb.lower()})"
        blank = blank[0].upper() + blank[1:]
    else:
        blank = f"__({verb})"

    # Replace only the first occurrence
    question = sentence[:match.start()] + blank + sentence[match.end():]

    return question

def generate_contextual_distractors(target_verb, sentence, num_distractors=3):
    """
    Generate distractors that are clearly wrong but still plausible and grammatically correct
    """
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

    # Get response from your generator model
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
        # Remove any content after apostrophes or special characters
        v = re.sub(r"[^a-zA-Z].*$", "", v)
        # Remove any remaining punctuation
        v = re.sub(r"[^a-zA-Z]", "", v)
        if v and v != target_verb.lower() and len(v) > 2:  # Minimum 3 letters
            distractors.append(v)

    # Remove duplicates and limit count
    return list(set(distractors))[:num_distractors]

def create_mc_question(sentence, correct_verb, incorrect_verbs):
    blank_sentence = create_fill_in_blank(sentence, correct_verb)
    options = incorrect_verbs + [correct_verb]
    random.shuffle(options)

    # Clean each option one more time
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
    generation_stats[level]['total_generated'] += 1

    pattern = r"The word is: ['\"]([^'\"]+)['\"] and it is a verb\. Example sentence: ['\"]([^'\"]+)['\"]"
    match = re.search(pattern, text)
    if not match:
        generation_stats[level]['rejected'] += 1  # Track total rejections
        generation_stats[level]['reasons']['format_mismatch'] += 1  # Track specific reason
        return None

    verb, sentence = match.group(1), match.group(2)

    # Basic validation
    if len(sentence.split()) < 3 or not sentence.endswith(('.', '!', '?')):
        generation_stats[level]['rejected'] += 1  # Track total rejections
        generation_stats[level]['reasons']['format_mismatch'] += 1  # Track specific reason
        return None

    # Create both question types
    fill_in_blank = create_fill_in_blank(sentence, verb)
    arrange_question = create_arrange_question(sentence, verb)

    if not fill_in_blank or not arrange_question:
        generation_stats[level]['rejected'] += 1  # Track total rejections
        generation_stats[level]['reasons']['verb_not_found'] += 1  # Track specific reason
        return None

    # Generate multiple choice options
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


# Main generation process
print("\nStarting sentence generation...")
overall_start = time.time()

for level in levels:
    level_start = time.time()
    generation_stats[level]['start_time'] = level_start
    print(f"\n=== Generating {num_sentences_per_level} sentences for {level} ===")

    level_sentences = []
    target_score = cefr_to_score[level]
    generated_count = 0
    progress_stars = ""

    while len(level_sentences) < num_sentences_per_level:
        # Generate the sentence
        prompt = prompt_templates[level]
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
        generated_count += 1
        progress_stars += "*"

        # Clear line and print progress
        print(f"\r{progress_stars}", end="", flush=True)

        # Process and validate
        extracted_data = extract_formatted_sentence(generated_text, level)
        if not extracted_data:
            continue

        # Evaluate
        predicted_score = predict_sentiment(extracted_data["sentence"])
        is_accepted = abs(predicted_score - target_score) <= 1

        if is_accepted:
            if not any(existing["sentence"] == extracted_data["sentence"] for existing in level_sentences):
                level_sentences.append(extracted_data)
                generation_stats[level]['accepted'] += 1
                print(f"\n✓ Accepted: {extracted_data['fill_in_blank']}")
            else:
                generation_stats[level]['rejected'] += 1
                generation_stats[level]['reasons']['duplicate'] += 1
        else:
            generation_stats[level]['rejected'] += 1
            generation_stats[level]['reasons']['score_out_of_range'] += 1

    all_sentences[level] = level_sentences
    generation_stats[level]['end_time'] = time.time()
    generation_stats[level]['time_elapsed'] = generation_stats[level]['end_time'] - generation_stats[level]['start_time']
    print(f"\nGenerated {generated_count} sentences to get {num_sentences_per_level} valid ones")



output_file = "cefr_sentences_with_question_number2_addMultipleAnswer_040425.txt"
with open(output_file, "w", encoding="utf-8") as f:
    for level, sentences in all_sentences.items():
        f.write(f"--- {level} ---\n")
        for sentence_data in sentences:
            f.write(sentence_data["formatted"] + "\n")
            f.write(f"Fill-in-the-blank: {sentence_data['fill_in_blank']}\n")
            f.write(f"Arrange the words: {sentence_data['arrange_question']}\n")

            # Handle multiple choice output with better cleaning and formatting
            if 'multiple_choice' in sentence_data:
                mc = sentence_data['multiple_choice']

                # Get question text
                question_text = ""
                if isinstance(mc, dict):
                    if 'question' in mc and isinstance(mc['question'], dict):
                        question_text = mc['question'].get('question_text', '')
                    else:
                        question_text = mc.get('question', '')

                # Get and clean options
                options = []
                if isinstance(mc, dict):
                    if 'question' in mc and isinstance(mc['question'], dict):
                        options = mc['question'].get('options', [])
                    else:
                        options = mc.get('options', [])

                # Clean each option
                cleaned_options = []
                for opt in options:
                    if isinstance(opt, str):
                        # Remove punctuation and everything after it
                        clean_opt = re.sub(r'[^a-zA-Z].*$', '', opt)
                        # Remove any remaining special characters
                        clean_opt = re.sub(r'[^a-zA-Z]', '', clean_opt)
                        if clean_opt and len(clean_opt) > 2:  # Minimum 3 letters
                            cleaned_options.append(clean_opt.lower())

                # Get correct answer
                correct_answer = ""
                if isinstance(mc, dict):
                    if 'question' in mc and isinstance(mc['question'], dict):
                        correct_answer = mc['question'].get('correct_answer', '')
                    else:
                        correct_answer = mc.get('answer', '')

                # Clean the correct answer
                correct_answer = re.sub(r'[^a-zA-Z].*$', '', str(correct_answer))
                correct_answer = re.sub(r'[^a-zA-Z]', '', correct_answer).lower()

                # Write to file with numbered options
                if question_text and cleaned_options and correct_answer:
                    f.write(f"Multiple Choice: {question_text}\n")
                    for i, opt in enumerate(cleaned_options[:4], 1):  # Show max 4 options
                        f.write(f"  {i}. {opt}\n")
                    f.write(f"Correct answer: {correct_answer}\n")
                else:
                    f.write("Multiple Choice: [Invalid format]\n")

            f.write("\n")  # Add extra newline between entries

# Calculate and display statistics
total_time = time.time() - overall_start
print("\n=== GENERATION COMPLETE ===")
print(f"Total time: {timedelta(seconds=int(total_time))}")
print(f"Results saved to: {output_file}")

print("\n=== DETAILED STATISTICS ===")
for level in levels:
    stats = generation_stats[level]
    time_taken = timedelta(seconds=int(stats['time_elapsed']))
    
    # Calculate total rejections from reasons (for verification)
    total_rejections_from_reasons = sum(stats['reasons'].values())
    
    # Ensure rejected count matches sum of rejection reasons
    if stats['rejected'] != total_rejections_from_reasons:
        print(f"\nWarning: Mismatch in rejection counts for {level} - "
              f"reported {stats['rejected']} but sum of reasons is {total_rejections_from_reasons}")
        stats['rejected'] = total_rejections_from_reasons  # Auto-correct

    print(f"\n{level} Statistics:")
    print(f"Time taken: {time_taken}")
    print(f"Generated: {stats['total_generated']}")
    print(f"Accepted: {stats['accepted']}")
    print(f"Rejected: {stats['rejected']} (sum check: {total_rejections_from_reasons})")
    print("Rejection reasons:")
    print(f"  Format issues: {stats['reasons']['format_mismatch']}")
    print(f"  Wrong level: {stats['reasons']['score_out_of_range']}")
    print(f"  Duplicates: {stats['reasons']['duplicate']}")
    print(f"  Verb not found: {stats['reasons']['verb_not_found']}")
    
    # Calculate acceptance rate safely (avoid division by zero)
    if stats['total_generated'] > 0:
        acceptance_rate = stats['accepted'] / stats['total_generated']
    else:
        acceptance_rate = 0
    print(f"Acceptance rate: {acceptance_rate:.1%}")
print("\n=== SAMPLE OUTPUT ===")
for level in levels[:2]:  # Show first two levels as example
    if all_sentences[level]:
        print(f"\n{level} Examples:")
        for i, sentence in enumerate(all_sentences[level][:2], 1):
            print(f"{i}. {sentence['fill_in_blank']}")