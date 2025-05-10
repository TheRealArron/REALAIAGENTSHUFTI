import torch
from transformers import T5Tokenizer, T5ForConditionalGeneration

# === Model Setup (Load once) ===
MODEL_NAME = "google/flan-t5-small"
tokenizer = T5Tokenizer.from_pretrained(MODEL_NAME)
model = T5ForConditionalGeneration.from_pretrained(MODEL_NAME)

def generate_application_message(user_profile, job_title, job_description, job_requirements):
    """
    Generates a job application message using the user's profile and job details.

    Args:
        user_profile (dict): Dict with 'name', 'skills', 'bio'.
        job_title (str): Title of the job.
        job_description (str): Job description.
        job_requirements (str): Job requirements.

    Returns:
        str: Generated message.
    """
    profile_text = (
        f"My name is {user_profile.get('name', 'Anonymous')}. "
        f"I have experience in {', '.join(user_profile.get('skills', []))}. "
        f"{user_profile.get('bio', '')}"
    )

    prompt = f"""
    Write a polite, concise job application message in English using the following profile and job details.
    Profile: {profile_text}
    Job Title: {job_title}
    Job Description: {job_description}
    Job Requirements: {job_requirements}
    """

    input_ids = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=1024).input_ids
    with torch.no_grad():
        output_ids = model.generate(
            input_ids,
            max_length=400,
            num_beams=5,
            early_stopping=True,
            no_repeat_ngram_size=2
        )

    return tokenizer.decode(output_ids[0], skip_special_tokens=True).strip()
