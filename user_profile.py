# components/user_profile.py

def create_user_profile(email, name, skills, bio):
    """
    Creates a user profile dictionary with the given details.

    Args:
        email (str): User's email address.
        name (str): User's name.
        skills (list): List of user skills.
        bio (str): User's bio information.

    Returns:
        dict: A dictionary representing the user profile.
    """
    return {
        "email": email,
        "name": name,
        "skills": skills,
        "bio": bio
    }

def update_user_profile(existing_profile, new_data):
    """
    Updates the existing user profile with new data.

    Args:
        existing_profile (dict): The current user profile.
        new_data (dict): Dictionary containing the new data to update.

    Returns:
        dict: The updated user profile.
    """
    updated_profile = existing_profile.copy()
    updated_profile.update(new_data)
    return updated_profile

def get_user_name(user_profile):
    """
    Retrieves the user's name from the profile.

    Args:
        user_profile (dict): The user's profile.

    Returns:
        str: The user's name.
    """
    return user_profile.get("name", "Unknown")

def get_user_skills(user_profile):
    """
    Retrieves the user's skills from the profile.

    Args:
        user_profile (dict): The user's profile.

    Returns:
        list: The list of user's skills.
    """
    return user_profile.get("skills", [])

def get_user_bio(user_profile):
    """
    Retrieves the user's bio from the profile.

    Args:
        user_profile (dict): The user's profile.

    Returns:
        str: The user's bio.
    """
    return user_profile.get("bio", "No bio provided.")
