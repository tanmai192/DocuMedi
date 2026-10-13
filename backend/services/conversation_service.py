"""
conversation_service.py — Conversational AI and Clinical Case-Taking Service for DocuMedi.

Handles:
1. Initial clinical intake greeting.
2. Dynamic conversation progression (Gemini / OpenAI REST API via httpx).
3. Red flag emergency symptom detection and urgent care notices.
4. Robust fallback clinical intake rules engine when API key is unconfigured or unavailable.
5. Server-side medical guardrails (no diagnosis, no prescription).
"""

import os
import re
from typing import List, Dict, Tuple, Optional
import httpx
from dotenv import load_dotenv

load_dotenv()

INITIAL_GREETING = (
    "Hello! Welcome to DocuMedi. How are you feeling today? "
    "Please describe any health concerns you would like to document."
)

SYSTEM_PROMPT = """
You are the DocuMedi Clinical Case-Taking Assistant.
DocuMedi is a patient-facing documentation tool for personal medical record-keeping.

YOUR MISSION:
Help the patient articulate and organize their health story so it can be structured into an accurate patient note.

CRITICAL CLINICAL & SAFETY RULES:
1. Ask ONE clear question at a time. Never ask multiple questions in a single response.
2. Use a calm, empathetic, and professional tone.
3. Systematically gather information covering:
   - Chief complaint (primary symptom or reason for visit)
   - History of present illness (onset, duration, severity on a 1-10 scale, description)
   - Associated symptoms
   - Past medical history and chronic conditions
   - Current medications and supplements
   - Known allergies (especially medications)
   - Relevant family and social history
4. Never force the patient to answer. If they skip or say "I don't know", move forward politely.
5. If the patient states they feel fine or have no symptoms, respond warmly and let them know they can finish the consultation.
6. When sufficient clinical context has been shared, summarize the key points neutrally and advise the patient that they can click "End Consultation" to proceed to their structured note review.
7. ABSOLUTE MEDICAL SAFETY RESTRICTIONS:
   - You are NOT a doctor. DO NOT provide a medical diagnosis or guess what disease they have.
   - NEVER prescribe medication, recommend pharmaceuticals, or advise changing any prescribed dosage.
   - For severe emergency symptoms (crushing chest pain, severe shortness of breath, sudden facial drooping or weakness, massive bleeding), instruct them IMMEDIATELY to call 911 (or local emergency services) and seek emergency medical care without delay.
"""

# Red flag patterns for immediate medical attention
EMERGENCY_PATTERNS = [
    r"\b(crushing|severe)\s+chest\s+pain\b",
    r"\bheart\s+attack\b",
    r"\bcan'?t\s+breathe\b",
    r"\bsevere\s+shortness\s+of\s+breath\b",
    r"\bface\s+(droop|numb)\b",
    r"\bsudden\s+(weakness|paralysis)\b",
    r"\bcoughing\s+(up\s+)?blood\b",
    r"\buncontrolled\s+bleeding\b",
    r"\bloss\s+of\s+consciousness\b",
    r"\bsuicid(al|e)\b",
]

EMERGENCY_WARNING = (
    "\n\n⚠️ **URGENT MEDICAL NOTICE:** Based on the symptoms you reported, this may be a medical emergency. "
    "Please call 911 (or your local emergency number) or go to the nearest emergency room immediately. "
    "Do not wait for online documentation."
)


def detect_emergencies(text: str) -> bool:
    """Check if patient message contains urgent emergency red flags."""
    lower_text = text.lower()
    for pattern in EMERGENCY_PATTERNS:
        if re.search(pattern, lower_text):
            return True
    return False


def get_ai_config() -> Tuple[str, Optional[str], str]:
    """Retrieve AI provider settings from environment."""
    provider = os.getenv("AI_PROVIDER", "gemini").lower().strip()
    api_key = os.getenv("AI_API_KEY", "").strip()
    model = os.getenv("AI_MODEL", "gemini-1.5-flash").strip()

    # Treat template placeholders as unconfigured
    if not api_key or api_key in ("your_ai_api_key_here", "your_gemini_api_key", "your_openai_api_key"):
        api_key = None

    return provider, api_key, model


def generate_rules_fallback_response(history: List[Dict[str, str]], patient_message: str) -> str:
    """
    Deterministic clinical intake progression used when live AI API is unconfigured or unavailable.
    Ensures students and evaluators can always complete a full case-taking flow.
    """
    msg_lower = patient_message.lower().strip()

    # 1. Check if patient has no concerns
    if any(phrase in msg_lower for phrase in ["no concern", "feel fine", "doing well", "feeling great", "nothing wrong", "no symptoms", "all good"]):
        return (
            "I'm glad to hear that you are feeling well today! Since you do not have any active health concerns to record, "
            "you can click 'End Consultation' at any time to finish, or let me know if you would like to document a routine checkup."
        )

    # Count how many patient messages were in history before this one
    previous_patient_turns = sum(1 for m in history if m.get("sender_role") == "patient")

    # Structured clinical question progression
    intake_steps = [
        # Turn 1 (0 previous): Duration & Onset
        "Thank you for sharing that. Approximately how long have you been experiencing this, and did it start suddenly or gradually?",
        # Turn 2 (1 previous): Severity & Character
        "On a scale of 1 to 10 (with 1 being very mild and 10 being the most severe), how would you rate the intensity, and could you describe what it feels like?",
        # Turn 3 (2 previous): Associated symptoms
        "Are you noticing any other symptoms alongside this, such as fever, fatigue, headaches, or nausea?",
        # Turn 4 (3 previous): Past medical history
        "Do you have any existing chronic conditions or past medical diagnoses (such as hypertension, asthma, diabetes)?",
        # Turn 5 (4 previous): Medications
        "Are you currently taking any prescription medications, over-the-counter drugs, or dietary supplements?",
        # Turn 6 (5 previous): Allergies
        "Do you have any known allergies to medications, foods, or environmental factors?",
        # Turn 7 (6 previous): Family History
        "Is there any relevant medical history in your immediate family related to these concerns?",
        # Turn 8 (7+ previous): Wrap-up & Summary
        "Thank you for providing this detailed health information. I have documented your chief concern, symptoms, medications, and medical background. "
        "Whenever you are ready, please click 'Finish Consultation' to proceed to your structured 11-section patient note."
    ]

    step_index = min(previous_patient_turns, len(intake_steps) - 1)
    return intake_steps[step_index]



async def generate_gemini_response(
    api_key: str,
    model: str,
    history: List[Dict[str, str]],
    patient_message: str
) -> str:
    """Call Google Gemini REST API via httpx."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

    # Build conversation transcript for context
    transcript = SYSTEM_PROMPT + "\n\nCONVERSATION HISTORY:\n"
    for msg in history:
        role = "Patient" if msg["sender_role"] == "patient" else "DocuMedi AI"
        transcript += f"{role}: {msg['message_content']}\n"
    transcript += f"Patient: {patient_message}\nDocuMedi AI:"

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": transcript}]
            }
        ],
        "generationConfig": {
            "temperature": 0.4,
            "maxOutputTokens": 600,
        }
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        candidates = data.get("candidates", [])
        if candidates and "content" in candidates[0]:
            parts = candidates[0]["content"].get("parts", [])
            if parts and "text" in parts[0]:
                return parts[0]["text"].strip()
        raise ValueError("Malformed response format received from Gemini API.")


async def generate_openai_response(
    api_key: str,
    model: str,
    history: List[Dict[str, str]],
    patient_message: str
) -> str:
    """Call OpenAI REST API via httpx."""
    url = "https://api.openai.com/v1/chat/completions"

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for msg in history:
        role = "user" if msg["sender_role"] == "patient" else "assistant"
        messages.append({"role": role, "content": msg["message_content"]})
    messages.append({"role": "user", "content": patient_message})

    payload = {
        "model": model or "gpt-4o-mini",
        "messages": messages,
        "temperature": 0.4,
        "max_tokens": 500,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()


async def process_patient_message(
    history: List[Dict[str, str]],
    patient_message: str
) -> Tuple[str, bool, str, Optional[str]]:
    """
    Main dispatch method:
    Returns (ai_response_text, is_live_ai, ai_provider_name, system_notice)
    """
    is_emergency = detect_emergencies(patient_message)
    provider, api_key, model = get_ai_config()

    ai_text = None
    is_live = False
    provider_name = provider
    system_notice = None

    if api_key:
        try:
            if provider == "gemini":
                ai_text = await generate_gemini_response(api_key, model, history, patient_message)
                is_live = True
                provider_name = f"Google Gemini ({model})"
            elif provider == "openai":
                ai_text = await generate_openai_response(api_key, model, history, patient_message)
                is_live = True
                provider_name = f"OpenAI ({model})"
            else:
                system_notice = f"Unsupported provider '{provider}'. Running DocuMedi Clinical Intake Engine."
        except Exception as e:
            system_notice = f"AI Provider connection issue: {str(e)[:120]}. Reverted safely to Clinical Intake Engine."

    # If live AI is unconfigured or failed, use rule-based clinical progression
    if not ai_text:
        ai_text = generate_rules_fallback_response(history, patient_message)
        is_live = False
        if not api_key:
            provider_name = "clinical_intake_rules"
            system_notice = "Notice: Live AI API key is not configured in backend/.env. Running DocuMedi Clinical Intake Engine."

    # Append emergency warning if red flag symptoms were detected
    if is_emergency:
        ai_text = ai_text + EMERGENCY_WARNING

    return ai_text, is_live, provider_name, system_notice
