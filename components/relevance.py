from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch

# Load a lightweight model for semantic similarity (you can upgrade this as needed)
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME)

def score_job_relevance(title, description, requirements, user_profile):
    """
    Scores job relevance using semantic similarity between user profile and job posting.

    Args:
        title (str): Job title.
        description (str): Job description.
        requirements (str): Job requirements.
        user_profile (dict): User profile with 'skills' and 'bio'.

    Returns:
        float: A score from 0.0 to 1.0 indicating relevance.
    """
    profile_text = f"{user_profile.get('name', '')} has experience in {', '.join(user_profile.get('skills', []))}. {user_profile.get('bio', '')}"
    job_text = f"{title}. {description}. {requirements}"

    inputs = tokenizer(profile_text, job_text, return_tensors="pt", truncation=True, padding=True)
    with torch.no_grad():
        outputs = model(**inputs)
        similarity_score = torch.sigmoid(outputs.logits).squeeze().item()

    return similarity_score
