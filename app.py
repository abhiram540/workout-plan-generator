"""Streamlit UI for the Workout Plan Generator."""

from __future__ import annotations

import os

import streamlit as st
from dotenv import load_dotenv

from workout_generator import (
    UserProfile,
    VALID_EQUIPMENT,
    VALID_EXPERIENCE,
    VALID_GOALS,
    generate_workout_plan,
    swap_exercise,
)

load_dotenv()

st.set_page_config(
    page_title="Workout plan generator",
    page_icon=":material/fitness_center:",
    layout="centered",
)

st.html("<style>[data-testid='stElementToolbar'] { display: none; }</style>")

HERO_IMAGE = "https://images.unsplash.com/photo-1571019613454-1cb2f99b2d8b?w=1600&auto=format&fit=crop&q=80"
STRENGTH_IMAGE = "https://images.unsplash.com/photo-1518611012118-696072aa579a?w=800&auto=format&fit=crop&q=80"
ENDURANCE_IMAGE = "https://images.unsplash.com/photo-1517836357463-d25dfeac3438?w=800&auto=format&fit=crop&q=80"
COMMUNITY_IMAGE = "https://images.unsplash.com/photo-1571731956672-f2b94d7dd0cb?w=800&auto=format&fit=crop&q=80"
RESULT_IMAGE = "https://images.unsplash.com/photo-1584464491033-06628f3a6b7b?w=1000&auto=format&fit=crop&q=80"

GOAL_LABELS = {
    "Build muscle": ":material/fitness_center: Build muscle",
    "Lose fat": ":material/local_fire_department: Lose fat",
    "General fitness": ":material/favorite: General fitness",
    "Improve endurance": ":material/directions_run: Improve endurance",
}
EXPERIENCE_LABELS = {
    "Beginner": ":material/spa: Beginner",
    "Intermediate": ":material/bolt: Intermediate",
    "Advanced": ":material/military_tech: Advanced",
}
EQUIPMENT_LABELS = {
    "No equipment": ":material/self_improvement: No equipment",
    "Home dumbbells": ":material/fitness_center: Home dumbbells",
    "Full gym": ":material/sports_gymnastics: Full gym",
}

if "plan" not in st.session_state:
    st.session_state.plan = None
if "profile" not in st.session_state:
    st.session_state.profile = None
if "swap_result" not in st.session_state:
    st.session_state.swap_result = None


def get_api_key() -> str:
    """Resolve the Groq API key from env/secrets, or let the user paste one."""
    env_key = os.getenv("GROQ_API_KEY", "")
    try:
        secrets_key = st.secrets.get("GROQ_API_KEY", "")
    except Exception:
        secrets_key = ""
    key = env_key or secrets_key
    if key:
        return key
    with st.container(border=True):
        st.markdown("**:material/key: Groq API key required**")
        st.text_input(
            "Groq API key",
            type="password",
            help="Set GROQ_API_KEY in a .env file to skip this.",
            key="api_key_input",
            label_visibility="collapsed",
            placeholder="Paste your Groq API key",
        )
        st.caption("Your key stays local to this session and is never stored.")
    return st.session_state.get("api_key_input", "")


api_key = get_api_key()

st.image(HERO_IMAGE, width="stretch")
st.title("🏋️‍♀️Workout Plan Generator🏋️", text_alignment="center")
st.caption("🤜Build a workout plan you'll actually stick to🤛", text_alignment="center")
st.markdown(
    "Tell us about your goals, your schedule, and your body — get back a structured, "
    "coach-quality weekly plan built around real constraints, not guesswork.",
    text_alignment="center",
)

st.space("large")

feature_cols = st.columns(3)
with feature_cols[0]:
    st.image(STRENGTH_IMAGE, width="stretch")
    st.markdown("##### :material/target: Built around your goal")
    st.caption("Muscle, fat loss, endurance, or general fitness — every exercise follows your primary target.")
with feature_cols[1]:
    st.image(ENDURANCE_IMAGE, width="stretch")
    st.markdown("##### :material/health_and_safety: Respects your limits")
    st.caption("Bad knees? No overhead pressing? Tell us once and the plan works around it, not through it.")
with feature_cols[2]:
    st.image(COMMUNITY_IMAGE, width="stretch")
    st.markdown("##### :material/calendar_month: Fits your real week")
    st.caption("Exactly as many training days as you have time for — no more, no less.")

st.space("large")

with st.container(border=True):
    st.subheader(":material/edit_note: Tell us about yourself")
    with st.form("profile_form"):
        goal = st.segmented_control(
            "Fitness goal",
            VALID_GOALS,
            format_func=lambda g: GOAL_LABELS[g],
            default=VALID_GOALS[0],
            required=True,
        )
        experience = st.segmented_control(
            "Experience level",
            VALID_EXPERIENCE,
            format_func=lambda e: EXPERIENCE_LABELS[e],
            default=VALID_EXPERIENCE[0],
            required=True,
        )
        days_per_week = st.slider("Days available per week", min_value=1, max_value=7, value=3)
        rest_days = 7 - days_per_week
        st.caption(
            f"{days_per_week} training day{'s' if days_per_week != 1 else ''} · "
            f"{rest_days} recovery day{'s' if rest_days != 1 else ''} — a sustainable weekly rhythm."
        )
        equipment = st.segmented_control(
            "Equipment access",
            VALID_EQUIPMENT,
            format_func=lambda eq: EQUIPMENT_LABELS[eq],
            default=VALID_EQUIPMENT[0],
            required=True,
        )
        limitations = st.text_area(
            "Injuries or limitations (optional)",
            placeholder='e.g. "bad knees", "no overhead pressing"',
            max_chars=500,
        )
        submitted = st.form_submit_button(
            "Generate my plan", icon=":material/rocket_launch:", type="primary", width="stretch"
        )

if submitted:
    profile = UserProfile(
        goal=goal,
        experience=experience,
        days_per_week=days_per_week,
        equipment=equipment,
        limitations=limitations,
    )
    with st.spinner("Designing your plan..."):
        success, result = generate_workout_plan(profile, api_key)

    if success:
        st.session_state.plan = result
        st.session_state.profile = profile
        st.session_state.swap_result = None
        st.toast("Your plan is ready", icon=":material/celebration:")
    else:
        st.session_state.plan = None
        st.error(result, icon=":material/error:")

if st.session_state.plan and st.session_state.profile:
    st.space("large")
    st.subheader(":material/calendar_view_week: Your weekly plan")

    result_cols = st.columns([2, 1])
    with result_cols[0]:
        with st.container(horizontal=True):
            if st.button("Regenerate", icon=":material/refresh:"):
                with st.spinner("Generating a new variation..."):
                    success, result = generate_workout_plan(
                        st.session_state.profile, api_key, temperature=0.95
                    )
                if success:
                    st.session_state.plan = result
                    st.session_state.swap_result = None
                    st.rerun()
                else:
                    st.error(result, icon=":material/error:")
            st.download_button(
                "Download",
                data=st.session_state.plan,
                file_name="workout_plan.md",
                mime="text/markdown",
                icon=":material/download:",
            )
        with st.container(border=True):
            st.markdown(st.session_state.plan)
    with result_cols[1]:
        st.image(RESULT_IMAGE, width="stretch")
        st.caption("Consistency beats intensity. Show up, follow the plan, and let the results compound.")

    st.space("large")
    with st.expander("Want to swap an exercise?", icon=":material/swap_horiz:"):
        with st.form("swap_form", border=False):
            with st.container(horizontal=True, vertical_alignment="bottom"):
                exercise_to_swap = st.text_input(
                    "Which exercise would you like an alternative for?",
                    placeholder='e.g. "Day 2 - Barbell Squat"',
                )
                swap_submitted = st.form_submit_button("Find alternative", icon=":material/search:")

        if swap_submitted:
            with st.spinner("Finding an alternative..."):
                success, result = swap_exercise(exercise_to_swap, st.session_state.profile, api_key)
            st.session_state.swap_result = result if success else None
            if not success:
                st.error(result, icon=":material/error:")

        if st.session_state.swap_result:
            st.success(st.session_state.swap_result, icon=":material/check_circle:")

st.space("large")
st.caption(
    "App designed/developed by Abhiram Muktineni. "
    "Content generated by AI as general fitness guidance, not medical advice. "
    "Consult a professional before starting a new program, especially with an injury."
)
