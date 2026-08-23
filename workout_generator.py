"""Core logic for the Workout Plan Generator: input validation, prompt
construction, and the Groq API call. Kept separate from the Streamlit UI
so the generation logic can be tested/reused independently.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from groq import Groq, APIConnectionError, APIStatusError, RateLimitError

DEFAULT_MODEL = "openai/gpt-oss-120b"

VALID_GOALS = ("Build muscle", "Lose fat", "General fitness", "Improve endurance")
VALID_EXPERIENCE = ("Beginner", "Intermediate", "Advanced")
VALID_EQUIPMENT = ("No equipment", "Home dumbbells", "Full gym")


@dataclass
class UserProfile:
    """Structured inputs collected from the Streamlit form."""

    goal: str
    experience: str
    days_per_week: int
    equipment: str
    limitations: str = ""


def validate_profile(profile: UserProfile) -> Optional[str]:
    """Return a friendly error message if the profile is invalid, else None."""
    if profile.goal not in VALID_GOALS:
        return "Please select a valid fitness goal."
    if profile.experience not in VALID_EXPERIENCE:
        return "Please select a valid experience level."
    if profile.equipment not in VALID_EQUIPMENT:
        return "Please select a valid equipment option."
    if not isinstance(profile.days_per_week, int) or not (1 <= profile.days_per_week <= 7):
        return "Days available per week must be between 1 and 7."
    if len(profile.limitations) > 500:
        return "Injuries/limitations text is too long (max 500 characters)."
    return None


def build_prompt(profile: UserProfile) -> Tuple[str, str]:
    """Build the (system_prompt, user_prompt) pair sent to the LLM."""

    system_prompt = (
        "You are a certified personal trainer writing a workout plan for a client. "
        "You write safe, practical, and well-structured training plans. "
        "You are not a doctor: never give medical diagnoses or medical advice. "
        "If the client mentions an injury or physical limitation, you must design "
        "around it (avoid or modify exercises that would aggravate it) and include "
        "a short disclaimer recommending they consult a medical professional or "
        "physical therapist before starting. "
        "Always respect the client's stated equipment access, available days, and "
        "experience level exactly - never assume equipment or days they didn't list. "
        "Output must be well-structured Markdown, never a single wall of text."
    )

    limitations_text = profile.limitations.strip() or "None reported"

    user_prompt = f"""Create a weekly workout plan for a client with the following profile:

- Primary goal: {profile.goal}
- Experience level: {profile.experience}
- Training days available per week: {profile.days_per_week}
- Equipment access: {profile.equipment}
- Injuries / limitations: {limitations_text}

Requirements for your response:
1. Produce exactly {profile.days_per_week} training day(s), labeled "Day 1", "Day 2", etc.
   Do not add extra days beyond what was requested. If rest/recovery days matter, mention
   them briefly in a short "Weekly Notes" section at the end, not as numbered training days.
2. For each training day, include:
   - A short focus label (e.g. "Day 1: Upper Body Push")
   - A brief warm-up (2-3 lines)
   - A table or bullet list of exercises with sets, reps (or duration), and rest time
   - Only exercises that are actually doable with the stated equipment ({profile.equipment})
   - If a day ends with a circuit or finisher made of multiple movements, list it as its own
     bulleted sub-list below the table (not crammed into one table cell)
3. Scale volume and exercise complexity to the client's experience level ({profile.experience}).
4. Keep every exercise choice consistent with the stated goal ({profile.goal}).
5. If limitations/injuries were reported ("{limitations_text}"), explicitly avoid or modify
   any exercise that would aggravate them, and briefly note the substitution you made.
6. Do not include medical claims or diagnoses. If any limitation was reported, end the plan
   with a one-line disclaimer recommending the client consult a doctor or physical therapist
   before starting.
7. Format the entire response in clean Markdown with headers for each day.
8. Never use raw HTML tags (e.g. <br>, <ul>, <li>) anywhere in the response, including inside
   table cells. Use plain Markdown line breaks, separate rows, or bullet lists instead.
"""

    return system_prompt, user_prompt


def generate_workout_plan(
    profile: UserProfile,
    api_key: str,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.7,
) -> Tuple[bool, str]:
    """Call the Groq API to generate a workout plan.

    Returns a (success, message) tuple: on success ``message`` is the plan
    text, on failure it is a user-friendly error message safe to display.
    """
    validation_error = validate_profile(profile)
    if validation_error:
        return False, validation_error

    if not api_key:
        return False, "No Groq API key found. Please set GROQ_API_KEY and try again."

    system_prompt, user_prompt = build_prompt(profile)

    try:
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=2000,
        )
    except RateLimitError:
        return False, "The Groq API is rate-limited right now. Please wait a moment and try again."
    except APIConnectionError:
        return False, "Couldn't connect to the Groq API. Please check your internet connection and try again."
    except APIStatusError as exc:
        if exc.status_code == 401:
            return False, "Groq API key is invalid or missing permissions. Please check your key."
        return False, f"The Groq API returned an error (status {exc.status_code}). Please try again."
    except Exception:
        return False, "Something went wrong while generating your plan. Please try again."

    try:
        plan_text = response.choices[0].message.content
    except (AttributeError, IndexError, KeyError):
        return False, "Received an unexpected response from the API. Please try again."

    if not plan_text or not plan_text.strip():
        return False, "The AI returned an empty response. Please try again."

    return True, plan_text.strip()


def swap_exercise(
    exercise_description: str,
    profile: UserProfile,
    api_key: str,
    model: str = DEFAULT_MODEL,
) -> Tuple[bool, str]:
    """Ask the LLM for a single alternative exercise, respecting the same
    equipment/limitation constraints as the main plan.
    """
    if not exercise_description.strip():
        return False, "Please describe which exercise you'd like to swap."
    if not api_key:
        return False, "No Groq API key found. Please set GROQ_API_KEY and try again."

    limitations_text = profile.limitations.strip() or "None reported"

    system_prompt = (
        "You are a certified personal trainer. You suggest a single safe alternative "
        "exercise when asked, respecting equipment access and any injuries. You are not "
        "a doctor and never give medical advice. Keep the answer short."
    )
    user_prompt = (
        f"The client wants to swap this exercise: \"{exercise_description}\".\n"
        f"Equipment access: {profile.equipment}\n"
        f"Injuries/limitations: {limitations_text}\n"
        f"Experience level: {profile.experience}\n\n"
        "Suggest exactly one alternative exercise that targets the same muscle group(s), "
        "is doable with the stated equipment, and avoids the stated limitations. "
        "Respond in this exact short format:\n"
        "**Alternative:** <exercise name>\n"
        "**Sets x Reps:** <value>\n"
        "**Why:** <one sentence>"
    )

    try:
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.8,
            max_tokens=200,
        )
    except RateLimitError:
        return False, "The Groq API is rate-limited right now. Please wait a moment and try again."
    except APIConnectionError:
        return False, "Couldn't connect to the Groq API. Please check your internet connection and try again."
    except APIStatusError as exc:
        return False, f"The Groq API returned an error (status {exc.status_code}). Please try again."
    except Exception:
        return False, "Something went wrong while swapping the exercise. Please try again."

    try:
        swap_text = response.choices[0].message.content
    except (AttributeError, IndexError, KeyError):
        return False, "Received an unexpected response from the API. Please try again."

    if not swap_text or not swap_text.strip():
        return False, "The AI returned an empty response. Please try again."

    return True, swap_text.strip()
