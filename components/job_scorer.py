from sentence_transformers import SentenceTransformer, util

# Load the model once (consider caching in real deployments)
model = SentenceTransformer("all-MiniLM-L6-v2")

def score_job_relevance(title, description, requirements, user_profile):
    """
    Scores the relevance of a job based on semantic similarity between the job content and user profile.

    Args:
        title (str): Job title.
        description (str): Job description.
        requirements (str): Job requirements.
        user_profile (dict): Dictionary with user's 'skills' and 'bio'.

    Returns:
        float: Relevance score (0.0 to 1.0).
    """
    profile_text = " ".join(user_profile.get("skills", [])) + " " + user_profile.get("bio", "")
    job_text = f"{title} {description} {requirements}"

    embeddings = model.encode([profile_text, job_text], convert_to_tensor=True)
    score = util.pytorch_cos_sim(embeddings[0], embeddings[1]).item()

    return score
