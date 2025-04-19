from unsloth import FastLanguageModel
from sentence_transformers import SentenceTransformer
import joblib
import numpy as np
import re
import random
from huggingface_hub import snapshot_download
import torch
from transformers import TextStreamer
import spacy

def generate_sentences(level, num_sentences=2, user_id=None):
    # Step 1: Load models
    max_seq_length = 2048
    dtype = None
    load_in_4bit = True
    model_name = "Mr-FineTuner/Generator-2-Epoch-UnifiedDataset"
    
    try:
        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name=model_name,
            max_seq_length=max_seq_length,
            dtype=dtype,
            load_in_4bit=load_in_4bit,
        )
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token
        model = FastLanguageModel.for_inference(model)
    except Exception as e:
        raise Exception(f"Error loading model: {e}")

    eval_model_path = snapshot_download(repo_id="Mr-FineTuner/Eval_02_dup")
    eval_model = joblib.load(f'{eval_model_path}/text_classification_model.joblib')
    embedder = SentenceTransformer('paraphrase-MiniLM-L6-v2')
    
    def predict_sentiment(text):
        embedding = embedder.encode([text])
        probs = eval_model.predict_proba(embedding)[0]
        prediction = np.argmax(probs) + 1
        return max(1, min(6, int(prediction)))

    # Step 2: Configuration
    levels = ["A1", "A2", "B1", "B2", "C1", "C2"]
    cefr_to_score = {'A1': 1, 'A2': 2, 'B1': 3, 'B2': 4, 'C1': 5, 'C2': 6}
    device = next(model.parameters()).device
    nlp = spacy.load("en_core_web_sm")

    # Step 3: Helper functions (same as original)
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

    def create_mc_question(sentence, correct_verb, incorrect_verbs):
        blank_sentence = create_fill_in_blank(sentence, correct_verb)
        options = incorrect_verbs + [correct_verb]
        random.shuffle(options)
        cleaned_options = []
        for opt in options:
            clean_opt = re.sub(r'[^a-zA-Z]', '', opt.lower()).strip()
            if clean_opt:
                cleaned_options.append(clean_opt)
        return {
            "question_text": blank_sentence,
            "options": cleaned_options,
            "correct_answer": correct_verb.lower()
        }

    def generate_contextual_distractors(target_verb, sentence, num_distractors=3):
        prompt = f"""Generate {num_distractors} incorrect verb options for fill-in-the-blank.
Rules:
1. Must be grammatically correct in the sentence
2. Must create a clearly incorrect but related meaning
3. Should be at the same CEFR level as the original verb
4. Should not be synonyms or alternative correct answers
Example:
Verb: "eat" | Sentence: "I ____ bread every morning."
Distractors: drive, sing, wear
Now generate {num_distractors} CLEARLY INCORRECT but grammatically valid distractors for:
Verb: "{target_verb}"
Sentence: "{sentence}"
Return ONLY the verbs as a comma-separated list:"""
        inputs = tokenizer(prompt, return_tensors="pt", padding=True).to(device)
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=50,
                do_sample=True,
                temperature=0.7,
                top_k=50,
                pad_token_id=tokenizer.pad_token_id,
            )
        response = tokenizer.decode(outputs[0][inputs['input_ids'].shape[1]:], skip_special_tokens=True).strip()
        distractors = []
        for v in response.split(","):
            v = re.sub(r'[^a-zA-Z]', '', v.strip().lower())
            if v and v != target_verb.lower() and len(v) > 2:
                distractors.append(v)
        return list(set(distractors))[:num_distractors]

    # Step 4: Generate sentences
    validated_sentences = []
    target_score = cefr_to_score.get(level, 1)
    
    while len(validated_sentences) < num_sentences:
        input_text = f"### Input:\nGenerate a sentence at CEFR level {level}.\n### Response:\n"
        input_data = tokenizer(
            input_text,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=max_seq_length,
        ).to("cuda")
        input_ids = input_data["input_ids"]
        attention_mask = input_data["attention_mask"]
        outputs = model.generate(
            input_ids=input_ids,
            attention_mask=attention_mask,
            max_new_tokens=25,
            pad_token_id=tokenizer.pad_token_id,
            do_sample=True,
            temperature=0.6,
            top_k=40,
            top_p=0.85,
            stop_strings=["\n"],
        )
        generated_text = tokenizer.decode(outputs[0], skip_special_tokens=True)
        response_start = generated_text.find("### Response:\n") + len("### Response:\n")
        response_text = generated_text[response_start:].strip()

        first_sent = nlp(response_text).sents.__next__().text.strip() if list(nlp(response_text).sents) else response_text
        prefix = f"Example sentence at level {level}: "
        if first_sent.startswith(prefix):
            first_sent = first_sent[len(prefix):].strip()

        doc = nlp(first_sent)
        verbs = [token for token in doc if token.pos_ == "VERB" and token.dep_ not in ["aux", "auxpass"]]
        verb = verbs[0].text if verbs else None

        if not verb:
            continue

        predicted_score = predict_sentiment(first_sent)
        if abs(predicted_score - target_score) > 1:
            continue

        if any(existing["sentence"] == first_sent for existing in validated_sentences):
            continue

        fill_in_blank = create_fill_in_blank(first_sent, verb)
        arrange_question = create_arrange_question(first_sent, verb)
        mc_distractors = generate_contextual_distractors(verb, first_sent)
        mc_question = create_mc_question(first_sent, verb, mc_distractors) if mc_distractors else None

        if not fill_in_blank or not arrange_question:
            continue

        validated_sentences.append({
            "sentence": first_sent,
            "verb": verb,
            "fill_in_blank": fill_in_blank,
            "arrange_question": arrange_question,
            "multiple_choice": mc_question,
            "level": level,
            "for_user": user_id
        })

    return validated_sentences