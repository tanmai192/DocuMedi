"""
conversation_service.py — Conversational AI and Clinical Case-Taking Service for DocuMedi.

Handles:
1. Initial clinical intake greeting.
2. Empathetic, dynamic conversation progression (Gemini / OpenAI REST API via httpx).
3. Cumulative clinical state tracking so patients never have to repeat information.
4. Red flag emergency symptom detection and urgent care notices.
5. Adaptive clinical intake rules engine when API key is unconfigured or unavailable.
6. Server-side medical guardrails (no diagnosis, no prescription).
"""

import os
import re
from typing import List, Dict, Tuple, Optional
import httpx
from dotenv import load_dotenv

from services.clinical_tracker import (
    build_clinical_state_from_history,
    generate_empathetic_acknowledgment,
    generate_adaptive_follow_up_questions,
    is_relief_or_aggravating_question,
    ClinicalDialogueState
)

load_dotenv()

INITIAL_GREETING = (
    "Hello! Welcome to DocuMedi. How are you feeling today? "
    "Please describe any health concerns you would like to document."
)

SYSTEM_PROMPT = """
You are the DocuMedi Clinical Case-Taking Assistant.
DocuMedi is an intelligent, compassionate patient intake documentation assistant for personal medical record-keeping.

YOUR MISSION:
Conduct a warm, natural, empathetic, and human-like clinical intake conversation. Help the patient articulate their health story while making them feel genuinely heard, respected, and understood.

CORE CLINICAL & CONVERSATIONAL PRINCIPLES:
1. EMPATHY & ACTIVE LISTENING:
   - Always warmly acknowledge each patient message and validate their distress or discomfort.
   - Avoid rigid, robotic, or overly scripted replies. Speak with the warmth, attentiveness, and calm reassurance of an experienced healthcare professional.

2. CUMULATIVE MEMORY & SYMPTOM CONNECTION:
   - Remember ALL symptoms, answers, medications, and details the patient has mentioned throughout the consultation.
   - When a patient introduces a new symptom midway through (even while discussing another topic), immediately recognize it, validate it, and connect it with their prior symptoms (e.g., "I'm so sorry you're feeling nauseous on top of the headache you mentioned").

3. ADAPTIVE FOLLOW-UP INQUIRIES:
   - Ask only ONE or TWO relevant follow-up questions at a time.
   - NEVER make the patient repeat information they have already provided (such as duration, severity, medications, or allergies).
   - Tailor your next inquiry dynamically to what is still missing from the clinical picture (onset, duration, severity on 1-10 scale, character, relieving/aggravating factors, medications, allergies, medical history).

4. PATIENT AUTONOMY:
   - Allow patients to describe multiple symptoms together or change topics naturally.
   - Never interrogate or force an answer. If they are unsure or skip a question, move forward gently.

5. CONCLUDING THE CONSULTATION:
   - When key clinical details have been gathered, summarize the picture neutrally and kindly invite them to click "Finish Consultation" to review their structured 11-section note, or share any remaining details.

6. ABSOLUTE MEDICAL SAFETY RESTRICTIONS:
   - You are an intake documentation assistant, NOT a physician. NEVER diagnose medical conditions or speculate on a specific disease.
   - NEVER prescribe medications, recommend treatments, or suggest dosage changes.
   - For severe red flag emergencies (crushing chest pain, severe shortness of breath, sudden facial drooping or weakness, massive bleeding), instruct the patient IMMEDIATELY to call 112 (or 108 for ambulance services in India) or visit the nearest emergency department without delay.
"""

# Configurable emergency guidance (Defaults to India: 112 primary, 108 ambulance)
EMERGENCY_COUNTRY = os.getenv("EMERGENCY_COUNTRY", "India").strip()
PRIMARY_EMERGENCY_NUMBER = os.getenv("PRIMARY_EMERGENCY_NUMBER", "112").strip()
AMBULANCE_EMERGENCY_NUMBER = os.getenv("AMBULANCE_EMERGENCY_NUMBER", "108").strip()

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
    f"\n\n⚠️ **URGENT MEDICAL NOTICE:** Based on the symptoms you reported, this may be a medical emergency. "
    f"If you are experiencing a life-threatening emergency in {EMERGENCY_COUNTRY}, call {PRIMARY_EMERGENCY_NUMBER} immediately "
    f"(or {AMBULANCE_EMERGENCY_NUMBER} for ambulance services) or visit the nearest emergency department without delay. "
    f"Do not wait for online documentation."
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
    Active listening, empathetic clinical intake engine used when live AI API is unconfigured or unavailable.
    Remembers previously reported symptoms, acknowledges new symptoms introduced midway,
    adapts follow-up questions dynamically, mirrors patient answers, and never repeats answered questions.
    """
    msg_lower = patient_message.lower().strip()

    # 1. Check if patient has no concerns
    if any(phrase in msg_lower for phrase in ["no concern", "feel fine", "doing well", "feeling great", "nothing wrong", "no symptoms", "all good"]):
        return (
            "I'm glad to hear that you are feeling well today! Since you do not have any active health concerns to record, "
            "you can click 'Finish Consultation' at any time to conclude, or let me know if you would like to document a routine checkup."
        )

    # Find the most recent AI message from history
    last_ai_msg = None
    for msg in reversed(history):
        if msg.get("sender_role") == "ai":
            last_ai_msg = msg.get("message_content", "").strip()
            break

    # 2. Build cumulative clinical dialogue state across all history + current message
    state = build_clinical_state_from_history(history, patient_message)

    # 3. Active listening reflection reflecting patient's latest message and connecting symptoms
    ack = generate_empathetic_acknowledgment(state, patient_message)

    # 4. Adaptive follow-up question strictly tailored to remaining clinical unknowns
    question = generate_adaptive_follow_up_questions(state, last_ai_msg)

    response = f"{ack} {question}".strip()

    # 5. HARD REPETITION GUARD:
    # Under NO circumstances may the AI response be identical to the previous AI message or repeat a relief question!
    is_repeat = False
    if last_ai_msg:
        if response.lower() == last_ai_msg.lower() or question.lower() in last_ai_msg.lower():
            is_repeat = True
        elif is_relief_or_aggravating_question(last_ai_msg) and is_relief_or_aggravating_question(question):
            is_repeat = True

    if is_repeat:
        alt_question = None
        if not state.medications:
            alt_question = "Are you currently taking any prescription medications, over-the-counter remedies, or supplements for this or other health conditions?"
        elif not state.allergies:
            alt_question = "Do you have any known allergies, especially to medications or foods?"
        elif not state.past_medical_history:
            alt_question = "Do you have any personal medical history, chronic conditions, or family history related to these concerns?"
        else:
            alt_question = "Is there anything else you would like to include before we finalize your consultation note?"

        if any(w in msg_lower for w in ["no", "nope", "nah", "none"]):
            ack = "Understood, thank you for confirming that."

        response = f"{ack} {alt_question}".strip()

    return response


def format_clinical_state_context(state: ClinicalDialogueState) -> str:
    """Formats cumulative clinical memory and strict non-repetition rules for LLMs."""
    return f"""
CURRENT CUMULATIVE PATIENT STATE:
- Active Reported Symptoms: {', '.join(state.symptoms) if state.symptoms else 'None identified yet'}
- Newly Introduced in Latest Message: {', '.join(state.new_symptoms_in_turn) if state.new_symptoms_in_turn else 'None'}
- Denied/Negative Symptoms: {', '.join(state.negative_symptoms) if state.negative_symptoms else 'None'}
- Confirmed Clinical Details Already Provided by Patient:
  * Onset / Duration: {state.onset_duration or 'NOT ANSWERED'}
  * Severity / Pain Level: {state.severity or 'NOT ANSWERED'}
  * Character / Quality: {state.character or 'NOT ANSWERED'}
  * Anatomical Location: {state.location or 'NOT ANSWERED'}
  * Relieving / Aggravating Factors: {state.relieving_aggravating or 'NOT ANSWERED'}
  * Current Medications: {state.medications or 'NOT ANSWERED'}
  * Allergies: {state.allergies or 'NOT ANSWERED'}
  * Medical / Family History: {state.past_medical_history or state.family_history or 'NOT ANSWERED'}

STRICT DIALOGUE RULES FOR YOUR RESPONSE:
1. ACTIVE LISTENING: Briefly acknowledge or reflect what the patient JUST stated in their latest message.
2. NEVER RE-ASK ANY CONFIRMED DETAILS:
   - If Onset/Duration is confirmed ({state.onset_duration}), NEVER ask when it started or how long it has lasted.
   - If Severity is confirmed ({state.severity}), NEVER ask for a 1-10 rating, severity, or discomfort level.
   - If Character is confirmed ({state.character}), NEVER ask what it feels like or if it's dry/mucus.
   - If Relieving/Aggravating Factors are confirmed ({state.relieving_aggravating}), NEVER ask what makes it better or worse, or what provides relief.
   - If Medications are confirmed ({state.medications}), NEVER ask if they take medications.
   - If Allergies are confirmed ({state.allergies}), NEVER ask about allergies.
3. NEW SYMPTOMS: If a new symptom was mentioned, warmly acknowledge it and explore how it connects to earlier symptoms.
4. Ask ONLY ONE relevant next question focusing strictly on what is still marked 'NOT ANSWERED' above.
"""


async def generate_gemini_response(
    api_key: str,
    model: str,
    history: List[Dict[str, str]],
    patient_message: str
) -> str:
    """Call Google Gemini REST API via httpx with cumulative clinical memory."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

    state = build_clinical_state_from_history(history, patient_message)
    state_context = format_clinical_state_context(state)

    # Build conversation transcript for context
    transcript = SYSTEM_PROMPT + "\n\n" + state_context + "\n\nCONVERSATION HISTORY:\n"
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
    """Call OpenAI REST API via httpx with cumulative clinical memory."""
    url = "https://api.openai.com/v1/chat/completions"

    state = build_clinical_state_from_history(history, patient_message)
    state_context = format_clinical_state_context(state)

    messages = [{"role": "system", "content": SYSTEM_PROMPT + "\n\n" + state_context}]
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

    # If live AI is unconfigured or failed, use empathetic clinical intake engine
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
