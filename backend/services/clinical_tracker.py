"""
clinical_tracker.py — Clinical State Tracker and Dialogue Intelligence for DocuMedi.

Maintains a cumulative, structured representation of all symptoms, clinical attributes,
medications, allergies, and history throughout a patient consultation. Enables natural,
listening-based dialogue that actively acknowledges the patient's answers, adapts
questions dynamically to missing clinical details, and never repeats answered questions.
"""

import re
from typing import List, Dict, Set, Optional, Tuple


# Comprehensive symptom lexicon with regex patterns (including common typos and phrasing)
SYMPTOM_LEXICON: Dict[str, List[str]] = {
    # Group 1 — Illnesses, Respiratory Symptoms, and Fever
    "cold": [
        r"\bcolds?\b", r"\bcommon\s+cold\b", r"\bhead\s+cold\b", r"\bcoryza\b"
    ],
    "cough": [
        r"\bcough(?:ing)?\b", r"\bcaugh\b", r"\bchesty\s+cough\b",
        r"\bdry\s+cough\b", r"\bhacking\s+cough\b"
    ],
    "fever": [
        r"\bfever(?:ish)?\b", r"\bhigh\s+temp(?:erature)?\b", r"\bchills\b",
        r"\bshivering\b", r"\bpyrexia\b", r"\belevated\s+temp(?:erature)?\b"
    ],
    "flu": [
        r"\bflu\b", r"\bflu[- ]like\b", r"\binfluenza\b"
    ],
    "suspected dengue": [
        r"\b(?:suspected\s+)?dengue\b", r"\bbreakbone\b"
    ],
    "suspected malaria": [
        r"\b(?:suspected\s+)?malaria\b"
    ],
    "chills": [
        r"\bchills\b", r"\bshivering\b", r"\brigors?\b"
    ],
    "sweating": [
        r"\bsweat(?:ing|s)?\b", r"\bnight\s+sweats?\b", r"\bdiaphoresis\b"
    ],
    "fatigue": [
        r"\bfatigue\b", r"\btired(?:ness)?\b", r"\bexhaust(?:ed|ion)\b",
        r"\bletharg(?:ic|y)\b", r"\bweakness\b"
    ],
    "sore throat": [
        r"\bsore\s+throat\b", r"\bthroat\b[^\.\,\;]{0,25}\b(?:sore|hurts?|pain|scratchy)",
        r"\bpainful\s+swallowing\b"
    ],
    "congestion": [
        r"\bcongestion\b", r"\bstuffy\s+nose\b", r"\brunny\s+nose\b",
        r"\bsneez(?:ing|e|es)\b", r"\bnasal\s+drip\b", r"\brhinorrhea\b"
    ],
    "sinus pressure": [
        r"\bsinus\b[^\.\,\;]{0,25}\b(?:pressure|pain|congestion)",
        r"\bfacial\s+pressure\b", r"\bcheek\s+pressure\b"
    ],
    "shortness of breath": [
        r"\bshort(?:ness)?\s+of\s+breath\b", r"\bdifficulty\s+breathing\b",
        r"\bbreathless(?:ness)?\b", r"\bwheez(?:ing|e)\b"
    ],
    "pain behind eyes": [
        r"\bpain\s+behind\s+(?:the\s+|my\s+)?eyes?\b", r"\bretro[- ]orbital\b",
        r"\bhurt(?:s|ing)?\s+behind\s+(?:the\s+|my\s+)?eyes?\b"
    ],

    # Group 2 — Pain, Aches, and Localized Discomfort
    "headache": [
        r"\bheadaches?\b", r"\bheadach\b", r"\bhead\b[^\.\,\;]{0,25}\bpain\b",
        r"\bmigraines?\b", r"\bhead\s+hurts?\b", r"\bhead\s+pounding\b"
    ],
    "body aches": [
        r"\bbody\s+aches?\b", r"\bmuscle\s+aches?\b", r"\bmyalgia\b",
        r"\baching\s+all\s+over\b", r"\baching\s+body\b", r"\bbody\s+pain\b",
        r"\baching\s+muscles?\b"
    ],
    "joint pain": [
        r"\bjoint\b[^\.\,\;]{0,25}\b(?:pain|swelling|stiff)",
        r"\barthr(?:itis|algia)\b", r"\bswollen\s+joints?\b", r"\bjoint\s+aches?\b"
    ],
    "back pain": [
        r"\bback\b[^\.\,\;]{0,25}\b(?:pain|stiff|ache|sore|spasm)",
        r"\bbackache\b", r"\blower\s+back\b", r"\bupper\s+back\b"
    ],
    "neck pain": [
        r"\bneck\b[^\.\,\;]{0,25}\b(?:pain|stiff|ache|sore)",
        r"\bstiff\b[^\.\,\;]{0,25}\bneck\b", r"\bneck\s+stiffness\b"
    ],
    "abdominal pain": [
        r"\b(?:stomach|abdominal|belly|gut)\b[^\.\,\;]{0,25}\b(?:pain|ache|cramps?|discomfort)"
    ],
    "chest pain": [
        r"\bchest\b[^\.\,\;]{0,25}\b(?:pain|tightness|pressure|discomfort|heaviness)"
    ],
    "localized pain": [
        r"\b(?:arm|leg|shoulder|hip|knee|elbow|foot|hand|wrist|ankle)\b[^\.\,\;]{0,25}\b(?:pain|hurts?|hurting|ache|aching|discomfort|sore|soreness|stiff|stiffness)\b"
    ],

    # Group 3 — Skin Rashes, Skin Infections, and Skin Changes
    "rash": [
        r"\brash(?:es)?\b", r"\bhives\b", r"\bwelts?\b", r"\beruption\b",
        r"\bskin\s+spots?\b", r"\bred\s+spots?\b"
    ],
    "itching": [
        r"\bitch(?:y|ing|iness)?\b", r"\bprurit(?:us|ic)\b", r"\bscratchy\s+skin\b"
    ],
    "skin redness / swelling": [
        r"\bredness\b", r"\bswollen\s+skin\b", r"\bskin\s+swelling\b",
        r"\berythema\b", r"\binflamed\s+skin\b"
    ],
    "suspected skin infection": [
        r"\b(?:suspected\s+)?skin\s+infection\b", r"\bcellulitis\b",
        r"\binfected\s+(?:skin|wound|sore|spot)\b", r"\babscess\b"
    ],
    "boils / blisters": [
        r"\bboils?\b", r"\bblisters?\b", r"\bpustules?\b", r"\blesions?\b",
        r"\bbulla[e]?\b"
    ],
    "scaling / peeling skin": [
        r"\bpeeling\b", r"\bscaling\b", r"\bflaking\b", r"\bflaky\s+skin\b",
        r"\bdesquamation\b"
    ],
    "pus / skin discharge": [
        r"\bpus\b", r"\booz(?:ing|e)\b", r"\bweeping\s+skin\b",
        r"\bdischarge\s+from\s+skin\b", r"\bdraining\s+pus\b"
    ],

    # Other Co-occurring / General Symptoms
    "nausea": [
        r"\bnausea\b", r"\bnauseous\b", r"\bqueas(?:y|iness)\b",
        r"\bfeel(?:ing)?\s+sick\b", r"\bstomach\b[^\.\,\;]{0,25}\bnauseous\b"
    ],
    "vomiting": [r"\bvomit(?:ing|ed)?\b", r"\bthrowing\s+up\b", r"\bthrew\s+up\b"],
    "dizziness": [r"\bdizz(?:y|iness)\b", r"\blightheaded(?:ness)?\b", r"\bvertigo\b", r"\bunsteady\b"],
    "diarrhea": [r"\bdiarrhea\b", r"\bloose\s+stools?\b", r"\bwatery\s+stools?\b"],
    "constipation": [r"\bconstipat(?:ed|ion)\b"],
    "light sensitivity / vision changes": [r"\blight\s+sensitiv(?:e|ity)\b", r"\bphotophobia\b", r"\bblurr(?:y|ed)\s+vision\b", r"\bvision\s+changes?\b"],
    "numbness or tingling": [r"\bnumb(?:ness)?\b", r"\btingling\b", r"\bpins\s+and\s+needles\b", r"\btingl(?:e|ing|y)\b"],
    "leg / knee symptoms": [r"\b(?:leg|knee)\b[^\.\,\;]{0,25}\b(?:weak|weakness|pain|aches?|tingling|hurt(?:s|ing)?|stiff(?:ness)?)"],
    "insomnia / sleep disturbance": [r"\binsomnia\b", r"\btrouble\s+sleeping\b", r"\bcan'?t\s+sleep\b", r"\bwaking\s+up\b"],
    "ear pain": [r"\bear\b[^\.\,\;]{0,25}\b(?:pain|ache|pressure)", r"\bearache\b", r"\btinnitus\b", r"\bclogged\s+ears?\b"],
}

# Symptom Groups definition
GROUP_1_ID = "group_1"  # Illnesses, Respiratory Symptoms, and Fever
GROUP_2_ID = "group_2"  # Pain, Aches, and Localized Discomfort
GROUP_3_ID = "group_3"  # Skin Rashes, Skin Infections, and Skin Changes

GROUP_1_SYMPTOMS: Set[str] = {
    "cold", "cough", "fever", "flu", "suspected dengue", "suspected malaria",
    "chills", "sweating", "fatigue", "sore throat", "congestion",
    "sinus pressure", "shortness of breath", "pain behind eyes"
}

GROUP_2_SYMPTOMS: Set[str] = {
    "headache", "body aches", "joint pain", "back pain", "neck pain",
    "abdominal pain", "chest pain", "localized pain"
}

GROUP_3_SYMPTOMS: Set[str] = {
    "rash", "itching", "skin redness / swelling", "suspected skin infection",
    "boils / blisters", "scaling / peeling skin", "pus / skin discharge"
}


def detect_symptom_groups(symptoms: Set[str], raw_text: str = "") -> Set[str]:
    """Detects which of the 3 symptom groups are active from symptoms and message context."""
    groups: Set[str] = set()
    text_lower = raw_text.lower() if raw_text else ""

    # Group 1 checks
    if any(s in GROUP_1_SYMPTOMS for s in symptoms):
        groups.add(GROUP_1_ID)
    elif any(re.search(rf"\b{w}\b", text_lower) for w in ["cold", "cough", "fever", "flu", "dengue", "malaria", "chills", "sweats", "phlegm", "mucus", "sneeze", "sneezing", "runny nose"]):
        groups.add(GROUP_1_ID)

    # Group 2 checks
    if any(s in GROUP_2_SYMPTOMS for s in symptoms):
        groups.add(GROUP_2_ID)
    elif any(re.search(rf"\b{w}\b", text_lower) for w in ["pain", "hurt", "hurts", "hurting", "ache", "aches", "aching", "headache", "migraine", "stiff", "stiffness", "cramp", "cramping", "throbbing", "sharp"]):
        groups.add(GROUP_2_ID)

    # Group 3 checks
    if any(s in GROUP_3_SYMPTOMS for s in symptoms):
        groups.add(GROUP_3_ID)
    elif any(re.search(rf"\b{w}\b", text_lower) for w in ["rash", "rashes", "itch", "itchy", "itching", "spots", "bumps", "blister", "blisters", "boil", "boils", "peeling", "skin infection", "pus", "oozing"]):
        groups.add(GROUP_3_ID)

    return groups


# Negation patterns to distinguish "no fever" from "fever"
NEGATION_REGEX = re.compile(
    r"\b(?:no|not|none|denies|denying|without|never\s+had|don'?t\s+have|haven'?t\s+had)\s+(?:a\s+|any\s+|much\s+)?([a-z\s]{3,30})\b",
    re.IGNORECASE
)

# Colloquial denial patterns (matches 'no', 'noo', 'nooo', 'nah', 'nope', 'nil', etc.)
DENIAL_PREFIX_REGEX = re.compile(
    r"^(?:no+|nah+|nope+|not\s+really|not\s+at\s+all|none|nothing|neither|negative|nil|don'?t\s+have|haven'?t\s+noticed|haven'?t\s+had|not\s+experiencing|i\s+don'?t|i\s+haven'?t|no\s+i\s+don'?t|no\s+i\s+haven'?t|no\s+none)\b",
    re.IGNORECASE
)


def normalize_patient_text(text: str) -> str:
    """
    Normalizes colloquial and informal patient phrasing:
    - Strips leading/trailing whitespace.
    - Collapses elongated repeated characters (e.g. 'noo', 'nooo' -> 'no', 'yesss' -> 'yes', 'soooo' -> 'so').
    - Normalizes common informal slang and affirmations/denials.
    """
    if not text:
        return ""
    cleaned = text.strip()
    # Normalize elongated vowels/letters for common short answers
    cleaned = re.sub(r'^n+o+\b', 'no', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'^n+a+h+\b', 'nah', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'^n+o+p+e*\b', 'nope', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'^y+e+s+\b', 'yes', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'^y+e+a+h*\b', 'yeah', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'^y+e+p+\b', 'yep', cleaned, flags=re.IGNORECASE)
    # General repeated characters (3+ letters collapsed to 1)
    cleaned = re.sub(r'([a-zA-Z])\1{2,}', r'\1', cleaned)
    return cleaned


def get_last_question(text: Optional[str]) -> str:
    """
    Extracts the actual inquiry portion of an AI message.
    AI responses often begin with an active-listening acknowledgment reflecting
    previous patient answers (e.g. 'Understood, I have recorded that you are not currently taking any medications.').
    Extracting only the actual questions or final sentence prevents acknowledgments
    from polluting inquiry classification and duplicate detection.
    """
    if not text:
        return ""
    # Find all question sentences ending with '?'
    questions = re.findall(r'[^.!?\n]+(?:\?|$)', text)
    q_only = [q.strip() for q in questions if q.strip().endswith('?')]
    if q_only:
        return " ".join(q_only)
    # If no explicit '?', strip common acknowledgment prefixes
    cleaned = re.sub(
        r'^(?:Understood|Got it|Thank you|Thanks|I hear you|I\'m really sorry|I\'m sorry|I understand|I have noted)[^.!?\n]*[.!?]',
        '',
        text,
        flags=re.IGNORECASE
    ).strip()
    return cleaned or text


def is_relief_or_aggravating_question(text: Optional[str]) -> bool:
    """
    Identifies whether an AI inquiry asks if anything relieves, worsens,
    or triggers symptoms (or home remedies).
    """
    if not text:
        return False
    if is_final_confirmation_question(text):
        return False
    inquiry = get_last_question(text)
    lower = inquiry.lower()
    phrases = [
        "better or worse", "better, or worse", "worse, or better",
        "better and worse", "makes it worse", "make it worse",
        "makes them worse", "make them worse", "makes the symptoms feel",
        "make the symptoms feel", "feel better or worse",
        "provided relief", "provide relief", "brings relief", "bring relief",
        "helped provide relief", "helps relieve", "helped relieve",
        "helped so far", "trigger worse", "triggers worse", "triggers coughing",
        "warm tea or steam helped", "tea or steam helped",
        "bright lights, sound", "physical activity makes it worse"
    ]
    if any(p in lower for p in phrases):
        return True
    has_relieve_worse = any(w in lower for w in ["better", "worse", "relief", "relieve", "helped", "trigger"])
    has_question_context = any(w in lower for w in ["anything", "noticed", "tried", "makes", "make", "does", "have you", "what"])
    return has_relieve_worse and has_question_context


def is_final_confirmation_question(text: Optional[str]) -> bool:
    """
    Detect whether an AI inquiry asks whether the patient wants to include/add
    anything else before finalizing the consultation note or concludes intake.
    """
    if not text:
        return False
    t_lower = text.lower()
    if "before we finalize" in t_lower or "before finalizing" in t_lower:
        return True
    if "finalize your consultation" in t_lower or "finalize our consultation" in t_lower:
        return True
    if "anything else" in t_lower and any(w in t_lower for w in ["finalize", "consultation note", "finish", "conclude", "include", "add", "share", "mention", "tell", "discuss"]):
        return True
    if "finish consultation" in t_lower and any(w in t_lower for w in ["anything else", "other details", "share any", "feel free to share", "any other", "whenever you feel ready", "when you're ready", "would like to add"]):
        return True
    if any(p in t_lower for p in [
        "anything else you'd like to add", "anything else you would like to add",
        "anything else to add", "anything more to add",
        "any other symptoms or details you would like to share",
        "anything else you want to include", "anything else you would like to include"
    ]):
        return True
    return False


def is_final_completion_response(patient_message: str) -> bool:
    """
    Detect whether a patient gave a clear negative or completion response
    (e.g., 'no', 'nothing', 'nothing else', 'that's all', 'nothing more', 'I'm done')
    specifically to a final wrap-up confirmation inquiry.
    Must NOT trigger if the patient provided meaningful medical details (e.g. new symptoms or treatments).
    """
    if not patient_message:
        return False

    cleaned = patient_message.strip()
    lower = cleaned.lower()

    # Normalize: strip punctuation
    norm = re.sub(r"[^\w\s']", " ", lower).strip()
    norm = re.sub(r"\s+", " ", norm)

    # Check for known medical/symptom keywords or qualifiers that indicate real medical information
    medical_clues = [
        "pain", "hurt", "hurts", "ache", "aching", "cough", "coughing", "fever", "rash",
        "nausea", "vomit", "vomiting", "dizzy", "dizziness", "headache", "throat",
        "swelling", "swollen", "bleed", "bleeding", "burn", "burning", "chest", "breath",
        "breathing", "stomach", "ear", "ears", "eye", "eyes", "leg", "legs", "arm", "arms",
        "back", "knee", "knees", "shoulder", "shoulders", "mucus", "chills", "medication",
        "medications", "allergy", "allergies", "allergic", "pill", "tablet", "dose",
        "took", "taking", "started", "worse", "better", "mild", "severe", "except",
        "actually", "also have", "started to", "now have", "feeling"
    ]
    for word in medical_clues:
        if re.search(rf"\b{word}\b", norm):
            return False

    exact_phrases = {
        "no",
        "nope",
        "nah",
        "nothing",
        "nothing else",
        "nothing more",
        "nothing really",
        "nothing to add",
        "nothing else to add",
        "nothing to report",
        "nothing else to report",
        "that's all",
        "thats all",
        "that is all",
        "all done",
        "i'm done",
        "im done",
        "i am done",
        "no more",
        "all good",
        "no thank you",
        "no thanks",
        "nothing thanks",
        "nothing thank you",
        "no that's all",
        "no thats all",
        "no that is all",
        "no nothing else",
        "no nothing",
        "that would be all",
        "that will be all",
        "none",
        "none that's all",
    }

    if norm in exact_phrases:
        return True

    pattern = (
        r"^(?:no|nope|nah|nothing|nothing\s+else|that'?s\s+all|that\s+is\s+all|nothing\s+more|i'?m\s+done|i\s+am\s+done|all\s+done)"
        r"(?:\s+(?:thank\s+you|thanks|that'?s\s+all|that\s+is\s+all|nothing\s+else|i'?m\s+done))?[.!]?$"
    )
    return bool(re.match(pattern, norm))


UNCERTAINTY_PATTERNS = [
    r"\b(?:not\s+sure|i'?m\s+not\s+sure|unsure)\b",
    r"\b(?:don'?t\s+know|do\s+not\s+know|i\s+don'?t\s+know)\b",
    r"\b(?:uncertain|unknown)\b",
    r"\b(?:can'?t\s+remember|cannot\s+remember|don'?t\s+recall|can'?t\s+recall|cannot\s+recall)\b",
    r"\b(?:not\s+certain|no\s+idea)\b",
]


def is_uncertain_response(text: str) -> bool:
    """Detect whether patient expressed uncertainty (e.g. 'I'm not sure', 'uncertain', 'don't know')."""
    if not text:
        return False
    lower = text.lower().strip()
    return any(re.search(pat, lower) for pat in UNCERTAINTY_PATTERNS)


def is_allergy_question(text: Optional[str]) -> bool:
    """
    Detect whether an AI inquiry specifically asked about allergies.
    Must return True even if the inquiry includes examples like 'allergies to medications or foods'.
    Must return False for final confirmation inquiries.
    """
    if not text:
        return False
    if is_final_confirmation_question(text):
        return False
    inquiry = get_last_question(text)
    lower = inquiry.lower()
    return bool(re.search(r"\b(?:allerg(?:y|ies|ic)?|nkda)\b", lower))


def is_medication_question(text: Optional[str]) -> bool:
    """
    Detect whether an AI inquiry specifically asked about medications taken.
    Must NOT trigger on allergy questions (e.g. 'known allergies, especially to medications or foods').
    Must return False for final confirmation inquiries and relief/remedy inquiries.
    """
    if not text:
        return False
    if is_final_confirmation_question(text):
        return False
    if is_relief_or_aggravating_question(text):
        return False
    inquiry = get_last_question(text)
    lower = inquiry.lower()
    if any(w in lower for w in ["better or worse", "make the pain better", "makes it better", "home remedies", "applied any creams", "ointments", "warm tea or steam"]):
        return False
    if bool(re.search(r"\ballerg", lower)):
        # If the inquiry mentions allergies, only classify as a medication question
        # if it explicitly and separately inquires about currently taken medications.
        if not re.search(r"\b(?:taking|prescribed|taking\s+any)\s+(?:prescription\s+)?medications?\b", lower):
            return False
    return bool(re.search(r"\b(?:prescription\s+medications?|medications?|over-the-counter|supplements?|currently\s+taking\s+any)\b", lower))


def clean_medication_input(raw: str) -> str:
    """Clean conversational filler while strictly preserving drug names, dosages, frequencies, and phrasing."""
    cleaned = raw.strip()
    cleaned = re.sub(
        r"^(?:i\s+(?:also\s+)?(?:take|am\s+taking|'m\s+taking|took|use|am\s+using|'m\s+using|am\s+on|'m\s+on|have\s+been\s+taking)|currently\s+taking|taking|just|i've\s+taken|i\s+have\s+taken)\s+",
        "",
        cleaned,
        flags=re.IGNORECASE
    ).strip()
    cleaned = re.sub(r"[.!?]+$", "", cleaned).strip()
    if cleaned and cleaned[0].islower():
        cleaned = cleaned[0].upper() + cleaned[1:]
    return cleaned


def clean_allergy_input(raw: str) -> str:
    """Clean conversational filler while strictly preserving allergen names, reactions, and phrasing."""
    cleaned = raw.strip()
    cleaned = re.sub(
        r"^(?:i\s+(?:am\s+|'m\s+)?(?:allergic\s+to|having\s+an\s+allergy\s+to)|allergy\s+to|allergies(?:\s+to)?|i\s+have\s+(?:an\s+)?allergy\s+to|i\s+have\s+allergies\s+to|allergic\s+with|just)\s+",
        "",
        cleaned,
        flags=re.IGNORECASE
    ).strip()
    cleaned = re.sub(r"[.!?]+$", "", cleaned).strip()
    if cleaned and cleaned[0].islower():
        cleaned = cleaned[0].upper() + cleaned[1:]
    return cleaned


def is_history_question(text: Optional[str]) -> bool:
    """
    Detect whether an AI inquiry specifically asked about past medical history or chronic conditions.
    Must return False for final confirmation inquiries and allergy-only questions.
    """
    if not text:
        return False
    if is_final_confirmation_question(text):
        return False
    inquiry = get_last_question(text)
    lower = inquiry.lower()
    return bool(re.search(r"\b(?:personal\s+medical\s+history|medical\s+history|chronic\s+conditions?|past\s+illness(?:es)?|underlying\s+conditions?|pre-existing\s+conditions?)\b", lower))


def clean_history_input(raw: str) -> str:
    """Clean conversational filler while strictly preserving condition names, diagnoses, and phrasing."""
    cleaned = raw.strip()
    cleaned = re.sub(
        r"^(?:i\s+(?:also\s+)?(?:have|had|was\s+diagnosed\s+with|suffer\s+from|'ve\s+had|am\s+diagnosed\s+with|got)|diagnosed\s+with|history\s+of|just|i\s+only\s+have|my\s+history\s+is)\s+",
        "",
        cleaned,
        flags=re.IGNORECASE
    ).strip()
    cleaned = re.sub(r"[.!?]+$", "", cleaned).strip()
    if cleaned and cleaned[0].islower():
        cleaned = cleaned[0].upper() + cleaned[1:]
    return cleaned


def is_temperature_question(text: Optional[str]) -> bool:
    if not text:
        return False
    inquiry = get_last_question(text).lower()
    return bool(re.search(r"\b(?:temperature|measured\s+(?:your\s+)?temp(?:erature)?|thermometer|what\s+was\s+it)\b", inquiry))


def is_cold_question(text: Optional[str]) -> bool:
    if not text:
        return False
    inquiry = get_last_question(text).lower()
    return bool(re.search(r"\b(?:runny\s+nose|blocked\s+nose|stuffy\s+nose|sneez(?:ing|e)|sore\s+throat)\b", inquiry))


def is_cough_nature_question(text: Optional[str]) -> bool:
    if not text:
        return False
    inquiry = get_last_question(text).lower()
    return bool(re.search(r"\b(?:dry\s+or\s+productive|cough\s+dry|mucus\s+look\s+like|bringing\s+up\s+any\s+mucus|bringing\s+up\s+mucus|phlegm)\b", inquiry))


def is_systemic_question(text: Optional[str]) -> bool:
    if not text:
        return False
    inquiry = get_last_question(text).lower()
    return bool(re.search(r"\b(?:chills,\s+sweating|sweating,\s+fatigue|fatigue,\s+or\s+weakness|chills\s+or\s+sweat)\b", inquiry))


def is_associated_aches_question(text: Optional[str]) -> bool:
    if not text:
        return False
    inquiry = get_last_question(text).lower()
    return bool(re.search(r"\b(?:headache,\s+body\s+aches|pain\s+behind\s+(?:your\s+|the\s+)?eyes?|retro[- ]orbital)\b", inquiry))


def is_infection_gi_rash_question(text: Optional[str]) -> bool:
    if not text:
        return False
    inquiry = get_last_question(text).lower()
    return bool(re.search(r"\b(?:nausea,\s+vomiting,\s+diarrhea|vomiting,\s+diarrhea,\s+or\s+a\s+rash)\b", inquiry))


def is_travel_exposure_question(text: Optional[str]) -> bool:
    if not text:
        return False
    inquiry = get_last_question(text).lower()
    return bool(re.search(r"\b(?:recently\s+travelled|travelled|exposed\s+to\s+someone|relevant\s+diagnosis)\b", inquiry))


def is_pain_location_question(text: Optional[str]) -> bool:
    if not text:
        return False
    inquiry = get_last_question(text).lower()
    return bool(re.search(r"\b(?:where\s+exactly\s+is\s+the\s+pain|radiate\s+or\s+spread|spread\s+anywhere\s+else)\b", inquiry))


def is_pain_character_question(text: Optional[str]) -> bool:
    if not text:
        return False
    inquiry = get_last_question(text).lower()
    return bool(re.search(r"\b(?:dull,\s+sharp,\s+throbbing|sharp,\s+dull,\s+aching|describe\s+what\s+the\s+(?:pain|sensation)\s+feels\s+like|throbbing,\s+burning,\s+or\s+cramping)\b", inquiry))


def is_pain_pattern_question(text: Optional[str]) -> bool:
    if not text:
        return False
    inquiry = get_last_question(text).lower()
    return bool(re.search(r"\b(?:constant,\s+or\s+does\s+it\s+come\s+and\s+go|constant\s+or\s+intermittent)\b", inquiry))


def is_prior_episodes_question(text: Optional[str]) -> bool:
    if not text:
        return False
    inquiry = get_last_question(text).lower()
    return bool(re.search(r"\b(?:similar\s+pain\s+in\s+the\s+past|similar\s+skin\s+issue\s+before|had\s+this\s+before)\b", inquiry))


def is_rash_location_spread_question(text: Optional[str]) -> bool:
    if not text:
        return False
    inquiry = get_last_question(text).lower()
    return bool(re.search(r"\b(?:where\s+on\s+your\s+body\s+did\s+the\s+(?:rash|skin)|first\s+appear,\s+and\s+has\s+it\s+spread)\b", inquiry))


def is_rash_sensation_question(text: Optional[str]) -> bool:
    if not text:
        return False
    inquiry = get_last_question(text).lower()
    return bool(re.search(r"\b(?:itchy,\s+painful,\s+warm,\s+burning|tender\s+to\s+the\s+touch)\b", inquiry))


def is_rash_appearance_question(text: Optional[str]) -> bool:
    if not text:
        return False
    inquiry = get_last_question(text).lower()
    return bool(re.search(r"\b(?:flat\s+red\s+spots|raised\s+bumps|blisters,\s+peeling|pus-filled|describe\s+its\s+appearance)\b", inquiry))


def is_skin_infection_check_question(text: Optional[str]) -> bool:
    if not text:
        return False
    inquiry = get_last_question(text).lower()
    return bool(re.search(r"\b(?:spreading\s+redness|warmth,\s+swelling,\s+pus)\b", inquiry))


def is_rash_triggers_question(text: Optional[str]) -> bool:
    if not text:
        return False
    inquiry = get_last_question(text).lower()
    return bool(re.search(r"\b(?:soaps,\s+lotions,\s+detergents|plants,\s+insects|new\s+soaps)\b", inquiry))


def is_remedies_question(text: Optional[str]) -> bool:
    if not text:
        return False
    inquiry = get_last_question(text).lower()
    return bool(re.search(r"\b(?:home\s+remedies|warm\s+tea\s+or\s+steam|creams,\s+ointments|tried\s+home\s+remedies)\b", inquiry))


class ClinicalDialogueState:
    """
    Cumulative clinical memory of the entire consultation.
    Tracks symptoms, clinical attributes, medications, and medical history.
    Also tracks turn-specific additions to enable active listening and reflection.
    """

    def __init__(self):
        self.symptoms: Set[str] = set()
        self.new_symptoms_in_turn: Set[str] = set()
        self.negative_symptoms: Set[str] = set()
        
        self.onset_duration: Optional[str] = None
        self.severity: Optional[str] = None
        self.character: Optional[str] = None
        self.location: Optional[str] = None
        self.relieving_aggravating: Optional[str] = None
        
        self.medications: Optional[str] = None
        self.allergies: Optional[str] = None
        self.past_medical_history: Optional[str] = None
        self.family_history: Optional[str] = None
        self.social_history: Optional[str] = None

        # Group-specific and contextual attributes
        self.symptom_groups: Set[str] = set()
        self.asked_topics: Set[str] = set()
        self.questions_asked: List[str] = []
        self.temperature: Optional[str] = None
        self.cold_symptoms: Optional[str] = None
        self.cough_nature: Optional[str] = None
        self.mucus_appearance: Optional[str] = None
        self.systemic_symptoms: Optional[str] = None
        self.associated_aches: Optional[str] = None
        self.infection_gi_rash: Optional[str] = None
        self.travel_exposure: Optional[str] = None
        self.suspected_conditions: Set[str] = set()
        self.pain_pattern: Optional[str] = None
        self.pain_radiation: Optional[str] = None
        self.prior_episodes: Optional[str] = None
        self.rash_appearance: Optional[str] = None
        self.rash_location: Optional[str] = None
        self.rash_spread: Optional[str] = None
        self.rash_sensation: Optional[str] = None
        self.rash_progression: Optional[str] = None
        self.triggers_exposure: Optional[str] = None

        # Turn-specific flags for the latest patient response
        self.turn_new_onset: bool = False
        self.turn_new_severity: bool = False
        self.turn_new_character: bool = False
        self.turn_new_location: bool = False
        self.turn_new_relieving_aggravating: bool = False
        self.turn_new_meds: bool = False
        self.turn_new_allergies: bool = False
        self.turn_new_history: bool = False
        self.turn_new_temperature: bool = False
        self.turn_new_cough_nature: bool = False
        self.turn_new_rash_details: bool = False
        self.turn_new_pain_details: bool = False
        self.turn_new_travel_exposure: bool = False
        self.turn_new_denials: Set[str] = set()
        self.turn_needs_clarification: Optional[str] = None

        self.patient_message_count: int = 0
        self.raw_patient_messages: List[str] = []
        self.last_asked_question: Optional[str] = None

    @property
    def is_cold_alone(self) -> bool:
        """True if patient reported cold without pain, high fever, or rash."""
        has_cold = "cold" in self.symptoms or any(s in self.symptoms for s in ["congestion", "sore throat"])
        has_pain = self.has_pain
        has_fever = "fever" in self.symptoms or "suspected dengue" in self.symptoms or "suspected malaria" in self.symptoms
        has_rash = "rash" in self.symptoms or "skin redness / swelling" in self.symptoms
        return has_cold and not (has_pain or has_fever or has_rash)

    @property
    def is_cough_alone(self) -> bool:
        """True if patient reported cough without fever, pain, or rash."""
        has_cough = "cough" in self.symptoms
        other_symptoms = self.symptoms - {"cough"}
        has_fever = "fever" in self.symptoms or "suspected dengue" in self.symptoms or "suspected malaria" in self.symptoms
        has_pain = self.has_pain
        has_rash = "rash" in self.symptoms or "skin redness / swelling" in self.symptoms
        return has_cough and not (has_fever or has_pain or has_rash) and len(other_symptoms) == 0

    @property
    def has_pain(self) -> bool:
        """True if patient reported actual pain or ache symptoms."""
        pain_syms = {"headache", "body aches", "joint pain", "back pain", "neck pain", "abdominal pain", "chest pain", "localized pain"}
        if any(s in pain_syms for s in self.symptoms):
            return True
        for msg in self.raw_patient_messages:
            low = msg.lower()
            if any(re.search(rf"\b{w}\b", low) for w in ["pain", "hurts", "ache", "aching", "headache", "migraine", "stiff neck", "soreness"]):
                if not any(re.search(rf"\b(?:no|denies|without|not\s+having)\s+{w}\b", low) for w in ["pain", "ache", "headache"]):
                    return True
        return False

    @property
    def has_itch_no_pain(self) -> bool:
        """True if patient has itchy rash/skin change and denies or has no pain."""
        has_rash_or_itch = bool(self.symptoms.intersection(GROUP_3_SYMPTOMS)) or any(
            any(re.search(rf"\b{w}\b", m.lower()) for w in ["rash", "itch", "itchy", "spots"])
            for m in self.raw_patient_messages
        )
        return has_rash_or_itch and not self.has_pain

    @property
    def has_fever(self) -> bool:
        return "fever" in self.symptoms or "suspected dengue" in self.symptoms or "suspected malaria" in self.symptoms

    @property
    def is_headache_alone(self) -> bool:
        """True if patient reported headache without other major systemic/rash complaints."""
        has_headache = "headache" in self.symptoms or any("headache" in m.lower() for m in self.raw_patient_messages)
        other_symptoms = self.symptoms - {"headache"}
        return has_headache and not (GROUP_1_ID in self.symptom_groups or GROUP_3_ID in self.symptom_groups) and len(other_symptoms) == 0

    @property
    def is_suspected_infection(self) -> bool:
        return bool(self.suspected_conditions or {"suspected dengue", "suspected malaria", "suspected skin infection"}.intersection(self.symptoms))

    @property
    def answered_dimensions(self) -> Set[str]:
        """Returns set of clinical dimensions that have been answered by the patient."""
        dims = set()
        if self.symptoms:
            dims.add("symptoms")
        if self.onset_duration:
            dims.add("onset")
            dims.add("duration")
        if self.severity:
            dims.add("severity")
        if self.character:
            dims.add("character")
        if self.location:
            dims.add("location")
        if self.relieving_aggravating:
            dims.add("relieving_aggravating")
        if self.medications:
            dims.add("medications")
        if self.allergies:
            dims.add("allergies")
        if self.past_medical_history or self.family_history:
            dims.add("history")
        if self.temperature:
            dims.add("temperature")
        if self.cold_symptoms:
            dims.add("cold_symptoms")
        if self.cough_nature:
            dims.add("cough_nature")
        if self.systemic_symptoms:
            dims.add("systemic_symptoms")
        if self.associated_aches:
            dims.add("associated_aches")
        if self.infection_gi_rash:
            dims.add("infection_gi_rash")
        if self.travel_exposure:
            dims.add("travel_exposure")
        if self.pain_pattern:
            dims.add("pain_pattern")
        if self.pain_radiation:
            dims.add("pain_radiation")
        if self.prior_episodes:
            dims.add("prior_episodes")
        if self.rash_appearance:
            dims.add("rash_appearance")
        if self.rash_sensation:
            dims.add("rash_sensation")
        if self.rash_spread:
            dims.add("rash_spread")
        if self.triggers_exposure:
            dims.add("triggers_exposure")
        return dims

    def ingest_turn(
        self,
        message: str,
        is_latest: bool = False,
        previous_ai_message: Optional[str] = None
    ):
        """Processes a patient message and updates the cumulative state."""
        cleaned = message.strip()
        if not cleaned:
            return
        
        self.patient_message_count += 1
        self.raw_patient_messages.append(cleaned)
        normalized = normalize_patient_text(cleaned)
        lower = cleaned.lower()
        norm_lower = normalized.lower()

        if is_latest:
            self.turn_new_onset = False
            self.turn_new_severity = False
            self.turn_new_character = False
            self.turn_new_location = False
            self.turn_new_relieving_aggravating = False
            self.turn_new_meds = False
            self.turn_new_allergies = False
            self.turn_new_history = False
            self.turn_new_temperature = False
            self.turn_new_cough_nature = False
            self.turn_new_rash_details = False
            self.turn_new_pain_details = False
            self.turn_new_travel_exposure = False
            self.turn_new_denials = set()
            self.turn_needs_clarification = None

        # Detect suspected conditions
        if re.search(r"\b(?:suspected\s+)?dengue\b", lower):
            self.suspected_conditions.add("dengue (suspected, patient-reported)")
            self.symptoms.add("suspected dengue")
        if re.search(r"\b(?:suspected\s+)?malaria\b", lower):
            self.suspected_conditions.add("malaria (suspected, patient-reported)")
            self.symptoms.add("suspected malaria")
        if re.search(r"\b(?:suspected\s+)?skin\s+infection\b", lower) or "cellulitis" in lower or "infected skin" in lower:
            self.suspected_conditions.add("skin infection (suspected, patient-reported)")
            self.symptoms.add("suspected skin infection")

        # 1. Extract Negated / Denied Symptoms first
        negated_terms = set()
        for match in NEGATION_REGEX.finditer(lower):
            negated_phrase = match.group(1).strip()
            for sym, patterns in SYMPTOM_LEXICON.items():
                if any(re.search(p, negated_phrase) for p in patterns):
                    negated_terms.add(sym)
                    self.negative_symptoms.add(sym)

        # 1b. Check if patient gave an informal or standalone denial response to previous AI inquiry
        is_pure_denial = (
            bool(DENIAL_PREFIX_REGEX.search(lower))
            or bool(DENIAL_PREFIX_REGEX.search(norm_lower))
            or norm_lower in {"no", "nope", "nah", "none", "neither", "nothing", "nil", "negative"}
            or lower in {"no", "noo", "nooo", "nope", "nah", "none", "neither", "nothing", "nil", "negative"}
        )
        if is_pure_denial and previous_ai_message and not is_final_confirmation_question(previous_ai_message):
            prev_lower = previous_ai_message.lower()
            denied_candidates = [
                ("fever", ["fever", "high temp", "temperature"]),
                ("chills", ["chills", "shivering"]),
                ("body aches", ["body aches", "muscle aches", "aches"]),
                ("shortness of breath", ["shortness of breath", "difficulty breathing", "breathless"]),
                ("sore throat", ["sore throat", "painful swallowing"]),
                ("chest pain", ["chest pain", "tightness in chest"]),
                ("dizziness", ["dizziness", "lightheaded"]),
                ("nausea", ["nausea", "vomiting"]),
                ("headache", ["headache", "migraine"]),
                ("rash", ["rash", "skin change", "spots"]),
                ("itching", ["itchy", "itching"])
            ]
            found_denials = []
            for canonical, terms in denied_candidates:
                if any(t in prev_lower for t in terms):
                    negated_terms.add(canonical)
                    self.negative_symptoms.add(canonical)
                    found_denials.append(canonical)
            if found_denials and is_latest:
                self.turn_new_denials = set(found_denials)

            # Check if previous question asked if temperature was measured
            if is_temperature_question(previous_ai_message):
                if not self.temperature:
                    self.temperature = "Not measured (patient has not taken temperature)"
                    if is_latest:
                        self.turn_new_temperature = True

            # Check if previous question asked about cold symptoms (runny nose, sore throat, sneezing)
            if is_cold_question(previous_ai_message):
                if not self.cold_symptoms:
                    self.cold_symptoms = "Denies runny nose, nasal blockage, sneezing, or sore throat"

            # Check if previous question asked about systemic symptoms (chills, sweating, fatigue)
            if is_systemic_question(previous_ai_message):
                if not self.systemic_symptoms:
                    self.systemic_symptoms = "Denies chills, sweating, fatigue, or generalized weakness"

            # Check if previous question asked about associated aches (headache, body aches, retro-orbital)
            if is_associated_aches_question(previous_ai_message):
                if not self.associated_aches:
                    self.associated_aches = "Denies headache, body aches, or pain behind eyes"

            # Check if previous question asked about travel or exposure
            if is_travel_exposure_question(previous_ai_message):
                if not self.travel_exposure:
                    self.travel_exposure = "Denies recent travel or known ill contacts"
                    if is_latest:
                        self.turn_new_travel_exposure = True

            # Check if previous question asked about pain radiation
            if is_pain_location_question(previous_ai_message):
                if not self.pain_radiation:
                    self.pain_radiation = "Does not radiate"
                    if is_latest:
                        self.turn_new_pain_details = True

            # Check if previous question asked about prior episodes
            if is_prior_episodes_question(previous_ai_message):
                if not self.prior_episodes:
                    self.prior_episodes = "No prior episodes reported"

            # Check if previous question asked about triggers / exposure for rash
            if is_rash_triggers_question(previous_ai_message):
                if not self.triggers_exposure:
                    self.triggers_exposure = "No new product exposures, soaps, plants, or insect bites identified"
                    if is_latest:
                        self.turn_new_rash_details = True

            # Check if previous question asked if tea/steam/home remedies helped
            if any(w in prev_lower for w in ["warm tea", "steam", "helped", "home remedies"]) and not is_medication_question(previous_ai_message):
                self.relieving_aggravating = "Home remedies (tea/steam) have not provided significant relief"
                if is_latest:
                    self.turn_new_relieving_aggravating = True

            # Check if previous question asked about medications
            if is_medication_question(previous_ai_message):
                if not self.medications:
                    self.medications = "None reported"
                    if is_latest:
                        self.turn_new_meds = True

            # Check if previous question asked about allergies
            if is_allergy_question(previous_ai_message):
                if not self.allergies:
                    self.allergies = "No known drug allergies (NKDA)"
                    if is_latest:
                        self.turn_new_allergies = True

            # Check if previous question asked about medical/family history
            if any(w in prev_lower for w in ["personal medical history", "chronic conditions", "family history"]) and not is_allergy_question(previous_ai_message):
                if not self.past_medical_history:
                    self.past_medical_history = "No chronic conditions reported"
                if not self.family_history:
                    self.family_history = "No significant family history reported"

        # 2. Extract Positive Symptoms (excluding explicitly negated ones)
        turn_symptoms = set()
        for sym, patterns in SYMPTOM_LEXICON.items():
            if sym in negated_terms:
                continue
            for pattern in patterns:
                if re.search(pattern, lower):
                    turn_symptoms.add(sym)
                    break

        if is_latest and self.patient_message_count > 1:
            self.new_symptoms_in_turn = turn_symptoms - self.symptoms
        else:
            self.new_symptoms_in_turn = set()

        self.symptoms.update(turn_symptoms)
        self.symptom_groups.update(detect_symptom_groups(self.symptoms, lower))

        # 3. Extract Onset & Duration
        if not self.onset_duration:
            if re.search(r"\b(?:from|since|started|in\s+the|this)\s+morning\b", lower):
                self.onset_duration = "this morning"
                if is_latest:
                    self.turn_new_onset = True
            elif re.search(r"\b(?:from|since|started)\s+yesterday\b|\byesterday\b", lower):
                self.onset_duration = "since yesterday"
                if is_latest:
                    self.turn_new_onset = True
            elif re.search(r"\b(?:started\s+)?today\b", lower):
                self.onset_duration = "today"
                if is_latest:
                    self.turn_new_onset = True
            elif re.search(r"\b(?:for\s+)?((?:\d+|a|an|one|two|three|four|five|six|seven|eight|nine|ten)\s*(?:days?|weeks?|months?|hours?|years?))\b", lower):
                m = re.search(r"\b(?:for\s+)?((?:\d+|a|an|one|two|three|four|five|six|seven|eight|nine|ten)\s*(?:days?|weeks?|months?|hours?|years?))\b", lower)
                self.onset_duration = m.group(1).strip()
                if is_latest:
                    self.turn_new_onset = True
            elif re.search(r"\b(\d+)\s+days?\s+ago\b", lower):
                m = re.search(r"\b(\d+)\s+days?\s+ago\b", lower)
                self.onset_duration = f"{m.group(1)} days"
                if is_latest:
                    self.turn_new_onset = True
            elif any(w in lower for w in ["couple of days", "few days"]):
                self.onset_duration = "a few days"
                if is_latest:
                    self.turn_new_onset = True
            elif any(w in lower for w in ["sudden", "all of a sudden", "suddenly"]):
                self.onset_duration = "started suddenly"
                if is_latest:
                    self.turn_new_onset = True
            elif any(w in lower for w in ["gradual", "gradually", "slowly"]):
                self.onset_duration = "developed gradually"
                if is_latest:
                    self.turn_new_onset = True

        # 4. Extract Severity
        num_word_map = {
            "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
            "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10"
        }
        scale_text = lower
        for word, num in num_word_map.items():
            scale_text = re.sub(rf"\b{word}\b", num, scale_text)

        out_of_10 = re.search(r"\b([0-9]|10)\s*(?:out\s+of|\/)\s*10\b", scale_text)
        if out_of_10:
            self.severity = f"{out_of_10.group(1)}/10"
            if is_latest:
                self.turn_new_severity = True
        else:
            scale_match = re.search(
                r"\b(?:scale\s+(?:of|is)\s+|on\s+a\s+scale\s+of\s+|rate\s+(?:it\s+)?(?:a\s+)?|rated\s+(?:at\s+)?|level\s+|score\s+(?:of\s+)?|discomfort\s+(?:is\s+)?(?:a\s+)?|pain\s+(?:is\s+)?(?:a\s+)?)([0-9]|10)\b",
                scale_text
            )
            if scale_match:
                self.severity = f"{scale_match.group(1)}/10"
                if is_latest:
                    self.turn_new_severity = True
            elif not self.severity:
                prev_asked_scale = previous_ai_message and any(
                    k in previous_ai_message.lower() for k in [
                        "scale of 1 to 10", "1 to 10", "1-10", "from 1 to 10",
                        "scale", "intensity", "rate the discomfort", "rate your",
                        "rate it", "how intense"
                    ]
                )
                standalone_digit = re.search(r"\b([1-9]|10)\b", scale_text)
                if prev_asked_scale and standalone_digit and not re.search(r"\b\d+\s*(?:days?|weeks?|hours?)\b", lower):
                    self.severity = f"{standalone_digit.group(1)}/10"
                    if is_latest:
                        self.turn_new_severity = True
                elif any(w in lower for w in ["excruciating", "unbearable", "intense", "severe", "very bad", "very severe"]):
                    self.severity = "severe"
                    if is_latest:
                        self.turn_new_severity = True
                elif any(w in lower for w in ["moderate", "medium", "pretty bad", "somewhat bad"]):
                    self.severity = "moderate"
                    if is_latest:
                        self.turn_new_severity = True
                elif any(w in lower for w in ["mild", "slight", "minor", "not too bad", "a little"]):
                    self.severity = "mild"
                    if is_latest:
                        self.turn_new_severity = True

        # 5. Extract Character / Quality
        if not self.character or self.character in ("dry", "wet"):
            if re.search(r"\b(?:dry\s+cough|it'?s\s+dry|cough\s+is\s+dry|\bdry\b)\b", lower):
                if not self.character or "dry" not in self.character:
                    self.character = f"{self.character}, dry" if self.character else "dry"
                    if is_latest:
                        self.turn_new_character = True
            elif re.search(r"\b(?:wet|productive|mucus|phlegm|bringing\s+up\s+(?:mucus|phlegm))\b", lower):
                c_val = "productive with mucus/phlegm"
                if not self.character or "productive" not in self.character:
                    self.character = f"{self.character}, {c_val}" if self.character else c_val
                    if is_latest:
                        self.turn_new_character = True

            char_matches = re.findall(
                r"\b(throbbing|pounding|sharp|stabbing|dull|aching|burning|cramping|tight|sore|shooting|tingling|scratchy)\b",
                lower
            )
            if char_matches:
                new_chars = ", ".join(dict.fromkeys(char_matches))
                if not self.character:
                    self.character = new_chars
                    if is_latest:
                        self.turn_new_character = True
                elif new_chars not in self.character:
                    self.character = f"{self.character}, {new_chars}"
                    if is_latest:
                        self.turn_new_character = True

        # 6. Extract Location
        if not self.location:
            loc_matches = re.findall(
                r"\b(right\s+side(?:\s+of\s+head)?|left\s+side(?:\s+of\s+head)?|bilateral|unilateral|forehead|temple|front\s+of\s+head|back\s+of\s+head|lower\s+back|upper\s+back|behind\s+(?:my\s+)?eyes?|chest|abdomen|stomach|throat|neck|knees?|shoulders?|ears?|sinuses?)\b",
                lower
            )
            if loc_matches:
                self.location = ", ".join(dict.fromkeys(loc_matches))
                if is_latest:
                    self.turn_new_location = True

        # 7. Extract Relieving / Aggravating factors
        prev_asked_relief = is_relief_or_aggravating_question(previous_ai_message)

        if not self.relieving_aggravating or "Home remedies" in self.relieving_aggravating:
            # 7a. Unclear / ambiguous response to a relief question
            unclear_patterns = [
                r"^(?:maybe|perhaps|not\s+sure|i\s+don'?t\s+know|idk|i'?m\s+not\s+certain|no\s+idea)[?!.]*$",
                r"^(?:what\s+do\s+you\s+mean|can\s+you\s+clarify|why|what|huh)[?!.]*$"
            ]
            if prev_asked_relief and any(re.search(p, lower) for p in unclear_patterns):
                if is_latest:
                    self.turn_needs_clarification = "relieving_aggravating"

            # 7b. Explicit denial in response to relief question (e.g. "nothing", "not really", "no")
            elif prev_asked_relief and (
                is_pure_denial
                or lower in {"nothing", "nothing really", "not really", "haven't noticed anything", "no nothing"}
                or re.search(r"\b(?:nothing\s+(?:helps|makes\s+it|worked)|not\s+noticed\s+anything)\b", lower)
            ):
                self.relieving_aggravating = "None identified (patient reports nothing notably improves or worsens symptoms)"
                if is_latest:
                    self.turn_new_relieving_aggravating = True

            # 7c. Explicit aggravating factor stated
            elif any(k in lower for k in ["worse with", "makes it worse", "make it worse", "light makes", "sound makes", "moving makes", "worse when", "aggravated by"]):
                m = re.search(r"\b((?:worse|aggravated)\s+(?:with|when|by)[^.,;\n]+|makes?\s+it\s+worse[^.,;\n]*|lifting\s+my\s+arm\s+makes\s+it\s+worse[^.,;\n]*)", cleaned, flags=re.IGNORECASE)
                if m:
                    self.relieving_aggravating = m.group(0).strip()
                else:
                    self.relieving_aggravating = cleaned
                if is_latest:
                    self.turn_new_relieving_aggravating = True

            # 7d. Explicit relieving factor stated
            elif any(k in lower for k in ["better with", "helps", "relieved by", "better when", "provides relief", "brings relief", "bring relief", "brings some relief", "some relief", "gives relief", "quiet room"]):
                m = re.search(r"\b(better\s+(?:with|when)[^.,;\n]+|relieved\s+by[^.,;\n]+|(?:provides?|brings?|gives?)\s+(?:some\s+)?relief[^.,;\n]*|resting\s+in\s+a\s+quiet\s+room[^.,;\n]*)", cleaned, flags=re.IGNORECASE)
                if m:
                    self.relieving_aggravating = m.group(0).strip()
                else:
                    self.relieving_aggravating = cleaned
                if is_latest:
                    self.turn_new_relieving_aggravating = True

            # 7e. Direct pain/hurt triggers (e.g. "it hurts when I move", "pain when lifting")
            elif re.search(r"\b(?:hurts?|pain|ache|discomfort)\s+(?:when|with|while|after|if)\s+[^.,;\n]+", lower):
                m = re.search(r"\b(?:hurts?|pain|ache|discomfort)\s+(?:when|with|while|after|if)\s+[^.,;\n]+", cleaned, flags=re.IGNORECASE)
                self.relieving_aggravating = m.group(0).strip()
                if is_latest:
                    self.turn_new_relieving_aggravating = True

            # 7f. Contextual descriptive answer to relief inquiry or temporal/activity trigger
            elif prev_asked_relief or re.search(r"\b(?:when|while)\s+(?:i\s+)?(?:lift|move|bend|walk|breathe|cough|swallow|stand|sit|turn|run|stretch|reach|eat)\w*\b", lower):
                m_when = re.search(r"\b(?:when|while)\s+(?:i\s+)?[a-zA-Z\s]+", cleaned, flags=re.IGNORECASE)
                if m_when and not any(k in lower for k in ["when did", "when it started"]):
                    self.relieving_aggravating = m_when.group(0).strip()
                    if is_latest:
                        self.turn_new_relieving_aggravating = True
                elif prev_asked_relief and len(cleaned.split()) <= 15 and not any(k in lower for k in [
                    "year", "month", "scale", "fever", "medication", "medications", "meds",
                    "allergic", "allergy", "allergies", "chronic", "diagnosed", "asthma", "diabetes",
                    "hypertension", "blood pressure", "history", "conditions"
                ]):
                    self.relieving_aggravating = cleaned
                    if is_latest:
                        self.turn_new_relieving_aggravating = True

            elif re.search(r"\b(?:sensitive to light|light sensitivity|photophobia)\b", lower):
                self.relieving_aggravating = "Aggravated by bright light / sensitivity to light"
                if is_latest:
                    self.turn_new_relieving_aggravating = True
            elif re.search(r"\b(?:barely helped|didn't help|did not help|partially helped|helped a bit|helped)\b", lower):
                m = re.search(r"\b([^.,;\n]*(?:barely helped|didn't help|did not help|helped|relieved)[^.,;\n]*)", lower)
                if m:
                    self.relieving_aggravating = m.group(1).strip()
                    if is_latest:
                        self.turn_new_relieving_aggravating = True

        # 8. Extract Medications
        is_answering_allergy = (
            bool(re.search(r"\b(?:allergic\s+to|allergy\s+to|allergies|nkda|not\s+allergic)\b", lower))
            or any(a in lower for a in ["penicillin", "latex", "sulfa", "peanuts", "pollen"])
        )
        is_answering_history = (
            bool(re.search(r"\b(?:diagnosed\s+with|history\s+of|chronic\s+condition|i\s+have\s+(?:asthma|diabetes|hypertension|blood\s+pressure|gerd|acid\s+reflux|eczema|cholesterol))\b", lower))
            or any(c in lower for c in ["asthma", "hypertension", "diabetes", "high blood pressure"])
        )

        has_med_info = (
            any(k in lower for k in [
                "ibuprofen", "advil", "tylenol", "paracetamol", "acetaminophen",
                "aspirin", "albuterol", "inhaler", "cetirizine", "zyrtec",
                "claritin", "lisinopril", "metformin", "omeprazole", "naproxen",
                "amoxicillin", "antibiotic", "steroids", "multivitamin", "supplements",
                "cough syrup", "cough drops", "lozenges", "medication", "medications", "meds", "pills", "tablets"
            ])
            or bool(re.search(r"\b(?:i\s+(?:take|am\s+taking|'m\s+taking|took|use)|taking|took|prescribed)\b", lower))
        )

        if is_medication_question(previous_ai_message) and (has_med_info or not (is_answering_allergy or is_answering_history)):
            if is_uncertain_response(lower):
                self.medications = "Uncertain"
                if is_latest:
                    self.turn_new_meds = True
            elif (
                is_pure_denial
                or any(k in lower for k in [
                    "no meds", "no medication", "no medications", "not taking any",
                    "don't take any", "not on any", "no prescription",
                    "take no medication", "takes no medication", "none reported", "none"
                ])
            ):
                self.medications = "None reported"
                if is_latest:
                    self.turn_new_meds = True
            elif (
                any(w in lower for w in [
                    "warm tea", "steam", "honey", "rest", "resting", "walk", "walking",
                    "exercise", "moving", "movement", "heat", "ice", "stretch", "stretching",
                    "position", "massage", "physio", "therapy"
                ])
                or any(w in lower for w in ["helps", "helped", "better", "worse", "relieve", "relieved", "hurts when", "hurts while"])
            ) and not any(d in lower for d in [
                "ibuprofen", "advil", "tylenol", "paracetamol", "acetaminophen",
                "aspirin", "albuterol", "inhaler", "cetirizine", "zyrtec",
                "claritin", "lisinopril", "metformin", "omeprazole", "naproxen",
                "amoxicillin", "antibiotic", "steroids", "multivitamin", "supplements",
                "cough syrup", "cough drops", "lozenges", "pills", "tablets", "capsule", "syrup"
            ]):
                # Home remedies / lifestyle measures belong to relieving_aggravating
                if not self.relieving_aggravating:
                    self.relieving_aggravating = cleaned.capitalize()
                    if is_latest:
                        self.turn_new_relieving_aggravating = True
            else:
                self.medications = clean_medication_input(cleaned)
                if is_latest:
                    self.turn_new_meds = True
        elif not self.medications or self.medications in ("Uncertain", "None reported"):
            # Spontaneous medication reporting outside direct medication inquiry
            if re.search(r"\b(?:no\s+(?:current\s+)?(?:prescription\s+)?(?:medications?|meds)|not\s+taking\s+(?:any\s+)?(?:meds|medications?|drugs?)|don'?t\s+take\s+(?:any\s+)?(?:meds|medications?)|take\s+no\s+(?:prescription\s+)?medications?|no\s+medication|no\s+meds)\b", lower):
                self.medications = "None reported"
                if is_latest:
                    self.turn_new_meds = True
            else:
                known_drugs = [
                    "ibuprofen", "advil", "tylenol", "paracetamol", "acetaminophen",
                    "aspirin", "albuterol", "inhaler", "cetirizine", "zyrtec",
                    "claritin", "lisinopril", "metformin", "omeprazole", "naproxen",
                    "amoxicillin", "antibiotic", "steroids?", "multivitamin", "supplements?",
                    "cough syrup", "cough drops?", "lozenges?"
                ]
                found_meds = []
                for drug in known_drugs:
                    pattern = rf"\b({drug}(?:[,\s]+\d+\s*(?:mg|mcg|ml|g))?(?:\s+(?:daily|twice\s+a\s+day|every\s+day|as\s+needed))?)\b"
                    found = re.findall(pattern, lower)
                    if found:
                        found_meds.extend(found)
                if found_meds:
                    self.medications = ", ".join(dict.fromkeys(found_meds)).capitalize()
                    if is_latest:
                        self.turn_new_meds = True
                else:
                    med_match = re.search(
                        r"\b(?:i\s+(?:also\s+)?(?:take|am\s+taking|'m\s+taking|took|use|am\s+using|'m\s+using|am\s+on|'m\s+on)|currently\s+taking|taking|took|prescribed)\s+([^.,;\n]+)",
                        cleaned,
                        re.IGNORECASE
                    )
                    if med_match:
                        self.medications = clean_medication_input(med_match.group(1))
                        if is_latest:
                            self.turn_new_meds = True

        # 9. Extract Allergies
        is_answering_med = (
            bool(re.search(r"\b(?:i\s+(?:take|am\s+taking|'m\s+taking|took|use)|taking|took|prescribed)\s+", cleaned, re.IGNORECASE))
            or any(d in lower for d in ["paracetamol", "ibuprofen", "aspirin", "tylenol", "advil", "metformin", "naproxen", "lisinopril", "albuterol"])
        )
        is_answering_history = (
            bool(re.search(r"\b(?:diagnosed\s+with|history\s+of|chronic\s+condition|i\s+have\s+(?:asthma|diabetes|hypertension|blood\s+pressure|gerd|acid\s+reflux|eczema|cholesterol))\b", lower))
            or any(c in lower for c in ["asthma", "hypertension", "diabetes", "high blood pressure"])
        )
        has_allergy_info = (
            bool(re.search(r"\b(?:allergic\s+to|allergy\s+to|allergies|nkda|not\s+allergic|no\s+allergies|known\s+allergies)\b", lower))
            or any(a in lower for a in ["penicillin", "latex", "sulfa", "peanuts", "pollen"])
        )

        if is_allergy_question(previous_ai_message) and (has_allergy_info or not (is_answering_med or is_answering_history)):
            if is_uncertain_response(lower):
                self.allergies = "Uncertain"
                if is_latest:
                    self.turn_new_allergies = True
            elif (
                is_pure_denial
                or any(k in lower for k in [
                    "no allergies", "no known allergies", "no drug allergies",
                    "nkda", "not allergic", "none that i know of",
                    "denies allergies", "have no known allergies", "none"
                ])
            ):
                self.allergies = "No known drug allergies (NKDA)"
                if is_latest:
                    self.turn_new_allergies = True
            else:
                self.allergies = clean_allergy_input(cleaned)
                if is_latest:
                    self.turn_new_allergies = True
        elif not self.allergies or self.allergies in ("Uncertain", "No known drug allergies (NKDA)"):
            # Spontaneous allergy reporting outside direct allergy inquiry
            if re.search(r"\b(?:no\s+(?:known\s+)?(?:drug\s+|food\s+)?allergies|nkda|not\s+allergic(?:\s+to\s+anything)?|denies\s+allergies|have\s+no\s+(?:known\s+)?allergies|no\s+allergies)\b", lower):
                self.allergies = "No known drug allergies (NKDA)"
                if is_latest:
                    self.turn_new_allergies = True
            else:
                allergy_match = re.search(
                    r"\b(?:allergic\s+to|allergy\s+to|allergies(?:\s+to)?|allergic\s+with)\s+([^.,;\n]+)",
                    cleaned,
                    re.IGNORECASE
                )
                if allergy_match:
                    self.allergies = clean_allergy_input(allergy_match.group(1))
                    if is_latest:
                        self.turn_new_allergies = True
                elif any(k in lower for k in ["penicillin", "sulfa", "latex", "peanuts", "pollen"]):
                    for allergen in ["penicillin", "sulfa", "latex", "peanuts", "pollen"]:
                        if allergen in lower and "no" not in lower:
                            self.allergies = f"{allergen.capitalize()}"
                            if is_latest:
                                self.turn_new_allergies = True
                            break

        # 10. Extract Past Medical History
        is_answering_med = (
            bool(re.search(r"\b(?:i\s+(?:take|am\s+taking|'m\s+taking|took|use)|taking|took|prescribed)\s+", cleaned, re.IGNORECASE))
            or any(d in lower for d in ["paracetamol", "ibuprofen", "aspirin", "tylenol", "advil", "metformin", "naproxen", "lisinopril", "albuterol"])
        )
        is_answering_allergy = (
            bool(re.search(r"\b(?:allergic\s+to|allergy\s+to|allergies|nkda|not\s+allergic)\b", lower))
            or any(a in lower for a in ["penicillin", "latex", "sulfa", "peanuts", "pollen"])
        )
        has_history_info = (
            bool(re.search(r"\b(?:diagnosed\s+with|history\s+of|chronic\s+condition|past\s+illness|pre-existing|no\s+chronic|no\s+(?:medical\s+)?history)\b", lower))
            or any(c in lower for c in ["asthma", "hypertension", "diabetes", "high blood pressure", "gerd", "acid reflux", "eczema", "cholesterol", "arthritis", "healthy"])
        )

        if is_history_question(previous_ai_message) and (has_history_info or not (is_answering_med or is_answering_allergy)):
            if is_uncertain_response(lower):
                self.past_medical_history = "Uncertain"
                if is_latest:
                    self.turn_new_history = True
            elif (
                is_pure_denial
                or any(k in lower for k in [
                    "no chronic conditions", "no medical history", "no past medical history", "no history",
                    "none", "nothing", "healthy", "no known conditions", "none that i know of",
                    "no past illness", "i don't have any", "don't have any", "never had any",
                    "no pre-existing conditions", "no illnesses", "no health conditions"
                ])
            ):
                self.past_medical_history = "No chronic conditions reported"
                if is_latest:
                    self.turn_new_history = True
            else:
                self.past_medical_history = clean_history_input(cleaned)
                if is_latest:
                    self.turn_new_history = True
        elif not self.past_medical_history or self.past_medical_history in ("Uncertain", "No chronic conditions reported"):
            # Spontaneous reporting outside direct history inquiry
            if any(k in lower for k in [
                "no medical history", "no history", "no chronic conditions", "healthy",
                "no past illness", "no pre-existing conditions"
            ]):
                self.past_medical_history = "No chronic conditions reported"
                if is_latest:
                    self.turn_new_history = True
            else:
                diag_match = re.search(
                    r"\b(?:diagnosed\s+with|history\s+of|i\s+have\s+(?:chronic\s+)?|suffer\s+from)\s+([^.,;\n]+)",
                    cleaned,
                    re.IGNORECASE
                )
                if diag_match and not any(k in lower for k in ["family", "mother", "father", "sister", "brother"]):
                    self.past_medical_history = clean_history_input(diag_match.group(1))
                    if is_latest:
                        self.turn_new_history = True
                else:
                    conditions = [
                        "asthma", "hypertension", "high blood pressure", "diabetes",
                        "migraines?", "thyroid", "gerd", "acid reflux", "eczema",
                        "cholesterol", "arthritis", "kidney stones?", "epilepsy", "depression"
                    ]
                    found_cond = [
                        c for c in conditions
                        if re.search(rf"\b{c}\b", lower) and "family" not in lower and "mother" not in lower and "father" not in lower
                    ]
                    if found_cond:
                        self.past_medical_history = ", ".join(dict.fromkeys(found_cond)).capitalize()
                        if is_latest:
                            self.turn_new_history = True

        # 11. Extract Family History
        if not self.family_history:
            if any(k in lower for k in ["no family history", "none in family", "family is healthy"]):
                self.family_history = "No significant family history reported"
            elif any(k in lower for k in ["mother", "mom", "father", "dad", "sister", "brother", "parents"]):
                m = re.search(r"\b((?:mother|mom|father|dad|sister|brother|parents?)\s+(?:has|had|suffers|gets)[^.,;\n]+)", lower)
                if m:
                    self.family_history = m.group(1).strip().capitalize()

        # 12. Extract Measured Temperature
        if not self.temperature:
            temp_num_match = re.search(r"\b(10[0-5](?:\.\d+)?|[9][6-9](?:\.\d+)?)\s*(?:degrees?|[°\s]*[fc]\b|f\b|c\b)", lower)
            if temp_num_match:
                raw_temp = temp_num_match.group(0).strip()
                unit = "°F" if "c" not in raw_temp.lower() else "°C"
                val = temp_num_match.group(1).strip()
                self.temperature = f"{val}{unit}"
                if is_latest:
                    self.turn_new_temperature = True
            elif is_temperature_question(previous_ai_message) and any(w in lower for w in ["haven't measured", "have not measured", "didn't measure", "not measured", "no thermometer", "haven't checked", "didn't check"]):
                self.temperature = "Not measured (patient has not taken temperature)"
                if is_latest:
                    self.turn_new_temperature = True
            elif is_temperature_question(previous_ai_message) and re.search(r"\b(10[0-5]|[9][6-9])\b", lower):
                m_dig = re.search(r"\b(10[0-5]|[9][6-9])\b", lower)
                self.temperature = f"{m_dig.group(1)}°F"
                if is_latest:
                    self.turn_new_temperature = True

        # 13. Extract Cold Symptoms (runny nose, blocked nose, sneezing, sore throat)
        if not self.cold_symptoms:
            cold_items = []
            if re.search(r"\b(?:runny\s+nose|running\s+nose)\b", lower):
                cold_items.append("runny nose")
            if re.search(r"\b(?:blocked\s+nose|stuffy\s+nose|nasal\s+congestion)\b", lower):
                cold_items.append("blocked nose")
            if re.search(r"\bsneez(?:ing|e|es)\b", lower):
                cold_items.append("sneezing")
            if re.search(r"\bsore\s+throat\b", lower):
                cold_items.append("sore throat")
            if cold_items:
                self.cold_symptoms = ", ".join(cold_items)

        # 14. Extract Cough Nature & Mucus Appearance
        if not self.cough_nature:
            if re.search(r"\b(?:dry\s+cough|dry|it'?s\s+dry|cough\s+is\s+dry)\b", lower) and "wet" not in lower and "productive" not in lower:
                self.cough_nature = "dry"
                if is_latest:
                    self.turn_new_cough_nature = True
            elif re.search(r"\b(?:productive|wet|bringing\s+up\s+mucus|phlegm|mucus)\b", lower):
                mucus_match = re.search(r"\b(yellow|green|clear|white|thick|brown|rusty)\b", lower)
                if mucus_match:
                    self.mucus_appearance = mucus_match.group(1)
                    self.cough_nature = f"productive ({self.mucus_appearance} mucus)"
                else:
                    self.cough_nature = "productive with mucus"
                if is_latest:
                    self.turn_new_cough_nature = True
            elif is_cough_nature_question(previous_ai_message) and "dry" in lower:
                self.cough_nature = "dry"
                if is_latest:
                    self.turn_new_cough_nature = True

        # 15. Extract Systemic Symptoms (chills, sweating, fatigue, weakness)
        if not self.systemic_symptoms:
            sys_items = []
            if re.search(r"\bchills\b", lower) and "no chills" not in lower:
                sys_items.append("chills")
            if re.search(r"\bsweat(?:ing|s)?\b", lower) and "no sweat" not in lower:
                sys_items.append("sweating")
            if re.search(r"\bfatigue\b|\btired\b", lower) and "not tired" not in lower:
                sys_items.append("fatigue")
            if re.search(r"\bweakness\b|\bweak\b", lower) and "not weak" not in lower:
                sys_items.append("weakness")
            if sys_items:
                self.systemic_symptoms = ", ".join(sys_items)

        # 16. Extract Associated Aches (headache, body aches, pain behind eyes)
        if not self.associated_aches:
            aches = []
            if re.search(r"\bheadaches?\b", lower) and "no headache" not in lower:
                aches.append("headache")
            if re.search(r"\bbody\s+aches?\b|\bmuscle\s+aches?\b", lower) and "no body aches" not in lower:
                aches.append("body aches")
            if re.search(r"\bpain\s+behind\s+(?:the\s+|my\s+)?eyes?\b|\bretro[- ]orbital\b", lower):
                aches.append("pain behind eyes")
            if aches:
                self.associated_aches = ", ".join(aches)

        # 17. Extract Travel / Exposure
        if not self.travel_exposure:
            if re.search(r"\b(?:travel(?:led|ed)?|trip)\s+to\s+([a-zA-Z\s]+)", cleaned, re.IGNORECASE):
                m_tr = re.search(r"\b(?:travel(?:led|ed)?|trip)\s+to\s+([a-zA-Z\s]+)", cleaned, re.IGNORECASE)
                self.travel_exposure = f"Recent travel to {m_tr.group(1).strip()}"
                if is_latest:
                    self.turn_new_travel_exposure = True
            elif any(w in lower for w in ["sick contact", "exposed to someone", "coworker is sick", "family member sick"]):
                self.travel_exposure = "Exposure to ill contact reported"
                if is_latest:
                    self.turn_new_travel_exposure = True

        # 18. Extract Pain Pattern & Radiation
        if not self.pain_pattern:
            if any(w in lower for w in ["constant", "continuously", "all the time", "persistent"]):
                self.pain_pattern = "constant"
                if is_latest:
                    self.turn_new_pain_details = True
            elif any(w in lower for w in ["comes and goes", "come and go", "intermittent", "in waves", "spasmodic"]):
                self.pain_pattern = "intermittent (comes and goes)"
                if is_latest:
                    self.turn_new_pain_details = True

        if not self.pain_radiation:
            rad_match = re.search(r"\b(?:radiat(?:es|ing)?|spreads?|shoots?|travels?)\s+to\s+([a-zA-Z\s]+)", cleaned, re.IGNORECASE)
            if rad_match:
                self.pain_radiation = f"Radiates to {rad_match.group(1).strip()}"
                if is_latest:
                    self.turn_new_pain_details = True
            elif any(w in lower for w in ["doesn't spread", "does not spread", "doesn't radiate", "does not radiate", "stays in one spot", "stays put"]):
                self.pain_radiation = "Does not radiate"
                if is_latest:
                    self.turn_new_pain_details = True

        # 19. Prior episodes
        if not self.prior_episodes:
            if any(w in lower for w in ["first time", "never had this before", "never before", "new for me"]):
                self.prior_episodes = "First time experiencing this (no prior episodes)"
            elif any(w in lower for w in ["had this before", "happened before", "have had similar", "recurrent"]):
                self.prior_episodes = "History of similar prior episodes"

        # 20. Extract Skin Rash details (Appearance, Location, Spread, Sensation, Triggers)
        has_skin_context = (
            GROUP_3_ID in self.symptom_groups
            or any(s in self.symptoms for s in GROUP_3_SYMPTOMS)
            or is_rash_sensation_question(previous_ai_message)
            or is_rash_appearance_question(previous_ai_message)
            or is_rash_location_spread_question(previous_ai_message)
            or is_skin_infection_check_question(previous_ai_message)
            or is_rash_triggers_question(previous_ai_message)
            or any(w in lower for w in ["rash", "skin", "spots", "bumps", "blister", "boil", "itching", "itchy", "pus"])
        )
        if has_skin_context:
            if not self.rash_sensation:
                sens_items = []
                if re.search(r"\bitch(?:y|ing|iness)?\b", lower):
                    sens_items.append("itchy")
                if re.search(r"\bpainful\b|\bhurt(?:s|ing)?\b|\bpain\b", lower) and "no pain" not in lower and "not painful" not in lower:
                    sens_items.append("painful")
                if re.search(r"\bwarm(?:th)?\b|\bhot\b", lower):
                    sens_items.append("warm")
                if re.search(r"\bburning\b", lower):
                    sens_items.append("burning")
                if re.search(r"\btender\b", lower):
                    sens_items.append("tender to touch")
                if "no pain" in lower or "not painful" in lower:
                    sens_items.append("not painful")
                if sens_items:
                    self.rash_sensation = ", ".join(sens_items)
                    if is_latest:
                        self.turn_new_rash_details = True

            if not self.rash_appearance:
                app_items = []
                if re.search(r"\bflat\s+red\s+spots?\b|\bred\s+spots?\b|\bmacules?\b", lower):
                    app_items.append("flat red spots")
                if re.search(r"\braised\s+bumps?\b|\bred\s+bumps?\b|\bpapules?\b", lower):
                    app_items.append("raised bumps")
                if re.search(r"\bblisters?\b|\bboils?\b|\bbullae?\b", lower):
                    app_items.append("blisters/boils")
                if re.search(r"\bpeeling\b|\bflaking\b|\bscaling\b", lower):
                    app_items.append("peeling/scaling")
                if re.search(r"\bpus(?:-filled)?\b|\boozing\b|\bdischarge\b", lower):
                    app_items.append("pus-filled/oozing")
                if app_items:
                    self.rash_appearance = ", ".join(app_items)
                    if is_latest:
                        self.turn_new_rash_details = True

            if not self.rash_location:
                rash_loc_match = re.search(r"\b(?:on\s+(?:my\s+)?)(arms?|legs?|chest|back|face|neck|hands?|feet|abdomen|torso|skin)\b", lower)
                if rash_loc_match:
                    self.rash_location = rash_loc_match.group(1).strip()
                    if not self.location:
                        self.location = f"skin of {self.rash_location}"
                    if is_latest:
                        self.turn_new_rash_details = True
            
            if not self.rash_spread:
                if re.search(r"\b(?:spread(?:ing)?\s+to\s+([a-zA-Z\s]+)|has\s+spread|spreading)\b", lower):
                    m_sp = re.search(r"\bspread(?:ing)?(?:\s+to\s+([a-zA-Z\s]+))?", cleaned, re.IGNORECASE)
                    self.rash_spread = m_sp.group(0).strip() if m_sp else "spreading"
                    if is_latest:
                        self.turn_new_rash_details = True
                elif any(w in lower for w in ["hasn't spread", "has not spread", "stayed in one place", "no spread"]):
                    self.rash_spread = "No spread noted (confined to initial area)"
                    if is_latest:
                        self.turn_new_rash_details = True

            if not self.triggers_exposure:
                trig_match = re.search(r"\b(?:new\s+(?:soap|detergent|lotion|cream|cosmetic|food|plant|insect\s+bite|animal|medication))\b", lower)
                if trig_match:
                    self.triggers_exposure = trig_match.group(0).strip()
                    if is_latest:
                        self.turn_new_rash_details = True


def build_clinical_state_from_history(
    history: List[Dict[str, str]],
    current_patient_message: str
) -> ClinicalDialogueState:
    """
    Parses the entire consultation history plus the latest patient message
    to produce a fully updated ClinicalDialogueState.
    Replays past patient messages alongside their respective preceding AI inquiries
    to ensure contextual extractions (such as standalone ratings or denials) are
    permanently preserved across all subsequent turns.
    """
    state = ClinicalDialogueState()

    last_ai_text = None
    # Replay historical dialogue chronologically, tracking the preceding AI context
    for msg in history:
        role = msg.get("sender_role")
        content = msg.get("message_content", "")
        if role in ("ai", "assistant"):
            last_ai_text = content
            state.questions_asked.append(content)
            # Reconstruct asked topics from historical AI inquiries
            c_low = content.lower()
            if is_temperature_question(content):
                state.asked_topics.add("temperature")
            if is_cold_question(content):
                state.asked_topics.add("cold_symptoms")
            if is_cough_nature_question(content):
                state.asked_topics.add("cough_nature")
            if is_systemic_question(content):
                state.asked_topics.add("systemic_symptoms")
            if is_associated_aches_question(content):
                state.asked_topics.add("associated_aches")
            if is_infection_gi_rash_question(content):
                state.asked_topics.add("infection_gi_rash")
            if is_travel_exposure_question(content):
                state.asked_topics.add("travel_exposure")
            if is_pain_location_question(content):
                state.asked_topics.add("pain_location")
            if is_pain_character_question(content):
                state.asked_topics.add("pain_character")
            if is_pain_pattern_question(content):
                state.asked_topics.add("pain_pattern")
            if is_prior_episodes_question(content):
                state.asked_topics.add("prior_episodes")
            if is_rash_location_spread_question(content):
                state.asked_topics.add("rash_location_spread")
            if is_rash_sensation_question(content):
                state.asked_topics.add("rash_sensation")
            if is_rash_appearance_question(content):
                state.asked_topics.add("rash_appearance")
            if is_skin_infection_check_question(content):
                state.asked_topics.add("skin_infection_check")
            if is_rash_triggers_question(content):
                state.asked_topics.add("rash_triggers")
            if is_remedies_question(content):
                state.asked_topics.add("remedies")
            if is_relief_or_aggravating_question(content):
                state.asked_topics.add("relieving_aggravating")
            if is_medication_question(content):
                state.asked_topics.add("medications")
            if is_allergy_question(content):
                state.asked_topics.add("allergies")
            if is_history_question(content):
                state.asked_topics.add("history")
            if any(w in c_low for w in ["how long", "when did", "how long have you"]):
                state.asked_topics.add("onset")
            if any(w in c_low for w in ["scale of 1 to 10", "rate the discomfort", "on a scale of"]):
                state.asked_topics.add("severity")
        elif role == "patient" and content:
            state.ingest_turn(content, is_latest=False, previous_ai_message=last_ai_text)

    state.last_asked_question = last_ai_text

    # Ingest current patient message with context of the most recent AI message
    if current_patient_message:
        state.ingest_turn(
            current_patient_message,
            is_latest=True,
            previous_ai_message=last_ai_text
        )

    return state


def generate_empathetic_acknowledgment(state: ClinicalDialogueState, latest_message: str = "") -> str:
    """
    Creates an active listening, reflective acknowledgment of what the patient
    JUST shared in their latest message. Validates symptoms, mirrors back details,
    and avoids repetitive canned phrases.
    """
    # 1. First turn presenting symptoms (primary clinical presentation)
    if state.patient_message_count == 1:
        if len(state.symptoms) >= 2:
            sym_list = list(state.symptoms)
            sym_str = ", ".join(sym_list[:-1]) + f" and {sym_list[-1]}"
            return (
                f"I'm really sorry to hear that you're going through all of that. "
                f"Dealing with {sym_str} together can be very draining, and I've noted each of these concerns."
            )
        elif state.symptoms:
            primary = list(state.symptoms)[0]
            return f"I'm sorry you're dealing with that {primary}."
        else:
            return "Thank you for explaining that. I have noted this down in your consultation record."

    # 2. Check if patient just answered with denials to previous symptom inquiry
    if state.turn_new_denials and state.patient_message_count > 1:
        d_list = [d for d in ["fever", "body aches", "chills", "rash", "itching"] if d in state.turn_new_denials]
        for d in state.turn_new_denials:
            if d not in d_list:
                d_list.append(d)
        if len(d_list) > 1:
            denied_str = ", ".join(d_list[:-1]) + f", or {d_list[-1]}"
        elif d_list:
            denied_str = d_list[0]
        else:
            denied_str = "those symptoms"
        if state.turn_new_relieving_aggravating and "tea" in (state.last_asked_question or "").lower():
            return f"Understood, you haven't noticed {denied_str}, and warm tea or steam hasn't helped much."
        return f"Understood, you haven't noticed {denied_str}."

    # 3. Patient introduced a new symptom midway through consultation (turn > 1)
    if state.new_symptoms_in_turn and state.patient_message_count > 1:
        new_sym_list = list(state.new_symptoms_in_turn)
        new_sym = " and ".join(new_sym_list)
        prior_sym_list = [s for s in state.symptoms if s not in state.new_symptoms_in_turn]
        
        if state.turn_new_character and prior_sym_list:
            primary = prior_sym_list[0]
            char = state.character.split(",")[-1].strip() if state.character else ""
            return f"Thanks for telling me. I'll note the {char} {primary} and the {new_sym} too."
        elif prior_sym_list:
            prior_str = " and ".join(prior_sym_list[:2])
            return (
                f"I hear you, and I am sorry you are dealing with {new_sym} on top of the {prior_str} you mentioned earlier. "
                f"I have made sure to document both in your record."
            )
        else:
            return f"Thanks for letting me know about the {new_sym}. I have added that to your record."

    # 4. Temperature acknowledgment
    if state.turn_new_temperature and state.temperature:
        if "not measured" in state.temperature.lower():
            return "Understood, you haven't had a chance to measure your temperature yet."
        return f"Got it, I've noted that your temperature was {state.temperature}."

    # 5. Cough nature acknowledgment
    if state.turn_new_cough_nature and state.cough_nature:
        return f"Understood, I've noted that your cough is {state.cough_nature}."

    # 6. Rash details acknowledgment
    if state.turn_new_rash_details:
        rash_parts = []
        if state.rash_sensation:
            rash_parts.append(f"it is {state.rash_sensation}")
        if state.rash_appearance:
            rash_parts.append(f"appears as {state.rash_appearance}")
        if state.rash_spread:
            rash_parts.append(f"{state.rash_spread}")
        if rash_parts:
            return f"Understood, I've noted that {', and '.join(rash_parts)}."
        return "Understood, I've noted these details regarding your skin changes."

    # 7. Travel / Exposure acknowledgment
    if state.turn_new_travel_exposure and state.travel_exposure:
        return f"Understood, I've noted that: {state.travel_exposure}."

    # 8. Pain details acknowledgment
    if state.turn_new_pain_details:
        if state.pain_pattern and state.pain_radiation:
            return f"Understood, I've noted that the pain is {state.pain_pattern} and {state.pain_radiation.lower()}."
        elif state.pain_radiation:
            return f"Understood, I've noted that the pain {state.pain_radiation.lower()}."
        elif state.pain_pattern:
            return f"Understood, I've noted that the pain is {state.pain_pattern}."

    # 9. Patient answered onset and/or severity in follow-up turn (turn > 1)
    if state.turn_new_onset or state.turn_new_severity:
        reflections = []
        if state.turn_new_onset and state.onset_duration:
            dur = state.onset_duration
            if any(w in dur for w in ["this morning", "today", "yesterday"]):
                reflections.append(f"it started {dur}")
            else:
                reflections.append(f"it has been going on for {dur}")
        
        if state.turn_new_severity and state.severity:
            sev = state.severity
            if "/10" in sev:
                num = sev.split("/")[0]
                reflections.append(f"you'd rate the discomfort a {num} out of 10")
            else:
                reflections.append(f"you'd rate the discomfort as {sev}")
        
        if reflections:
            return f"Got it, {', and '.join(reflections)}."

    # 10. Patient answered character/quality only
    if state.turn_new_character and state.character:
        char_val = state.character.split(",")[-1].strip()
        return f"Understood, I've noted that it feels {char_val}."

    # 11. Patient provided medications, allergies, and/or medical history
    if state.turn_new_meds or state.turn_new_allergies or state.turn_new_history:
        recorded = []
        if state.turn_new_meds and state.medications:
            if state.medications == "None reported":
                recorded.append("you are not currently taking any medications")
            elif state.medications in ("Uncertain", "Unknown", "Not sure"):
                recorded.append("your medication status is uncertain")
            else:
                recorded.append(f"you take {state.medications}")
        if state.turn_new_allergies and state.allergies:
            if state.allergies == "No known drug allergies (NKDA)":
                recorded.append("you have no known allergies")
            elif state.allergies in ("Uncertain", "Unknown", "Not sure"):
                recorded.append("your allergy status is uncertain")
            else:
                recorded.append(f"your allergies ({state.allergies})")
        if state.turn_new_history and state.past_medical_history:
            if state.past_medical_history == "No chronic conditions reported":
                recorded.append("you have no chronic conditions")
            elif state.past_medical_history in ("Uncertain", "Unknown", "Not sure"):
                recorded.append("your medical history status is uncertain")
            else:
                recorded.append(f"your medical history ({state.past_medical_history})")
        return f"Understood, I have recorded that {', and '.join(recorded)}."

    # 12. Relieving / aggravating factors
    if state.turn_needs_clarification == "relieving_aggravating":
        return "To clarify:"

    if state.turn_new_relieving_aggravating and state.relieving_aggravating:
        ra = state.relieving_aggravating.strip()
        ra_lower = ra.lower()
        if ra_lower.startswith("when "):
            return f"Understood, I've noted that this happens {ra}."
        elif "worse" in ra_lower or "hurts" in ra_lower or "pain" in ra_lower:
            return f"I've noted that {ra}."
        elif "better" in ra_lower or "relief" in ra_lower or "helps" in ra_lower:
            return f"Understood, I've noted that {ra}."
        elif "none identified" in ra_lower:
            return "Understood, you haven't noticed anything that clearly makes it better or worse."
        else:
            return f"Understood, I've noted that: {ra}."

    # 13. General listener fallback
    return "Thank you for explaining that. I have noted this down in your consultation record."


def is_question_safe(
    question: str,
    state: ClinicalDialogueState,
    previous_ai_message: Optional[str] = None,
    topic: Optional[str] = None
) -> bool:
    """
    Validates that a proposed question strictly avoids asking for any attribute
    or symptom that the patient has already answered, explicitly denied,
    or was already asked in earlier turns or in the immediate previous AI turn.
    """
    if topic and topic in state.asked_topics:
        return False

    q_lower = question.lower().strip()

    # 1. Immediate previous message deduplication
    if previous_ai_message:
        prev_inquiry = get_last_question(previous_ai_message)
        prev_lower = prev_inquiry.lower().strip()
        # Direct match or substring match
        if q_lower in prev_lower or prev_lower in q_lower:
            return False
        # Specific topic overlap checks with previous AI message
        if is_temperature_question(prev_lower) and is_temperature_question(q_lower):
            return False
        if is_cold_question(prev_lower) and is_cold_question(q_lower):
            return False
        if is_cough_nature_question(prev_lower) and is_cough_nature_question(q_lower):
            return False
        if is_systemic_question(prev_lower) and is_systemic_question(q_lower):
            return False
        if is_associated_aches_question(prev_lower) and is_associated_aches_question(q_lower):
            return False
        if is_infection_gi_rash_question(prev_lower) and is_infection_gi_rash_question(q_lower):
            return False
        if is_travel_exposure_question(prev_lower) and is_travel_exposure_question(q_lower):
            return False
        if is_pain_location_question(prev_lower) and is_pain_location_question(q_lower):
            return False
        if is_pain_character_question(prev_lower) and is_pain_character_question(q_lower):
            return False
        if is_pain_pattern_question(prev_lower) and is_pain_pattern_question(q_lower):
            return False
        if is_prior_episodes_question(prev_lower) and is_prior_episodes_question(q_lower):
            return False
        if is_rash_location_spread_question(prev_lower) and is_rash_location_spread_question(q_lower):
            return False
        if is_rash_sensation_question(prev_lower) and is_rash_sensation_question(q_lower):
            return False
        if is_rash_appearance_question(prev_lower) and is_rash_appearance_question(q_lower):
            return False
        if is_skin_infection_check_question(prev_lower) and is_skin_infection_check_question(q_lower):
            return False
        if is_rash_triggers_question(prev_lower) and is_rash_triggers_question(q_lower):
            return False
        if is_remedies_question(prev_lower) and is_remedies_question(q_lower):
            return False
        if is_relief_or_aggravating_question(prev_lower) and is_relief_or_aggravating_question(q_lower):
            return False
        if ("scale of 1 to 10" in prev_lower or "rate the discomfort" in prev_lower) and ("scale of 1 to 10" in q_lower or "rate the discomfort" in q_lower):
            return False
        if is_medication_question(prev_lower) and is_medication_question(q_lower):
            return False
        if is_allergy_question(prev_lower) and is_allergy_question(q_lower):
            return False
        if is_history_question(prev_lower) and is_history_question(q_lower):
            return False

    # 2. State-based dimension checks
    if state.temperature and is_temperature_question(q_lower):
        return False
    if state.cold_symptoms and is_cold_question(q_lower):
        return False
    if state.cough_nature and is_cough_nature_question(q_lower):
        return False
    if state.systemic_symptoms and is_systemic_question(q_lower):
        return False
    if state.associated_aches and is_associated_aches_question(q_lower):
        return False
    if state.infection_gi_rash and is_infection_gi_rash_question(q_lower):
        return False
    if state.travel_exposure and is_travel_exposure_question(q_lower):
        return False
    if state.location and is_pain_location_question(q_lower):
        return False
    if state.character and is_pain_character_question(q_lower):
        return False
    if state.pain_pattern and is_pain_pattern_question(q_lower):
        return False
    if state.prior_episodes and is_prior_episodes_question(q_lower):
        return False
    if (state.rash_location or state.rash_spread) and is_rash_location_spread_question(q_lower):
        return False
    if state.rash_sensation and is_rash_sensation_question(q_lower):
        return False
    if state.rash_appearance and is_rash_appearance_question(q_lower):
        return False
    if state.triggers_exposure and is_rash_triggers_question(q_lower):
        return False
    if state.severity and any(k in q_lower for k in ["scale of 1 to 10", "rate the discomfort", "how intense", "on a scale", "1 to 10", "rate your", "rate the pain"]):
        return False
    if state.onset_duration and any(k in q_lower for k in ["how long", "when did", "start suddenly", "how long have you"]):
        return False
    if state.relieving_aggravating and (is_relief_or_aggravating_question(q_lower) or is_remedies_question(q_lower)):
        return False
    if state.medications and is_medication_question(q_lower):
        return False
    if state.allergies and is_allergy_question(q_lower):
        return False
    if state.past_medical_history and is_history_question(q_lower):
        return False

    # 3. Cross-group specific safety rules
    if state.is_cold_alone:
        # For cold alone, do NOT ask whether the pain is dull, sharp, or throbbing. Do NOT ask for pain scale.
        if is_pain_character_question(q_lower) or "scale" in q_lower or "dull" in q_lower or "sharp" in q_lower or "throbbing" in q_lower or "rate the discomfort" in q_lower:
            return False

    if state.has_itch_no_pain:
        # If the patient reports an itchy rash without pain, do NOT ask whether the pain is dull or sharp!
        if is_pain_character_question(q_lower) or "dull" in q_lower or "sharp" in q_lower or "throbbing" in q_lower or "cramping" in q_lower:
            return False

    if not state.has_pain:
        # Only ask whether pain is dull, sharp, throbbing, burning, or cramping IF the patient actually reports pain.
        if is_pain_character_question(q_lower):
            return False

    if any(s in state.negative_symptoms for s in ["fever", "chills", "body aches"]) and ("fever" in q_lower or "chills" in q_lower or "body aches" in q_lower):
        return False

    return True


def generate_adaptive_follow_up_questions(
    state: ClinicalDialogueState,
    previous_ai_message: Optional[str] = None
) -> str:
    """
    Formulates 1 relevant follow-up question tailored strictly to what is still
    missing from the clinical picture based on intelligent symptom-based flow.
    NEVER repeats any question whose attribute has already been provided or asked.
    """
    answered = state.answered_dimensions
    prev_lower = (previous_ai_message or state.last_asked_question or "").lower()

    # Priority 0: Focused clarification for genuinely unclear relief answers
    if state.turn_needs_clarification == "relieving_aggravating":
        return "Could you clarify if any particular movement, activity, resting, or remedies change how your symptoms feel, or do they stay about the same?"

    # Priority 1: Newly introduced symptoms midway through conversation (turn > 1)
    if state.new_symptoms_in_turn and state.patient_message_count > 1:
        new_sym_list = list(state.new_symptoms_in_turn)
        new_sym = " and ".join(new_sym_list)
        prior_sym = [s for s in state.symptoms if s not in state.new_symptoms_in_turn]
        
        # Connect with prior symptoms and ask a relevant question from the new group
        if any(s in GROUP_3_SYMPTOMS for s in state.new_symptoms_in_turn):
            q = f"Where on your body did the {new_sym} first appear, and has it spread anywhere else?"
            if is_question_safe(q, state, previous_ai_message, "rash_location_spread"):
                state.asked_topics.add("rash_location_spread")
                return q
        elif any(s in {"fever", "chills"} for s in state.new_symptoms_in_turn):
            q = f"Have you measured your temperature since noticing the {new_sym}?"
            if is_question_safe(q, state, previous_ai_message, "temperature"):
                state.asked_topics.add("temperature")
                return q
        elif prior_sym:
            q = f"Did the {new_sym} start around the same time as the {prior_sym[0]}, or did it begin later?"
            if is_question_safe(q, state, previous_ai_message, "onset"):
                state.asked_topics.add("onset")
                return q
        else:
            q = f"When did the {new_sym} start, and how intense does it feel?"
            if is_question_safe(q, state, previous_ai_message, "onset"):
                state.asked_topics.add("onset")
                return q

    # Priority 2: Unanswered part of a previous compound question
    if any(w in prev_lower for w in ["dry or", "mucus", "phlegm"]) and "cough_nature" not in answered and "cough" in state.symptoms:
        q = "Is the cough dry, or are you bringing up any mucus?"
        if is_question_safe(q, state, previous_ai_message, "cough_nature"):
            state.asked_topics.add("cough_nature")
            return q

    # Priority 2.5: If all core clinical dimensions including medications, allergies, and history are answered -> Wrap up!
    core_dimensions = {"medications", "allergies", "history"}
    if core_dimensions.issubset(answered) and ("onset" in answered or "duration" in answered):
        if state.is_cold_alone or state.is_cough_alone or "severity" in answered or "relieving_aggravating" in answered or len(answered) >= 6:
            summary_points = []
            if state.symptoms:
                summary_points.append(f"symptoms ({', '.join(state.symptoms)})")
            if state.onset_duration:
                summary_points.append(f"duration ({state.onset_duration})")
            if state.severity:
                summary_points.append(f"severity ({state.severity})")
            if state.medications:
                summary_points.append(f"medications ({state.medications})")
            if state.allergies:
                summary_points.append(f"allergies ({state.allergies})")

            return (
                "You have provided a thorough overview of your health concerns, including your "
                + ", ".join(summary_points)
                + ". Whenever you feel ready, please select **'Finish Consultation'** below to review your structured 11-section clinical note, "
                "or feel free to share any other details you would like included."
            )

    # Priority 3: Formulate candidates based on active symptom groups
    candidates: List[Tuple[str, str]] = []

    # Detect groups
    groups = state.symptom_groups
    if not groups:
        groups = detect_symptom_groups(state.symptoms, " ".join(state.raw_patient_messages))

    # --- CASE A: Cold Alone ---
    if state.is_cold_alone:
        if "onset" not in answered:
            candidates.append(("onset", "When did the symptoms begin?"))
        if "cold_symptoms" not in answered:
            candidates.append(("cold_symptoms", "Do you have a runny nose, blocked nose, sneezing, or sore throat?"))
        if "relieving_aggravating" not in answered and "remedies" not in state.asked_topics:
            candidates.append(("remedies", "Have you taken medication or tried home remedies (such as warm tea or steam), and did they help?"))

    # --- CASE B: Cough Alone ---
    elif state.is_cough_alone:
        if "onset" not in answered:
            candidates.append(("onset", "When did your cough begin?"))
        if "cough_nature" not in answered:
            candidates.append(("cough_nature", "If you have a cough, is it dry or productive? If productive, what does the mucus look like?"))
        if "severity" not in answered:
            candidates.append(("severity", "On a scale of 1 to 10 (with 1 being very mild and 10 being severe), how would you rate the discomfort?"))
        if "relieving_aggravating" not in answered:
            if "fever" not in state.negative_symptoms and "chills" not in state.negative_symptoms:
                candidates.append(("remedies", "Are you noticing any fever, body aches, or chills alongside this, and has any warm tea or steam helped?"))
            else:
                candidates.append(("cough_relief", "Have you noticed anything that triggers worse coughing, or has anything helped relieve it?"))

    else:
        # General / Multi-Group / Specific Group logic

        # 1. Onset / Duration (Shared across all groups)
        if "onset" not in answered and "duration" not in answered:
            if GROUP_3_ID in groups and GROUP_2_ID not in groups and GROUP_1_ID not in groups:
                candidates.append(("onset", "When did you first notice the rash or skin change?"))
            elif GROUP_2_ID in groups and GROUP_1_ID not in groups and GROUP_3_ID not in groups:
                candidates.append(("onset", "How long have you had this pain, and did it start suddenly or gradually?"))
            else:
                candidates.append(("onset", "When did these symptoms begin?"))

        # 2. Group 1 specific follow-ups
        if GROUP_1_ID in groups:
            # Temperature for fever, flu, or suspected dengue / malaria
            if state.has_fever or "suspected dengue" in state.symptoms or "suspected malaria" in state.symptoms or "flu" in state.symptoms:
                if "temperature" not in answered:
                    candidates.append(("temperature", "Have you measured your temperature? If yes, what was it?"))

            # Respiratory symptoms (cough nature or cold symptoms)
            if "cough" in state.symptoms and "cough_nature" not in answered:
                candidates.append(("cough_nature", "If you have a cough, is it dry or productive? If productive, what does the mucus look like?"))
            elif any(s in state.symptoms for s in ["cold", "congestion", "sore throat"]) and "cold_symptoms" not in answered:
                candidates.append(("cold_symptoms", "Do you have a runny nose, blocked nose, sneezing, or sore throat?"))

            is_fever_or_infection = state.has_fever or any(s in state.symptoms for s in ["flu", "chills", "weakness", "suspected dengue", "suspected malaria"]) or state.is_suspected_infection
            if is_fever_or_infection:
                # Systemic symptoms (chills, sweating, fatigue, weakness)
                if "systemic_symptoms" not in answered and "chills" not in state.negative_symptoms:
                    candidates.append(("systemic_symptoms", "Are you experiencing chills, sweating, fatigue, or weakness?"))

                # Associated aches (headache, body aches, pain behind eyes)
                if "associated_aches" not in answered and not ("headache" in state.symptoms and "body aches" in state.symptoms):
                    candidates.append(("associated_aches", "Do you also have a headache, body aches, or pain behind your eyes?"))

                # GI symptoms or rash
                if "infection_gi_rash" not in answered and GROUP_3_ID not in groups:
                    candidates.append(("infection_gi_rash", "Are you experiencing nausea, vomiting, diarrhea, or a rash?"))

                # Travel & exposure (especially for suspected dengue / malaria / fever)
                if "travel_exposure" not in answered:
                    candidates.append(("travel_exposure", "Have you recently travelled, been exposed to someone who is ill, or received a relevant diagnosis?"))

        # 3. Group 2 specific follow-ups
        if GROUP_2_ID in groups:
            # Location & Radiation
            if "location" not in answered and "pain_location" not in state.asked_topics:
                candidates.append(("pain_location", "Where exactly is the pain located? Does it radiate or spread anywhere else?"))

            # Severity on 1-10 scale
            if "severity" not in answered:
                candidates.append(("severity", "How would you rate the pain on a scale from 1 to 10?"))

            # Pain Character / Quality (ONLY if patient has pain)
            if state.has_pain and "character" not in answered and not state.has_itch_no_pain:
                candidates.append(("pain_character", "How would you describe the pain (for example, is it dull, sharp, throbbing, burning, or cramping)?"))

            # Relieving / Aggravating factors
            if "relieving_aggravating" not in answered:
                candidates.append(("pain_relief", "Does anything make the pain better or worse (such as movement, rest, heat, ice, or medication)?"))

            # Secondary exploratory pain questions (for generalized/other pain when relief not yet answered and not headache alone)
            if not state.is_headache_alone and "relieving_aggravating" not in answered and not any(t in state.asked_topics for t in ["pain_relief", "relieving_aggravating", "remedies"]):
                if "pain_pattern" not in answered and "pain_pattern" not in state.asked_topics:
                    candidates.append(("pain_pattern", "Is the pain constant, or does it come and go?"))
                if "associated_symptoms" not in state.asked_topics and not any(s in state.symptoms for s in ["nausea", "dizziness"]):
                    candidates.append(("associated_symptoms", "Do you have any associated symptoms (such as nausea, dizziness, numbness, tingling, or weakness)?"))
                if "prior_episodes" not in answered and "prior_episodes" not in state.asked_topics:
                    candidates.append(("prior_episodes", "Have you had similar pain in the past?"))

        # 4. Group 3 specific follow-ups
        if GROUP_3_ID in groups:
            # Location & Spread
            if "rash_location" not in answered and "rash_spread" not in answered and "location" not in answered:
                candidates.append(("rash_location_spread", "Where on your body did the rash or skin change first appear, and has it spread anywhere else?"))

            # Sensation (itchy, painful, warm, tender)
            if "rash_sensation" not in answered:
                candidates.append(("rash_sensation", "Is it itchy, painful, warm, burning, or tender to the touch?"))

            # Appearance (flat spots, bumps, blisters, peeling, pus)
            if "rash_appearance" not in answered:
                candidates.append(("rash_appearance", "How would you describe its appearance (for example, flat red spots, raised bumps, blisters, peeling, or pus-filled)?"))

            # Suspected skin infection / Systemic check
            if "suspected skin infection" in state.symptoms or "skin infection" in " ".join(state.suspected_conditions):
                if "skin_infection_check" not in state.asked_topics:
                    candidates.append(("skin_infection_check", "Have you noticed spreading redness, warmth, swelling, pus, or had any fever or chills?"))
            elif GROUP_1_ID not in groups and "fever" not in state.symptoms:
                if "rash_systemic" not in state.asked_topics:
                    candidates.append(("rash_systemic", "Have you had a fever, chills, body aches, or felt generally unwell?"))

            # Triggers / Exposures
            if "triggers_exposure" not in answered:
                candidates.append(("rash_triggers", "Have you been exposed to new soaps, lotions, detergents, plants, insects, medications, foods, or animals?"))

            # Remedies / Creams / Ointments
            if "relieving_aggravating" not in answered and "rash_remedies" not in state.asked_topics:
                candidates.append(("rash_remedies", "Have you applied any creams, ointments, or taken medication? Did they help?"))

            # Prior skin episodes (when relief not yet answered and not asked)
            if "relieving_aggravating" not in answered and not any(t in state.asked_topics for t in ["rash_remedies", "relieving_aggravating", "remedies"]):
                if "prior_episodes" not in answered and "prior_episodes" not in state.asked_topics:
                    candidates.append(("prior_episodes", "Have you had a similar skin issue before?"))

        # Shared Remedies / Relief if not already asked
        if "relieving_aggravating" not in answered and not any(t[0] in ["remedies", "cough_relief", "pain_relief", "rash_remedies"] for t in candidates):
            candidates.append(("relieving_aggravating", "Have you noticed anything that makes the symptoms feel better or worse, or anything you've tried that provided relief?"))

    # --- MANDATORY CORE INTAKE INQUIRIES ---
    # Medications
    if "medications" not in answered:
        candidates.append(("medications", "Are you currently taking any prescription medications, over-the-counter remedies, or supplements for this or other health conditions?"))

    # Allergies
    if "allergies" not in answered:
        candidates.append(("allergies", "Do you have any known allergies, especially to medications or foods?"))

    # Past Medical / Family History
    if "history" not in answered:
        candidates.append(("history", "Do you have any personal medical history, chronic conditions, or family history related to these concerns?"))

    # Find first candidate passing strict safety check
    for topic, cand in candidates:
        if is_question_safe(cand, state, previous_ai_message, topic):
            state.asked_topics.add(topic)
            state.questions_asked.append(cand)
            return cand

    # Priority 4: All core dimensions collected -> Wrap-up completion invitation
    if is_final_confirmation_question(previous_ai_message):
        return (
            "Whenever you feel ready, please select **'Finish Consultation'** below to review your structured 11-section clinical note, "
            "or feel free to share any other details you would like included."
        )

    summary_points = []
    if state.symptoms:
        summary_points.append(f"symptoms ({', '.join(state.symptoms)})")
    if state.onset_duration:
        summary_points.append(f"duration ({state.onset_duration})")
    if state.severity:
        summary_points.append(f"severity ({state.severity})")
    if state.medications:
        summary_points.append(f"medications ({state.medications})")
    if state.allergies:
        summary_points.append(f"allergies ({state.allergies})")

    return (
        "You have provided a thorough overview of your health concerns, including your "
        + ", ".join(summary_points)
        + ". Whenever you feel ready, please select **'Finish Consultation'** below to review your structured 11-section clinical note, "
        "or feel free to share any other details you would like included."
    )
