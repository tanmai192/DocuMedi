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
    "headache": [
        r"\bheadaches?\b", r"\bheadach\b", r"\bhead\b[^\.\,\;]{0,25}\bpain\b",
        r"\bmigraines?\b", r"\bhead\s+hurts?\b", r"\bhead\s+pounding\b"
    ],
    "nausea": [
        r"\bnausea\b", r"\bnauseous\b", r"\bqueas(?:y|iness)\b",
        r"\bfeel(?:ing)?\s+sick\b", r"\bstomach\b[^\.\,\;]{0,25}\bnauseous\b"
    ],
    "vomiting": [r"\bvomit(?:ing|ed)?\b", r"\bthrowing\s+up\b", r"\bthrew\s+up\b"],
    "dizziness": [r"\bdizz(?:y|iness)\b", r"\blightheaded(?:ness)?\b", r"\bvertigo\b", r"\bunsteady\b"],
    "fever": [r"\bfever(?:ish)?\b", r"\bhigh\s+temp(?:erature)?\b", r"\bchills\b", r"\bshivering\b"],
    "fatigue": [r"\bfatigue\b", r"\btired(?:ness)?\b", r"\bexhaust(?:ed|ion)\b", r"\bletharg(?:ic|y)\b", r"\bweakness\b"],
    "cough": [
        r"\bcough(?:ing)?\b", r"\bcaugh\b", r"\bchesty\s+cough\b",
        r"\bdry\s+cough\b", r"\bhacking\s+cough\b"
    ],
    "sore throat": [r"\bsore\s+throat\b", r"\bthroat\b[^\.\,\;]{0,25}\b(?:sore|hurts?|pain|scratchy)", r"\bpainful\s+swallowing\b"],
    "congestion": [r"\bcongestion\b", r"\bstuffy\s+nose\b", r"\brunny\s+nose\b", r"\bsneez(?:ing|e|es)\b", r"\bnasal\s+drip\b"],
    "sinus pressure": [r"\bsinus\b[^\.\,\;]{0,25}\b(?:pressure|pain|congestion)", r"\bfacial\s+pressure\b", r"\bcheek\s+pressure\b"],
    "shortness of breath": [r"\bshort(?:ness)?\s+of\s+breath\b", r"\bdifficulty\s+breathing\b", r"\bbreathless(?:ness)?\b", r"\bwheez(?:ing|e)\b"],
    "chest pain": [r"\bchest\b[^\.\,\;]{0,25}\b(?:pain|tightness|pressure|discomfort|heaviness)"],
    "back pain": [r"\bback\b[^\.\,\;]{0,25}\b(?:pain|stiff|ache|sore|spasm)", r"\bbackache\b", r"\blower\s+back\b", r"\bupper\s+back\b"],
    "neck pain": [r"\bneck\b[^\.\,\;]{0,25}\b(?:pain|stiff|ache|sore)", r"\bstiff\b[^\.\,\;]{0,25}\bneck\b", r"\bneck\s+stiffness\b"],
    "abdominal pain": [r"\b(?:stomach|abdominal|belly|gut)\b[^\.\,\;]{0,25}\b(?:pain|ache|cramps?|discomfort)"],
    "diarrhea": [r"\bdiarrhea\b", r"\bloose\s+stools?\b", r"\bwatery\s+stools?\b"],
    "constipation": [r"\bconstipat(?:ed|ion)\b"],
    "joint pain": [r"\bjoint\b[^\.\,\;]{0,25}\b(?:pain|swelling|stiff)", r"\barthr(?:itis|algia)\b", r"\bswollen\s+joints?\b", r"\bbody\s+aches?\b"],
    "rash": [r"\brash\b", r"\bhives\b", r"\bitch(?:y|ing)\b", r"\bskin\s+(?:eruption|irritation|bumps?)\b"],
    "light sensitivity / vision changes": [r"\blight\s+sensitiv(?:e|ity)\b", r"\bphotophobia\b", r"\bblurr(?:y|ed)\s+vision\b", r"\bvision\s+changes?\b"],
    "numbness or tingling": [r"\bnumb(?:ness)?\b", r"\btingling\b", r"\bpins\s+and\s+needles\b", r"\btingl(?:e|ing|y)\b"],
    "leg / knee symptoms": [r"\b(?:leg|knee)\b[^\.\,\;]{0,25}\b(?:weak|weakness|pain|aches?|tingling)"],
    "insomnia / sleep disturbance": [r"\binsomnia\b", r"\btrouble\s+sleeping\b", r"\bcan'?t\s+sleep\b", r"\bwaking\s+up\b"],
    "ear pain": [r"\bear\b[^\.\,\;]{0,25}\b(?:pain|ache|pressure)", r"\bearache\b", r"\btinnitus\b", r"\bclogged\s+ears?\b"],
}


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

        # Turn-specific flags for the latest patient response
        self.turn_new_onset: bool = False
        self.turn_new_severity: bool = False
        self.turn_new_character: bool = False
        self.turn_new_location: bool = False
        self.turn_new_relieving_aggravating: bool = False
        self.turn_new_meds: bool = False
        self.turn_new_allergies: bool = False
        self.turn_new_denials: Set[str] = set()

        self.patient_message_count: int = 0
        self.raw_patient_messages: List[str] = []
        self.last_asked_question: Optional[str] = None

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
            self.turn_new_denials = set()

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
        if is_pure_denial and previous_ai_message:
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
                ("headache", ["headache", "migraine"])
            ]
            found_denials = []
            for canonical, terms in denied_candidates:
                if any(t in prev_lower for t in terms):
                    negated_terms.add(canonical)
                    self.negative_symptoms.add(canonical)
                    found_denials.append(canonical)
            if found_denials and is_latest:
                self.turn_new_denials = set(found_denials)

            # Check if previous question asked if tea/steam/home remedies helped
            if any(w in prev_lower for w in ["warm tea", "steam", "helped", "home remedies"]):
                self.relieving_aggravating = "Home remedies (tea/steam) have not provided significant relief"
                if is_latest:
                    self.turn_new_relieving_aggravating = True

            # Check if previous question asked about medications
            if any(w in prev_lower for w in ["prescription medications", "over-the-counter", "medications", "currently taking any"]):
                if not self.medications:
                    self.medications = "None reported"
                    if is_latest:
                        self.turn_new_meds = True

            # Check if previous question asked about allergies
            if any(w in prev_lower for w in ["known allergies", "allergies to", "allergic to"]):
                if not self.allergies:
                    self.allergies = "No known drug allergies (NKDA)"
                    if is_latest:
                        self.turn_new_allergies = True

            # Check if previous question asked about medical/family history
            if any(w in prev_lower for w in ["personal medical history", "chronic conditions", "family history"]):
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
        if not self.relieving_aggravating or "Home remedies" in self.relieving_aggravating:
            if re.search(r"\b(?:sensitive to light|light sensitivity|photophobia)\b", lower):
                self.relieving_aggravating = "Aggravated by bright light / sensitivity to light"
                if is_latest:
                    self.turn_new_relieving_aggravating = True
            elif re.search(r"\b(?:barely helped|didn't help|did not help|partially helped|helped a bit|helped)\b", lower):
                m = re.search(r"\b([^.,;\n]*(?:barely helped|didn't help|did not help|helped|relieved)[^.,;\n]*)", lower)
                if m:
                    self.relieving_aggravating = m.group(1).strip()
                    if is_latest:
                        self.turn_new_relieving_aggravating = True
            elif any(k in lower for k in ["worse with", "makes it worse", "light makes", "sound makes", "moving makes", "worse when", "aggravated by"]):
                m = re.search(r"\b((?:worse|aggravated)\s+(?:with|when|by)[^.,;\n]+|makes?\s+it\s+worse[^.,;\n]*)", lower)
                if m:
                    self.relieving_aggravating = m.group(1).strip()
                    if is_latest:
                        self.turn_new_relieving_aggravating = True
            elif any(k in lower for k in ["better with", "helps", "relieved by", "better when"]):
                m = re.search(r"\b(better\s+(?:with|when)[^.,;\n]+|relieved\s+by[^.,;\n]+)", lower)
                if m:
                    self.relieving_aggravating = m.group(1).strip()
                    if is_latest:
                        self.turn_new_relieving_aggravating = True

        # 8. Extract Medications
        if not self.medications:
            if any(k in lower for k in ["no meds", "no medication", "not taking any", "don't take any", "none"]):
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
                    pattern = rf"\b{drug}(?:\s+\d+\s*mg)?\b"
                    found = re.findall(pattern, lower)
                    if found:
                        found_meds.extend(found)
                if found_meds:
                    self.medications = ", ".join(dict.fromkeys(found_meds))
                    if is_latest:
                        self.turn_new_meds = True

        # 9. Extract Allergies
        if not self.allergies:
            if re.search(r"\b(?:no\s+(?:known\s+)?(?:drug\s+|food\s+)?allergies|nkda|not\s+allergic|denies\s+allergies|no\s+allergies)\b", lower):
                self.allergies = "No known drug allergies (NKDA)"
                if is_latest:
                    self.turn_new_allergies = True
            else:
                allergy_match = re.search(
                    r"\b(?:allergic\s+to|allergy\s+to|allergies(?:\s+to)?)\s+([a-z\s,]+)\b",
                    lower
                )
                if allergy_match:
                    self.allergies = allergy_match.group(1).strip()
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
        if not self.past_medical_history:
            if any(k in lower for k in ["no medical history", "no chronic conditions", "healthy", "no past illness"]):
                self.past_medical_history = "No chronic conditions reported"
            else:
                conditions = ["asthma", "hypertension", "high blood pressure", "diabetes", "migraines?", "thyroid", "gerd", "acid reflux"]
                found_cond = [c for c in conditions if re.search(rf"\b{c}\b", lower) and "family" not in lower and "mother" not in lower and "father" not in lower]
                if found_cond:
                    self.past_medical_history = ", ".join(dict.fromkeys(found_cond)).capitalize()

        # 11. Extract Family History
        if not self.family_history:
            if any(k in lower for k in ["no family history", "none in family", "family is healthy"]):
                self.family_history = "No significant family history reported"
            elif any(k in lower for k in ["mother", "mom", "father", "dad", "sister", "brother", "parents"]):
                m = re.search(r"\b((?:mother|mom|father|dad|sister|brother|parents?)\s+(?:has|had|suffers|gets)[^.,;\n]+)", lower)
                if m:
                    self.family_history = m.group(1).strip().capitalize()


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
        if role == "ai":
            last_ai_text = content
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
        d_list = [d for d in ["fever", "body aches", "chills"] if d in state.turn_new_denials]
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

    # 4. Patient answered onset and/or severity in follow-up turn (turn > 1)
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

    # 5. Patient answered character/quality only
    if state.turn_new_character and state.character:
        char_val = state.character.split(",")[-1].strip()
        return f"Understood, I've noted that it feels {char_val}."

    # 6. Patient provided medications and/or allergies
    if state.turn_new_meds or state.turn_new_allergies:
        recorded = []
        if state.turn_new_meds and state.medications:
            if state.medications == "None reported":
                recorded.append("you are not currently taking any medications")
            else:
                recorded.append(f"you took {state.medications}")
        if state.turn_new_allergies and state.allergies:
            if state.allergies == "No known drug allergies (NKDA)":
                recorded.append("you have no known allergies")
            else:
                recorded.append(f"your allergies ({state.allergies})")
        return f"Understood, I have recorded that {', and '.join(recorded)}."

    # 7. Relieving / aggravating factors
    if state.turn_new_relieving_aggravating and state.relieving_aggravating:
        return f"I've noted what affects your symptoms ({state.relieving_aggravating})."

    # 8. General listener fallback
    return "Thank you for explaining that. I have noted this down in your consultation record."


def is_question_safe(
    question: str,
    state: ClinicalDialogueState,
    previous_ai_message: Optional[str] = None
) -> bool:
    """
    Validates that a proposed question strictly avoids asking for any attribute
    or symptom that the patient has already answered, explicitly denied,
    or was already asked in the immediate previous AI turn.
    """
    q_lower = question.lower().strip()

    # 1. Immediate previous message deduplication
    if previous_ai_message:
        prev_lower = previous_ai_message.lower().strip()
        # Direct match or substring match
        if q_lower in prev_lower or prev_lower in q_lower:
            return False
        # Specific topic overlap checks with previous AI message
        if ("fever" in prev_lower or "chills" in prev_lower) and ("fever" in q_lower or "chills" in q_lower):
            return False
        if ("scale of 1 to 10" in prev_lower or "rate the discomfort" in prev_lower) and ("scale of 1 to 10" in q_lower or "rate the discomfort" in q_lower):
            return False
        if ("warm tea" in prev_lower or "steam" in prev_lower) and ("warm tea" in q_lower or "steam" in q_lower):
            return False
        if ("medication" in prev_lower or "prescription" in prev_lower) and ("medication" in q_lower or "prescription" in q_lower):
            return False
        if ("allerg" in prev_lower) and ("allerg" in q_lower):
            return False
        if ("medical history" in prev_lower or "chronic condition" in prev_lower) and ("medical history" in q_lower or "chronic condition" in q_lower):
            return False

    # 2. State-based dimension checks
    if state.severity and any(k in q_lower for k in ["scale of 1 to 10", "rate the discomfort", "how intense", "on a scale", "1 to 10", "rate your"]):
        return False
    if state.onset_duration and any(k in q_lower for k in ["how long", "when did", "start suddenly", "how long have you"]):
        return False
    if state.character and any(k in q_lower for k in ["dry or", "mucus", "what the sensation feels like", "is it sharp"]):
        return False
    if state.medications and any(k in q_lower for k in ["currently taking any", "prescription medications", "over-the-counter"]):
        return False
    if state.allergies and any(k in q_lower for k in ["known allergies", "allergic to"]):
        return False
    if state.past_medical_history and any(k in q_lower for k in ["personal medical history", "chronic conditions", "family history"]):
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
    missing from the clinical picture. NEVER repeats any question whose attribute
    has already been provided in state.answered_dimensions or in the previous AI turn.
    """
    answered = state.answered_dimensions
    prev_lower = (previous_ai_message or state.last_asked_question or "").lower()

    # Priority 1: Newly introduced symptoms midway through conversation (turn > 1)
    if state.new_symptoms_in_turn and state.patient_message_count > 1:
        new_sym_list = list(state.new_symptoms_in_turn)
        new_sym = " and ".join(new_sym_list)
        prior_sym = [s for s in state.symptoms if s not in state.new_symptoms_in_turn]
        if prior_sym:
            q = f"Did the {new_sym} start around the same time as the {prior_sym[0]}, or did it begin later?"
            if is_question_safe(q, state, previous_ai_message):
                return q
        else:
            q = f"When did the {new_sym} start, and how intense does it feel?"
            if is_question_safe(q, state, previous_ai_message):
                return q

    # Priority 2: Unanswered part of a previous compound question
    if any(w in prev_lower for w in ["dry or", "mucus", "phlegm"]) and "character" not in answered and "cough" in state.symptoms:
        q = "Is the cough dry, or are you bringing up any mucus?"
        if is_question_safe(q, state, previous_ai_message):
            return q

    # Priority 3: Inquire about missing clinical dimensions
    candidates = []

    # 1. Onset / Duration
    if "onset" not in answered and "duration" not in answered:
        if "cough" in state.symptoms and "character" not in answered:
            candidates.append("When did your cough start, and is it dry or are you bringing up mucus?")
        else:
            candidates.append("Approximately how long have you been noticing these symptoms, and did they come on suddenly or gradually?")

    # 2. Severity (1 to 10 scale)
    if "severity" not in answered:
        candidates.append("On a scale of 1 to 10 (with 1 being very mild and 10 being severe), how would you rate the discomfort?")

    # 3. Character / Quality
    if "character" not in answered:
        if "cough" in state.symptoms:
            candidates.append("Is the cough dry, or are you bringing up any mucus?")
        elif "headache" in state.symptoms:
            candidates.append("Could you describe what the headache feels like (for example, is it throbbing, sharp, dull, or feeling like pressure)?")
        elif "abdominal pain" in state.symptoms:
            candidates.append("Is the abdominal discomfort sharp, cramping, burning, or dull?")
        else:
            candidates.append("Could you describe what the sensation feels like (for example, is it sharp, dull, aching, or burning)?")

    # 4. Relieving / Aggravating factors & Triggers
    if "relieving_aggravating" not in answered:
        if any(s in state.symptoms for s in ["cough", "congestion", "sinus pressure", "sore throat"]):
            if "fever" not in state.negative_symptoms and "chills" not in state.negative_symptoms:
                candidates.append("Are you noticing any fever, body aches, or chills alongside this, and has any warm tea or steam helped?")
            else:
                candidates.append("Has anything helped relieve your cough so far, or does anything trigger worse coughing spells?")
        elif "headache" in state.symptoms:
            candidates.append("Have you noticed if bright lights, sound, or physical activity makes it worse, or has anything helped provide relief?")
        else:
            candidates.append("Have you noticed anything that makes the symptoms feel better or worse, or anything you've tried that provided relief?")

    # 5. Medications
    if "medications" not in answered:
        candidates.append("Are you currently taking any prescription medications, over-the-counter remedies, or supplements for this or other health conditions?")

    # 6. Allergies
    if "allergies" not in answered:
        candidates.append("Do you have any known allergies, especially to medications or foods?")

    # 7. Past Medical / Family History
    if "history" not in answered:
        candidates.append("Do you have any personal medical history, chronic conditions, or family history related to these concerns?")

    # Find first candidate passing strict safety check
    for cand in candidates:
        if is_question_safe(cand, state, previous_ai_message):
            return cand

    # Priority 4: All core dimensions collected -> Wrap-up completion invitation
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
        + ". Whenever you feel ready, please click **'Finish Consultation'** below to review your structured 11-section clinical note, "
        "or feel free to share any other details you would like included."
    )
