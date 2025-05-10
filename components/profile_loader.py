def load_user_profile(email, name, skills, bio):
    """
    Constructs and returns a user profile dictionary.

    Args:
        email (str): User's email.
        name (str): User's full name.
        skills (list of str): List of user skills.
        bio (str): A brief personal or professional bio.

    Returns:
        dict: A user profile dictionary used across the agent.
    """
    return {
        "name": name,
        "email": email,
        "skills": skills,
        "bio": bio or "User bio not provided."
    }
