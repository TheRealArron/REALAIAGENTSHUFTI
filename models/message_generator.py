import torch
from transformers import T5ForConditionalGeneration, T5Tokenizer
from utils.logger import append_log


class MessageGenerator:
    def __init__(self, model_name="google/flan-t5-small"):
        self.tokenizer = T5Tokenizer.from_pretrained(model_name)
        self.model = T5ForConditionalGeneration.from_pretrained(model_name)

    def generate_message(self, job_title, job_description, job_requirements, user_profile):
        """
        Generates a polite, concise job application message using the job details and user profile.

        Args:
            job_title (str): Title of the job.
            job_description (str): Description of the job.
            job_requirements (str): Requirements for the job.
            user_profile (dict): User's profile including name, skills, and bio.

        Returns:
            str: The generated application message.
        """
        profile_text = f"My name is {user_profile.get('name', 'Anonymous')}. " \
                       f"I have experience in {', '.join(user_profile.get('skills', []))}. " \
                       f"{user_profile.get('bio', '')}"

        prompt = f"""Write a polite, concise job application message in English using the following profile and job details.
Profile: {profile_text}
Job Title: {job_title}
Job Description: {job_description}
Job Requirements: {job_requirements}
"""
        input_ids = self.tokenizer(prompt, return_tensors="pt", truncation=True, max_length=1024).input_ids
        with torch.no_grad():
            output_ids = self.model.generate(
                input_ids,
                max_length=400,
                num_beams=5,
                early_stopping=True,
                no_repeat_ngram_size=2
            )

        message = self.tokenizer.decode(output_ids[0], skip_special_tokens=True).strip()

        # Log the generated message for debugging
        append_log(f"Generated message: {message}\n")

        return message
