"""
Gemini API Service for RevitAI Chatbot.
Provides structured intent classification, entity extraction, and typo normalization.
Includes a robust deterministic fallback classifier when GEMINI_API_KEY is not configured or unavailable.
"""

import json
import os
import re
from dotenv import load_dotenv

load_dotenv()

try:
    from google import genai
    from google.genai import types
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False


# ============================================================
# GEMINI CLIENT SETUP
# ============================================================

def get_genai_client():
    if not HAS_GENAI:
        return None
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or not api_key.strip() or "YOUR_" in api_key or api_key == "YOUR_API_KEY":
        return None
    try:
        return genai.Client(api_key=api_key.strip())
    except Exception as e:
        print("Error initializing Gemini client:", e)
        return None


SYSTEM_PROMPT = """You are the Intent Classification and Entity Extraction engine for RevitAI, an AI Assistant for Autodesk Revit.

Your job is to classify the user's message into one of these strict intents:
- GENERAL_CONVERSATION: Normal greetings, small talk, casual check-ins, social phrases, personal inquiries, farewells (e.g. hello, hi, helo, ello, how are you, how was ur day, whats up, are you okay, tell me about yourself, thanks, bye, okay).
- HELP: Questions about what RevitAI can do or how to use it (e.g. what can you do, help, commands, how to use).
- PROJECT_INFO: User is asking about the active or current Revit project, file, or model name (e.g. what project am I working on, which project is open, what revit file am i using, current project, current model, project info, show project info).
- REVIT_SEARCH: User wants to search or find specific Revit views, floor plans, levels, rooms, walls, sheets, schedules, elevations, 3D views (e.g. show me L3 floor plan, find rooms on L5, L3 wall plans).
- REVIT_ACTION: User explicitly wants to open a view in Revit (e.g. open L1 floor plan, open Rooms - L5).
- FOLLOW_UP: User is referring to a previous search or result (e.g. only wall plans, open the first one, what about level 3, no I meant L5).
- CLARIFICATION_REQUIRED: Message is ambiguous, too short without context, or intent confidence is low.

Typo handling:
- Correct obvious typos in user message (e.g. "ello" -> "hello", "hw was ur day" -> "how was your day", "wats up" -> "whats up", "r u ok" -> "are you okay", "flor" -> "floor", "roms" -> "rooms", "wal" -> "wall", "saftey" -> "safety").
- IMPORTANT: Conversational messages or conversational typos MUST remain GENERAL_CONVERSATION or HELP. They must NEVER become REVIT_SEARCH.

Entities to extract:
- level: normalized level string like "L1", "L2", "L3", "L4", "L5", "M1", "B1", "Roof" (if mentioned).
- category: e.g. "wall", "rooms", "door", "window", "toilet", "life safety", "furniture".
- viewType: e.g. "FloorPlan", "CeilingPlan", "Section", "Elevation", "ThreeD", "Schedule", "DrawingSheet", "AreaPlan", "Detail", "StructuralPlan".
- action: "SEARCH" or "OPEN".
- resultIndex: integer 0-indexed if user refers to a specific result index like "first one" -> 0, "#2" -> 1.

Respond ONLY with a valid JSON object with this exact structure:
{
  "intent": "GENERAL_CONVERSATION" | "HELP" | "PROJECT_INFO" | "REVIT_SEARCH" | "REVIT_ACTION" | "FOLLOW_UP" | "CLARIFICATION_REQUIRED",
  "confidence": 0.98,
  "normalizedQuery": "corrected message",
  "entities": {
    "level": "L3" or null,
    "category": "wall" or null,
    "viewType": "FloorPlan" or null,
    "action": "SEARCH" or "OPEN" or null,
    "resultIndex": 0 or null
  },
  "conversationalResponse": "friendly natural response for conversation, help, or clarification" or null
}
"""


# ============================================================
# DETERMINISTIC FALLBACK CLASSIFIER
# ============================================================

TYPO_MAP = {
    # Conversational typos & shortcuts
    "ello": "hello",
    "helo": "hello",
    "helllo": "hello",
    "hii": "hi",
    "hiii": "hi",
    "hiiii": "hi",
    "heyy": "hey",
    "heyyy": "hey",
    "thx": "thanks",
    "thnx": "thanks",
    "hw": "how",
    "ur": "your",
    "u": "you",
    "r": "are",
    "abt": "about",
    "wats": "whats",
    "wat": "what",
    "wazzup": "whats up",
    "ok": "okay",
    "okayy": "okay",
    # Domain typos
    "flor": "floor",
    "fllor": "floor",
    "floorr": "floor",
    "levl": "level",
    "leval": "level",
    "lvl": "level",
    "vieww": "view",
    "vew": "view",
    "wal": "wall",
    "wallls": "wall",
    "strucural": "structural",
    "wwall": "wall",
    "wwalls": "walls",
    "rom": "room",
    "roms": "rooms",
    "toilt": "toilet",
    "tolet": "toilet",
    "bathrom": "bathroom",
    "staircas": "staircase",
    "corridr": "corridor",
    "saftey": "safety",
    "elevatn": "elevation",
    "elvation": "elevation",
    "sectn": "section",
    "sechtion": "section",
    "schedul": "schedule",
}

GREETINGS = {
    "hello", "hi", "hey", "greetings", "good morning", "good afternoon", "good evening",
    "bye", "goodbye", "see you", "okay", "ok", "nice", "great", "perfect", "cool",
}

THANKS = {
    "thanks", "thank you", "thanks a lot", "thank you so much", "thank you very much",
}

SMALL_TALK = {
    "how are you", "how are u", "how r u", "how are you doing", "how is it going", "hows it going",
    "how was your day", "how was ur day", "how is your day", "hows your day",
    "whats up", "what s up", "sup", "wats up", "wat up", "what up",
    "are you okay", "are u ok", "are u okay", "r u ok", "r u okay", "are you fine", "are u fine",
    "who are you", "who r u", "what is your name", "whats your name",
    "who created you", "who made you", "are you an ai", "are you a bot",
    "tell me about yourself", "tell me abt yourself", "tell me about u", "tell me abt u", "tell me about your self",
    "tell me something", "can you help me", "i need help",
}

PROJECT_INFO_PHRASES = {
    "what project am i working on",
    "which project am i working on",
    "what revit project is open",
    "which revit file is open",
    "what file am i working on",
    "tell me the current project",
    "what project is this",
    "what model am i working on",
    "which model is currently open",
    "whats the current revit project",
    "what is the current revit project",
    "current project",
    "current model",
    "current revit project",
    "current file",
    "what project am i on",
    "which project is open",
    "what revit file am i using",
    "tell me which model is open",
    "what model is open",
    "what file is open",
    "tell me current project",
    "which model is open",
    "what model am i on",
    "which model am i on",
    "project info",
    "current project info",
    "show project info",
    "show current project info",
    "active project",
    "active project info",
    "show active project",
    "tell me the active project name",
    "active project name",
    "project name",
}

ADDRESSING_TERMS = {
    "revit", "revitai", "assistant", "bot", "ai", "there", "mr", "sir", "bro", "man",
    "buddy", "dude", "mate", "friend", "guy", "guys",
}


def normalize_query(query: str) -> str:
    if not query:
        return ""
    text = str(query).lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    words = text.split()
    corrected_words = []
    for w in words:
        if w in TYPO_MAP:
            corrected_words.append(TYPO_MAP[w])
        elif re.fullmatch(r"h+i+", w):
            corrected_words.append("hi")
        elif re.fullmatch(r"h+e+y+", w):
            corrected_words.append("hey")
        elif re.fullmatch(r"h+e+l+o+", w):
            corrected_words.append("hello")
        else:
            corrected_words.append(w)
    return " ".join(corrected_words)


def strip_addressing_words(text: str) -> str:
    words = text.split()
    while words and words[-1] in ADDRESSING_TERMS:
        words.pop()
    while words and words[0] in ADDRESSING_TERMS:
        words.pop(0)
    return " ".join(words)


def extract_entities_fallback(text: str) -> dict:
    entities = {
        "level": None,
        "category": None,
        "viewType": None,
        "action": "SEARCH",
        "resultIndex": None,
    }

    # Action detection
    if any(term in text for term in ["open", "take me to", "go to", "navigate to"]):
        entities["action"] = "OPEN"

    # Level extraction
    level_match = re.search(r"\b(l|level)\s*[-]?\s*(\d+)\b", text)
    if level_match:
        entities["level"] = f"L{level_match.group(2)}"

    if not entities["level"]:
        ordinals = [
            ("first floor", "L1"), ("1st floor", "L1"), ("floor 1", "L1"), ("ground floor", "L1"),
            ("second floor", "L2"), ("2nd floor", "L2"), ("floor 2", "L2"),
            ("third floor", "L3"), ("3rd floor", "L3"), ("floor 3", "L3"),
            ("fourth floor", "L4"), ("4th floor", "L4"), ("floor 4", "L4"),
            ("fifth floor", "L5"), ("5th floor", "L5"), ("floor 5", "L5"),
        ]
        for phrase, lvl in ordinals:
            if phrase in text:
                entities["level"] = lvl
                break

    # View type
    if any(p in text for p in ["structural plan", "structural plans", "structural floor plan", "structural layout", "structural levels"]):
        entities["viewType"] = "StructuralPlan"
    elif any(p in text for p in ["floor plan", "floor plans", "floorplan", "floorplans", "plan", "plans"]):
        entities["viewType"] = "FloorPlan"
    elif any(p in text for p in ["ceiling plan", "ceiling plans", "ceilingplan", "ceilingplans", "reflected ceiling"]):
        entities["viewType"] = "CeilingPlan"
    elif any(p in text for p in ["3d", "three dimensional", "model view"]):
        entities["viewType"] = "ThreeD"
    elif "elevation" in text:
        entities["viewType"] = "Elevation"
    elif "section" in text:
        entities["viewType"] = "Section"
    elif "schedule" in text:
        entities["viewType"] = "Schedule"
    elif "sheet" in text:
        entities["viewType"] = "DrawingSheet"

    # Category
    categories = ["wall", "walls", "room", "rooms", "toilet", "bathroom", "life safety", "door", "window", "furniture", "site"]
    for cat in categories:
        if cat in text:
            entities["category"] = cat.rstrip("s") if cat in ["walls", "rooms"] else cat
            break

    # Follow-up result index
    idx_patterns = [
        (r"\b(first|1st)(\s+one|\s+result|\s+view)?\b", 0),
        (r"\b#?1\b", 0),
        (r"\b(second|2nd)(\s+one|\s+result|\s+view)?\b", 1),
        (r"\b#?2\b", 1),
        (r"\b(third|3rd)(\s+one|\s+result|\s+view)?\b", 2),
        (r"\b#?3\b", 2),
        (r"\b(fourth|4th)(\s+one|\s+result|\s+view)?\b", 3),
        (r"\b#?4\b", 3),
        (r"\b(fifth|5th)(\s+one|\s+result|\s+view)?\b", 4),
        (r"\b#?5\b", 4),
    ]
    for pat, idx in idx_patterns:
        if re.search(pat, text):
            if not entities["level"]:
                entities["resultIndex"] = idx
                break

    return entities


def fallback_intent_classifier(user_message: str, session_context: dict | None = None) -> dict:
    norm = normalize_query(user_message)
    cleaned = strip_addressing_words(norm)

    # 1. Ambiguous prompt check before search
    if norm in {"open something", "open the thing", "show me something", "show something", "find something"} or cleaned in {"open something", "show me something", "show something", "find something"}:
        return {
            "intent": "CLARIFICATION_REQUIRED",
            "confidence": 0.50,
            "normalizedQuery": norm,
            "entities": extract_entities_fallback(norm),
            "conversationalResponse": (
                "What would you like me to find in the Revit model? You can specify a view, sheet, level, or element."
            ),
        }

    # 2. PROJECT_INFO Check
    entities = extract_entities_fallback(norm)
    is_project_info = (
        (
            norm in PROJECT_INFO_PHRASES
            or cleaned in PROJECT_INFO_PHRASES
            or any(
                p in norm or p in cleaned
                for p in [
                    "what project am i", "which project am i", "what revit project",
                    "which revit project", "what project is", "which project is",
                    "what model am i", "which model am i", "what file am i",
                    "which file am i", "what model is open", "which model is open",
                    "what file is open", "which file is open", "what revit file",
                    "which revit file", "tell me the current project", "tell me which project",
                    "tell me which model", "current revit project", "project info",
                    "current project info", "active project info", "active project",
                    "project name", "current project", "active model",
                ]
            )
        )
        and entities.get("level") is None
    )

    if is_project_info:
        return {
            "intent": "PROJECT_INFO",
            "confidence": 0.99,
            "normalizedQuery": norm,
            "entities": {
                "level": None,
                "category": None,
                "viewType": None,
                "action": None,
                "resultIndex": None,
            },
            "conversationalResponse": None,
        }

    # 3. GENERAL_CONVERSATION Check
    is_greeting = norm in GREETINGS or cleaned in GREETINGS
    is_thanks = norm in THANKS or cleaned in THANKS
    is_small_talk = (
        norm in SMALL_TALK
        or cleaned in SMALL_TALK
        or any(st in norm or st in cleaned for st in [
            "how was your day", "how was ur day", "how is your day", "hows your day",
            "whats up", "what s up", "wats up", "sup", "what up",
            "are you okay", "are u ok", "are u okay", "r u ok", "r u okay", "are you fine", "are u fine",
            "tell me about yourself", "tell me abt yourself", "tell me about u", "tell me abt u", "tell me about your self",
            "how are you", "how are u", "how r u", "how are you doing", "how is it going",
            "who are you", "who r u", "what is your name", "whats your name",
        ])
    )

    # Guard against queries containing explicit Revit search directives (e.g., "show me the view named Hello")
    if any(p in norm for p in ["show me", "find ", "open ", "search ", "named ", "called "]):
        is_greeting = False
        is_thanks = False
        is_small_talk = False

    if is_greeting or is_thanks or is_small_talk:
        if "how was" in norm or "how is your day" in norm:
            resp = "My day is going great, thank you for asking! 😊 I'm here and ready to help you navigate your Revit model. What view can I find for you?"
        elif "are you okay" in norm or "r u ok" in norm or "are u ok" in norm:
            resp = "I'm doing great, thank you! Ready to assist you with any Revit views or floor plans you need."
        elif "tell me about yourself" in norm or "tell me abt" in norm or "who are you" in norm:
            resp = "I am RevitAI, your intelligent AI assistant built to search, navigate, and manage Autodesk Revit models through natural conversation!"
        elif "whats up" in norm or "wats up" in norm or "sup" in norm:
            resp = "Not much! Just here and ready to help with your Revit project. What view would you like to explore?"
        elif is_thanks:
            resp = "You're very welcome! Let me know if you need anything else from your Revit model."
        else:
            resp = "Hello! 👋 I am your RevitAI Assistant. How can I help you navigate or find views in your Revit model today?"

        return {
            "intent": "GENERAL_CONVERSATION",
            "confidence": 0.99,
            "normalizedQuery": norm,
            "entities": {
                "level": None,
                "category": None,
                "viewType": None,
                "action": None,
                "resultIndex": None,
            },
            "conversationalResponse": resp,
        }

    # 4. HELP
    if any(
        h in norm or h in cleaned
        for h in ["what can you do", "help", "commands", "how to use", "what views", "who are you"]
    ):
        return {
            "intent": "HELP",
            "confidence": 0.98,
            "normalizedQuery": norm,
            "entities": {
                "level": None,
                "category": None,
                "viewType": None,
                "action": None,
                "resultIndex": None,
            },
            "conversationalResponse": (
                "I can help you search and open views in your active Revit project using natural language.\n\n"
                "Examples you can try:\n"
                "• 'Open L1' or 'Open Level 1'\n"
                "• 'Show me the first floor plan'\n"
                "• 'Show me the 3D view'\n"
                "• 'Find elevations' or 'Find sections'\n"
                "• 'Show Level 2 ceiling plan'"
            ),
        }

    entities = extract_entities_fallback(norm)

    # 5. FOLLOW_UP / RESULT SELECTION / CORRECTION
    if entities["resultIndex"] is not None:
        return {
            "intent": "FOLLOW_UP",
            "confidence": 0.95,
            "normalizedQuery": norm,
            "entities": entities,
            "conversationalResponse": None,
        }

    if session_context and (
        session_context.get("results")
        or session_context.get("current_level")
        or session_context.get("current_view_type")
        or session_context.get("current_category")
    ):
        is_correction = any(
            norm.startswith(p)
            for p in ["no i meant", "actually", "i meant", "not ", "change that to", "same thing but", "only ", "what about"]
        )
        if is_correction:
            return {
                "intent": "FOLLOW_UP",
                "confidence": 0.95,
                "normalizedQuery": norm,
                "entities": entities,
                "conversationalResponse": None,
            }

    # 6. REVIT_SEARCH / REVIT_ACTION
    has_revit_indicators = (
        entities["level"] is not None
        or entities["viewType"] is not None
        or entities["category"] is not None
        or any(w in norm for w in ["find", "search", "show", "open", "view", "views", "plan", "level", "floor", "section", "elevation", "sheet"])
    )

    if has_revit_indicators:
        intent = "REVIT_ACTION" if entities["action"] == "OPEN" else "REVIT_SEARCH"
        return {
            "intent": intent,
            "confidence": 0.95,
            "normalizedQuery": norm,
            "entities": entities,
            "conversationalResponse": None,
        }

    # 7. CLARIFICATION_REQUIRED (Default fallback)
    return {
        "intent": "CLARIFICATION_REQUIRED",
        "confidence": 0.50,
        "normalizedQuery": norm,
        "entities": entities,
        "conversationalResponse": (
            "I'm not sure which Revit view you're looking for. "
            "Could you specify a level or view type? For example: 'Open L1 floor plan' or 'Show 3D view'."
        ),
    }


# ============================================================
# MAIN GEMINI CLASSIFICATION API
# ============================================================

def classify_intent_with_gemini(user_message: str, session_context: dict | None = None) -> dict:
    client = get_genai_client()
    if client is None:
        return fallback_intent_classifier(user_message, session_context)

    try:
        context_str = ""
        if session_context:
            last_level = session_context.get("current_level")
            last_vtype = session_context.get("current_view_type")
            last_cat = session_context.get("current_category")
            if last_level or last_vtype or last_cat:
                context_str = f"\nPrevious Session Context: Level={last_level}, ViewType={last_vtype}, Category={last_cat}"

        prompt = f"User Message: {user_message}{context_str}"

        model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
                temperature=0.1,
            ),
        )

        raw_text = response.text.strip()
        data = json.loads(raw_text)

        if "intent" in data and "confidence" in data:
            return data

    except Exception as e:
        print("Gemini API call failed or timed out:", e)
        print("Using deterministic fallback intent classifier.")

    return fallback_intent_classifier(user_message, session_context)
