from components.job_scoring import score_job_relevance

def is_job_relevant(job, user_profile, threshold=0.5):
    """
    Determines if a job is relevant to the user based on relevance score.

    Args:
        job (dict): A job dictionary containing title, description, and requirements.
        user_profile (dict): The user's profile with skills and bio.
        threshold (float): Minimum relevance score to consider the job relevant.

    Returns:
        tuple(bool, float): Whether the job is relevant and its score.
    """
    score = score_job_relevance(
        job["title"],
        job["description"],
        job["requirements"],
        user_profile
    )
    is_relevant = score >= threshold
    return is_relevant, score
