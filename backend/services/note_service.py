"""
note_service.py — Structured Clinical Note Generation Service for DocuMedi.

Converts conversation dialogue into a structured 11-section patient note:
1. Chief Complaint
2. HPI
3. Past Medical History
4. Medications
5. Allergies
6. Family History
7. Social History
8. Review of Systems
9. Physical Examination
10. Assessment and Plan
11. Follow-up

Adheres strictly to medical safety:
- Never invents patient symptoms, dates, medications, or findings.
- Retains all cumulative symptoms and details reported across the entire dialogue.
- Physical examination is always set to:
  'Not performed — information not collected during the patient conversation'
- Assessment & Plan neutrally summarizes concerns and advises professional evaluation.
- Follow-up recommends physician review without inventing calendar dates.
"""

import json
import re
from typing import List, Dict, Tuple, Optional
import httpx
from services.conversation_service import get_ai_config
from services.clinical_tracker import build_clinical_state_from_history, ClinicalDialogueState

NOTE_SYSTEM_PROMPT = """
You are the DocuMedi Clinical Documentation Engine.
Your task is to synthesize the patient-reported conversation dialogue into a structured 11-section Clinical Patient Note.

CRITICAL INSTRUCTIONS & MEDICAL SAFETY RULES:
1. Extract ONLY facts explicitly reported by the patient in the dialogue.
2. DO NOT invent, assume, or hallucinate ANY details (no made-up vitals, lab values, symptoms, medications, or dates).
3. If information for a section was not discussed or not provided by the patient, write EXACTLY: "Not provided".
4. For Physical Examination, write EXACTLY:
   "Not performed — information not collected during the patient conversation"
5. For Assessment and Plan:
   Neutrally summarize the reported symptoms. Explicitly state that definitive clinical assessment and treatment require a qualified healthcare professional. Do NOT give a definitive diagnosis. Do NOT prescribe medication.
6. For Follow-up:
   Recommend consulting a qualified healthcare professional or seeking urgent care if symptoms worsen. Do NOT invent a calendar appointment date.
7. For Medications:
   - If the patient reported medications, preserve exact names, dosages, frequencies, and details reported.
   - If the patient explicitly denied medications, write: "None reported".
   - If the patient reported uncertainty, write: "Uncertain".
   - If medications were not discussed or not provided, write EXACTLY: "Not provided". Never write "No" or "None".
8. For Allergies:
   - If the patient reported allergies, state the specific allergens reported.
   - If the patient explicitly denied known allergies, write: "No known drug allergies (NKDA)".
   - If the patient reported uncertainty, write: "Uncertain".
   - If allergies were not discussed or not provided, write EXACTLY: "Not provided". Never write "No" or "None".

You must return a valid, strictly formatted JSON object with these EXACT 11 keys:
{
  "chief_complaint": "...",
  "hpi": "...",
  "past_medical_history": "...",
  "medications": "...",
  "allergies": "...",
  "family_history": "...",
  "social_history": "...",
  "review_of_systems": "...",
  "physical_examination": "Not performed — information not collected during the patient conversation",
  "assessment_and_plan": "...",
  "follow_up": "..."
}
Return ONLY JSON without markdown fences.
"""


def extract_fallback_note(history: List[Dict[str, str]]) -> Dict[str, str]:
    """
    Synthesizes the entire consultation history into a structured 11-section patient note
    using cumulative ClinicalDialogueState tracking.
    
    Guarantees:
    - Never invents patient symptoms, dates, medications, or findings.
    - Preserves all cumulative symptoms and details reported throughout the consultation.
    - Sets missing sections explicitly to 'Not provided'.
    - Physical Examination is strictly set to:
      'Not performed — information not collected during the patient conversation'
    - Assessment and Plan neutrally summarizes concerns without diagnosing or prescribing.
    """
    state = build_clinical_state_from_history(history, "")

    patient_messages = [
        m["message_content"].strip()
        for m in history
        if m.get("sender_role") == "patient" and m.get("message_content")
    ]

    if not patient_messages and not state.symptoms:
        chief_complaint = "Patient reported no specific symptoms during consultation"
        hpi = "No symptoms or clinical history reported by patient during consultation."
    else:
        # 1. Chief Complaint: Reflects all reported symptoms
        if state.symptoms:
            sym_list = list(state.symptoms)
            if len(sym_list) == 1:
                cc = f"{sym_list[0].capitalize()}"
            elif len(sym_list) == 2:
                cc = f"{sym_list[0].capitalize()} and {sym_list[1]}"
            else:
                cc = f"{', '.join(sym_list[:-1]).capitalize()}, and {sym_list[-1]}"
            if state.location and state.location.lower() not in cc.lower():
                cc += f" ({state.location})"
            chief_complaint = cc
        else:
            chief_complaint = patient_messages[0]

        # 2. HPI Narrative: Comprehensive synthesis of dialogue
        hpi_parts = []
        pres_items = []
        if state.symptoms:
            pres_items.append(f"Patient reports {', '.join(state.symptoms)}")
        else:
            pres_items.append(f"Patient presents with: {patient_messages[0]}")
        
        if state.location:
            pres_items.append(f"in the {state.location}")
        if state.onset_duration:
            pres_items.append(f"persisting for {state.onset_duration}")
        if state.character:
            pres_items.append(f"described as {state.character}")
        if state.severity:
            pres_items.append(f"rated at {state.severity}")

        hpi_parts.append(" ".join(pres_items) + ".")

        if state.relieving_aggravating:
            ra = state.relieving_aggravating.strip()
            if ra.lower().startswith(("symptoms are", "aggravated", "relieved", "home remedies", "worse", "better", "none identified")):
                hpi_parts.append(f"{ra.capitalize()}.")
            else:
                hpi_parts.append(f"Relieving or aggravating factors: {ra}.")

        if state.medications and state.medications not in ("None reported", "Not provided", "Uncertain", "Unknown", "Not sure"):
            hpi_parts.append(f"Current medication or treatment used: {state.medications}.")
        elif state.medications == "None reported":
            hpi_parts.append("Patient denies taking medications for these symptoms.")
        elif state.medications in ("Uncertain", "Unknown", "Not sure"):
            hpi_parts.append("Current medication usage is uncertain.")

        if state.allergies and state.allergies not in ("No known drug allergies (NKDA)", "Not provided", "Uncertain", "Unknown", "Not sure"):
            hpi_parts.append(f"Reported allergies: {state.allergies}.")
        elif state.allergies == "No known drug allergies (NKDA)":
            hpi_parts.append("Patient denies known drug or food allergies.")
        elif state.allergies in ("Uncertain", "Unknown", "Not sure"):
            hpi_parts.append("Known allergy status is uncertain.")

        if state.negative_symptoms:
            hpi_parts.append(f"Patient explicitly denies {', '.join(state.negative_symptoms)}.")

        # Additional patient context
        if len(patient_messages) > 1:
            hpi_parts.append(f"Clinical details gathered across {len(patient_messages)} consultation turns.")

        hpi = " ".join(hpi_parts)

    pmh = state.past_medical_history if state.past_medical_history else "Not provided"
    meds = state.medications if state.medications else "Not provided"
    allergies = state.allergies if state.allergies else "Not provided"
    fam = state.family_history if state.family_history else "Not provided"
    social = state.social_history if state.social_history else "Not provided"

    ros_items = []
    if state.symptoms:
        ros_items.append(f"Positive for: {', '.join(state.symptoms)}")
    if state.negative_symptoms:
        ros_items.append(f"Negative for: {', '.join(state.negative_symptoms)}")
    ros = ". ".join(ros_items) + "." if ros_items else "Review of systems documented based on consultation dialogue."

    pe = "Not performed — information not collected during the patient conversation"

    assessment = (
        f"Patient reports {chief_complaint.lower().rstrip('.')}. "
        "Clinical assessment and treatment planning require in-person evaluation by a qualified medical professional. "
        "DocuMedi provides clinical intake documentation and does not render definitive medical diagnoses or prescribe medications."
    )

    follow_up = (
        "Consult a qualified healthcare provider or primary care physician for clinical evaluation. "
        "If red flag symptoms develop or existing symptoms worsen significantly, seek emergency medical care immediately."
    )

    return {
        "chief_complaint": chief_complaint,
        "hpi": hpi,
        "past_medical_history": pmh,
        "medications": meds,
        "allergies": allergies,
        "family_history": fam,
        "social_history": social,
        "review_of_systems": ros,
        "physical_examination": pe,
        "assessment_and_plan": assessment,
        "follow_up": follow_up
    }


def clean_json_response(raw_text: str) -> Optional[dict]:
    """Parse JSON safely from raw LLM output, stripping markdown fences if present."""
    text = raw_text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except Exception:
        pass

    # Try regex match for JSON object
    match = re.search(r"(\{.*\})", text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(1))
            if isinstance(data, dict):
                return data
        except Exception:
            pass

    return None


async def generate_note_from_dialogue(
    case_title: str,
    history: List[Dict[str, str]]
) -> Tuple[Dict[str, str], bool, str, Optional[str]]:
    """
    Main note generation dispatcher.
    Returns: (note_dict, is_live_ai, ai_provider_name, system_notice)
    """
    provider, api_key, model = get_ai_config()

    note_data = None
    is_live = False
    provider_name = provider
    system_notice = None

    # Format transcript
    transcript = f"Case Title: {case_title}\n\nCONVERSATION DIALOGUE:\n"
    for msg in history:
        role = "Patient" if msg.get("sender_role") == "patient" else "DocuMedi AI"
        transcript += f"{role}: {msg.get('message_content')}\n"

    if api_key:
        try:
            if provider == "gemini":
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
                payload = {
                    "contents": [
                        {"role": "user", "parts": [{"text": NOTE_SYSTEM_PROMPT + "\n\n" + transcript}]}
                    ],
                    "generationConfig": {
                        "temperature": 0.2,
                        "response_mime_type": "application/json"
                    }
                }
                async with httpx.AsyncClient(timeout=20.0) as client:
                    res = await client.post(url, json=payload)
                    res.raise_for_status()
                    cand = res.json().get("candidates", [])
                    if cand and "content" in cand[0]:
                        parts = cand[0]["content"].get("parts", [])
                        if parts and "text" in parts[0]:
                            note_data = clean_json_response(parts[0]["text"])
                            if note_data:
                                is_live = True
                                provider_name = f"Google Gemini ({model})"

            elif provider == "openai":
                url = "https://api.openai.com/v1/chat/completions"
                payload = {
                    "model": model or "gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": NOTE_SYSTEM_PROMPT},
                        {"role": "user", "content": transcript}
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.2
                }
                headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
                async with httpx.AsyncClient(timeout=20.0) as client:
                    res = await client.post(url, json=payload, headers=headers)
                    res.raise_for_status()
                    content = res.json()["choices"][0]["message"]["content"]
                    note_data = clean_json_response(content)
                    if note_data:
                        is_live = True
                        provider_name = f"OpenAI ({model})"
        except Exception as e:
            system_notice = f"Live AI generation failed ({str(e)[:80]}). Safely structured note using Clinical Intake Engine."

    # Fallback to cumulative clinical parser if no API key or if provider call failed
    if not note_data:
        note_data = extract_fallback_note(history)
        is_live = False
        if not api_key:
            provider_name = "clinical_intake_rules"
            system_notice = "Notice: Live AI API key is not configured in backend/.env. Note generated with DocuMedi Clinical Intake Engine."

    # Validate and enforce standard clinical keys
    required_keys = [
        "chief_complaint",
        "hpi",
        "past_medical_history",
        "medications",
        "allergies",
        "family_history",
        "social_history",
        "review_of_systems",
        "physical_examination",
        "assessment_and_plan",
        "follow_up",
    ]

    sanitized_note = {}
    for key in required_keys:
        val = note_data.get(key)
        if not val or not str(val).strip():
            val = "Not provided"
        sanitized_note[key] = str(val).strip()

    # Normalize single-word negative boolean-like fallbacks if returned by external LLM
    if sanitized_note.get("medications", "").strip().lower() in ("no", "none", "nil", "false", "n/a", "na"):
        sanitized_note["medications"] = "None reported"
    if sanitized_note.get("allergies", "").strip().lower() in ("no", "none", "nil", "false", "n/a", "na"):
        sanitized_note["allergies"] = "No known drug allergies (NKDA)"

    # Safety enforcement: Physical Examination must never be invented
    sanitized_note["physical_examination"] = "Not performed — information not collected during the patient conversation"

    return sanitized_note, is_live, provider_name, system_notice
