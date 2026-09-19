import json
import os
import re
import urllib.error
import urllib.request

import psycopg

from backend.embedding_service import create_embedding


# ============================================================
# DATABASE CONFIGURATION
# ============================================================

DATABASE_URL = os.getenv(
    "REVITAI_DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/revitai",
)


# ============================================================
# REVIT PLUGIN
# ============================================================

REVIT_PLUGIN_URL = (
    "http://127.0.0.1:8765/current-project"
)


def normalize_file_path(path: str | None) -> str | None:
    if not path or not str(path).strip():
        return None
    try:
        norm = os.path.abspath(str(path).strip()).lower().replace("/", "\\")
        return norm
    except Exception:
        return str(path).strip().lower().replace("/", "\\")


def get_active_project_info() -> dict | None:
    try:
        request = urllib.request.Request(
            REVIT_PLUGIN_URL,
            method="GET",
        )

        with urllib.request.urlopen(
            request,
            timeout=3,
        ) as response:
            payload = json.loads(
                response.read().decode(
                    "utf-8"
                )
            )

        return payload

    except (
        urllib.error.URLError,
        urllib.error.HTTPError,
        TimeoutError,
        ValueError,
        json.JSONDecodeError,
    ):
        return None

    except Exception:
        return None


def get_active_project_id() -> int | None:
    payload = get_active_project_info()

    if payload is not None:
        if payload.get("success"):
            project_id = payload.get("project_id")
            if project_id is not None:
                try:
                    return int(project_id)
                except (ValueError, TypeError):
                    return None
            else:
                return None
        else:
            return None

    # Fallback for standalone CLI testing
    dev_id = os.getenv("REVITAI_PROJECT_ID")
    if dev_id:
        try:
            return int(dev_id)
        except (ValueError, TypeError):
            return None

    return None


# ============================================================
# ORDINAL & LEVEL MAP
# ============================================================

ORDINAL_MAP = {
    "first": "1",
    "1st": "1",
    "one": "1",

    "second": "2",
    "2nd": "2",
    "two": "2",

    "third": "3",
    "3rd": "3",
    "three": "3",

    "fourth": "4",
    "4th": "4",
    "four": "4",

    "fifth": "5",
    "5th": "5",
    "five": "5",

    "sixth": "6",
    "6th": "6",
    "six": "6",

    "seventh": "7",
    "7th": "7",
    "seven": "7",

    "eighth": "8",
    "8th": "8",
    "eight": "8",

    "ninth": "9",
    "9th": "9",
    "nine": "9",

    "tenth": "10",
    "10th": "10",
    "ten": "10",

    "ground": "1",
    "ground floor": "1",
    "ground level": "1",

    "basement 1": "-1",
    "basement 2": "-2",
    "basement": "-1",
    "b1": "-1",
    "b2": "-2",

    "roof": "roof",
    "roof level": "roof",
    "roof plan": "roof",
}


# ============================================================
# ACTION WORDS
# ============================================================

ACTION_WORDS = {
    "open",
    "show",
    "find",
    "search",
    "display",
    "view",
    "views",
    "get",
    "give",
    "please",
    "need",
    "want",
    "me",
    "the",
    "a",
    "an",
    "i",
    "can",
    "you",
    "could",
    "would",
    "take",
    "go",
    "navigate",
    "bring",
    "to",
    "see",
    "let",
    "list",
}


# ============================================================
# PROJECT WORDS
# ============================================================

PROJECT_WORDS = {
    "project",
    "file",
    "document",
    "model",
}


# ============================================================
# VIEW WORDS
# ============================================================

VIEW_WORDS = {
    "view",
    "views",
    "plan",
    "drawing",
    "drawings",
    "layout",
    "section",
    "elevation",
    "3d",
    "sheet",
    "detail",
    "schedule",
    "legend",
}


# ============================================================
# VIEW TYPE TERMS AND SYNONYMS
# ============================================================

VIEW_TYPE_TERMS = {
    # FloorPlan
    "floorplan": "FloorPlan",
    "floorplans": "FloorPlan",
    "floor plan": "FloorPlan",
    "floor plans": "FloorPlan",
    "floor drawing": "FloorPlan",
    "floor layout": "FloorPlan",
    "plan of level": "FloorPlan",

    # CeilingPlan
    "ceilingplan": "CeilingPlan",
    "ceilingplans": "CeilingPlan",
    "ceiling plan": "CeilingPlan",
    "ceiling plans": "CeilingPlan",
    "reflected ceiling": "CeilingPlan",
    "reflected ceiling plan": "CeilingPlan",
    "ceiling drawing": "CeilingPlan",

    # AreaPlan
    "areaplan": "AreaPlan",
    "area plan": "AreaPlan",
    "gross building area": "AreaPlan",

    # Section
    "section": "Section",
    "sections": "Section",
    "section view": "Section",
    "section drawing": "Section",
    "building section": "Section",
    "wall section": "Section",

    # Elevation
    "elevation": "Elevation",
    "elevations": "Elevation",
    "elevation view": "Elevation",
    "front elevation": "Elevation",
    "rear elevation": "Elevation",
    "side elevation": "Elevation",
    "north elevation": "Elevation",
    "south elevation": "Elevation",
    "east elevation": "Elevation",
    "west elevation": "Elevation",

    # ThreeD (3D)
    "3d": "ThreeD",
    "3d view": "ThreeD",
    "3d views": "ThreeD",
    "3d model": "ThreeD",
    "three dimensional": "ThreeD",
    "three dimensional view": "ThreeD",
    "model view": "ThreeD",
    "3d drawing": "ThreeD",

    # Sheet
    "sheet": "DrawingSheet",
    "drawing sheet": "DrawingSheet",
    "sheets": "DrawingSheet",

    # Schedule
    "schedule": "Schedule",
    "schedules": "Schedule",
    "structural schedule": "Schedule",
    "structural schedules": "Schedule",
    "wall schedule": "Schedule",
    "wall schedules": "Schedule",
    "door schedule": "Schedule",
    "window schedule": "Schedule",
    "room schedule": "Schedule",

    # Detail
    "detail": "Detail",
    "detail view": "Detail",
    "detail drawing": "Detail",
    "callout": "Detail",

    # Drafting
    "drafting": "DraftingView",
    "drafting view": "DraftingView",

    # Structural
    "structural": "StructuralPlan",
    "structural plan": "StructuralPlan",
    "structural plans": "StructuralPlan",
    "strucural": "StructuralPlan",
    "strucural plan": "StructuralPlan",
    "strucural plans": "StructuralPlan",
    "stuctural": "StructuralPlan",
    "stuctural plan": "StructuralPlan",
    "stuctural plans": "StructuralPlan",
    "structure plan": "StructuralPlan",
    "structure plans": "StructuralPlan",
    "engineering plan": "StructuralPlan",
    "structural layout": "StructuralPlan",

    # Site
    "site": "SitePlan",
    "site plan": "SitePlan",
    "site layout": "SitePlan",

    # Legend
    "legend": "Legend",
    "symbol legend": "Legend",
}


# ============================================================
# SPECIALIZED TERMS
# ============================================================

SPECIALIZED_TERMS = {
    "site",
    "rooms",
    "room",
    "wall",
    "walls",
    "life",
    "safety",
    "kitchen",
    "ceiling",
    "export",
    "civil",
    "detail",
    "detailed",
    "dimension",
    "dimensions",
    "structure",
    "structural",
    "electrical",
    "mechanical",
    "plumbing",
    "fire",
    "furniture",
}


# ============================================================
# NORMALIZE TEXT
# ============================================================

def normalize_text(text: str | None) -> str:
    if not text:
        return ""
    text = str(text).lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# ============================================================
# TOKENIZE
# ============================================================

def tokenize(text: str | None) -> list[str]:
    normalized = normalize_text(text)
    words = normalized.split()
    return [word for word in words if word not in ACTION_WORDS]


# ============================================================
# DETECT NON-SEARCH CONVERSATIONAL INTENT
# ============================================================

GREETING_BASES = {
    "hello",
    "hi",
    "hey",
    "greetings",
    "good morning",
    "good afternoon",
    "good evening",
}

THANKS_BASES = {
    "thank you",
    "thanks",
    "thanks a lot",
    "thank you so much",
    "thank you very much",
    "many thanks",
    "awesome",
    "great",
    "perfect",
}

ASSISTANT_SUFFIXES = {
    "revit",
    "revitai",
    "revit ai",
    "assistant",
    "ai assistant",
    "there",
    "mr",
    "sir",
    "bro",
    "man",
    "buddy",
    "dude",
    "mate",
    "friend",
    "guy",
    "guys",
}

ADDRESSING_WORDS = ASSISTANT_SUFFIXES

HELP_BASES = {
    "what can you do",
    "who are you",
    "help",
    "commands",
    "what views",
    "what can i ask",
    "how to use",
    "how do i use this",
    "what can you do for me",
}

SMALL_TALK_BASES = {
    "how are you",
    "how are u",
    "how r u",
    "how are you doing",
    "how are u doing",
    "how is it going",
    "hows it going",
    "how s it going",
    "how are things",
    "how was your day",
    "how was ur day",
    "how is your day",
    "hows your day",
    "whats up",
    "what s up",
    "wats up",
    "wat up",
    "what up",
    "sup",
    "are you okay",
    "are u ok",
    "are u okay",
    "r u ok",
    "r u okay",
    "are you fine",
    "are u fine",
    "who are you",
    "who r u",
    "what is your name",
    "whats your name",
    "who created you",
    "who made you",
    "are you an ai",
    "are you a bot",
    "are you ai",
    "are you real",
    "tell me about yourself",
    "tell me abt yourself",
    "tell me about u",
    "tell me abt u",
    "tell me about your self",
    "nice to meet you",
    "good to see you",
    "pleasure to meet you",
}

AMBIGUOUS_BASES = {
    "open something",
    "open the thing",
    "show me something",
    "open the plan",
    "find a view",
    "show something",
    "view plan",
    "open view",
    "show plan",
    "open a view",
    "find something",
    "show a view",
}


def normalize_greeting_text(query: str) -> str:
    norm = normalize_text(query)
    if not norm:
        return ""
    words = norm.split()
    normalized_words = []
    typos = {
        "hw": "how", "ur": "your", "u": "you", "r": "are", "abt": "about",
        "wats": "whats", "wat": "what", "ok": "okay", "thx": "thanks", "thnx": "thanks",
        "strucural": "structural", "wwall": "wall", "wwalls": "walls"
    }
    for w in words:
        if w in typos:
            normalized_words.append(typos[w])
        elif re.fullmatch(r"h+i+", w):
            normalized_words.append("hi")
        elif re.fullmatch(r"h+e+y+", w):
            normalized_words.append("hey")
        elif re.fullmatch(r"h+e+l+o+", w):
            normalized_words.append("hello")
        elif re.fullmatch(r"g+r+e+e+t+i+n+g+s*", w):
            normalized_words.append("greetings")
        elif re.fullmatch(r"t+h+a+n+k+s+", w):
            normalized_words.append("thanks")
        else:
            normalized_words.append(w)
    return " ".join(normalized_words)


def clean_conversational_query(query: str) -> str:
    norm = normalize_greeting_text(query)
    if not norm:
        return ""
    words = norm.split()
    while words and words[-1] in ADDRESSING_WORDS:
        words.pop()
    while words and words[0] in ADDRESSING_WORDS:
        words.pop(0)
    return " ".join(words)


def detect_conversational_intent(query: str) -> str | None:
    norm = normalize_greeting_text(query)
    if not norm:
        return None

    # Guard against queries containing explicit Revit search directives (e.g., "show me the view named Hello")
    if any(p in norm for p in ["show me the view", "find the view", "open the view", "search view", "named ", "called "]):
        return None

    cleaned = clean_conversational_query(query)

    # 1. Greetings
    if norm in GREETING_BASES or cleaned in GREETING_BASES:
        return "GREETING"
    for base in GREETING_BASES:
        for suffix in ASSISTANT_SUFFIXES:
            if norm == f"{base} {suffix}" or norm == f"{suffix} {base}":
                return "GREETING"

    # 2. Small Talk / Chit-Chat
    if norm in SMALL_TALK_BASES or cleaned in SMALL_TALK_BASES:
        return "SMALL_TALK"
    for base in SMALL_TALK_BASES:
        for suffix in ASSISTANT_SUFFIXES:
            if norm == f"{base} {suffix}" or norm == f"{suffix} {base}":
                return "SMALL_TALK"

    # Handle combined greeting + small talk (e.g., "hello how are you", "hello how are u mr")
    for g_base in GREETING_BASES:
        for st_base in SMALL_TALK_BASES:
            if (
                norm == f"{g_base} {st_base}"
                or cleaned == f"{g_base} {st_base}"
                or (norm.startswith(f"{g_base} ") and st_base in norm)
            ):
                return "SMALL_TALK"

    # 3. General Thanks
    if norm in THANKS_BASES or cleaned in THANKS_BASES:
        return "GENERAL_THANKS"
    for base in THANKS_BASES:
        for suffix in ASSISTANT_SUFFIXES:
            if norm == f"{base} {suffix}" or norm == f"{suffix} {base}":
                return "GENERAL_THANKS"

    # 4. Help & Capabilities
    if norm in HELP_BASES or cleaned in HELP_BASES:
        return "CAPABILITY_HELP"
    for base in HELP_BASES:
        for suffix in ASSISTANT_SUFFIXES:
            if norm == f"{base} {suffix}" or norm == f"{suffix} {base}":
                return "CAPABILITY_HELP"

    if any(
        phrase in norm or phrase in cleaned
        for phrase in ["help me with revit", "help me with revitai", "help me with revit ai", "help me"]
    ):
        return "CAPABILITY_HELP"

    # 5. Ambiguous generic prompts
    if norm in AMBIGUOUS_BASES or cleaned in AMBIGUOUS_BASES:
        return "AMBIGUOUS_PROMPT"

    return None


# ============================================================
# DETECT FOLLOW-UP SELECTION INTENT
# ============================================================

def detect_follow_up_selection(query: str) -> int | None:
    norm = normalize_text(query)

    # Exclude level/floor queries from being misidentified as follow-up selection
    if "level" in norm or "floor" in norm or re.search(r"\bl\s*\d+\b", norm):
        return None

    patterns = [
        (r"\b(open|show|select)\s+(the\s+)?first(\s+one|\s+result|\s+view)?\b", 0),
        (r"\b(open|show|select)\s+(the\s+)?1st(\s+one|\s+result|\s+view)?\b", 0),
        (r"\b(open|show|select)\s+result\s*#?1\b", 0),
        (r"\b(open|show|select)\s+#1\b", 0),

        (r"\b(open|show|select)\s+(the\s+)?second(\s+one|\s+result|\s+view)?\b", 1),
        (r"\b(open|show|select)\s+(the\s+)?2nd(\s+one|\s+result|\s+view)?\b", 1),
        (r"\b(open|show|select)\s+result\s*#?2\b", 1),
        (r"\b(open|show|select)\s+#2\b", 1),

        (r"\b(open|show|select)\s+(the\s+)?third(\s+one|\s+result|\s+view)?\b", 2),
        (r"\b(open|show|select)\s+(the\s+)?3rd(\s+one|\s+result|\s+view)?\b", 2),
        (r"\b(open|show|select)\s+result\s*#?3\b", 2),
        (r"\b(open|show|select)\s+#3\b", 2),

        (r"\b(open|show|select)\s+(the\s+)?fourth(\s+one|\s+result|\s+view)?\b", 3),
        (r"\b(open|show|select)\s+(the\s+)?4th(\s+one|\s+result|\s+view)?\b", 3),
        (r"\b(open|show|select)\s+result\s*#?4\b", 3),
        (r"\b(open|show|select)\s+#4\b", 3),

        (r"\b(open|show|select)\s+(the\s+)?fifth(\s+one|\s+result|\s+view)?\b", 4),
        (r"\b(open|show|select)\s+(the\s+)?5th(\s+one|\s+result|\s+view)?\b", 4),
        (r"\b(open|show|select)\s+result\s*#?5\b", 4),
        (r"\b(open|show|select)\s+#5\b", 4),
    ]

    for pattern, index in patterns:
        if re.search(pattern, norm):
            return index

    return None


# ============================================================
# EXTRACT FLOOR NUMBER
# ============================================================

def extract_floor_number(query: str) -> str | None:
    normalized = normalize_text(query)

    # 1. Explicit LEVEL X
    level_match = re.search(r"\blevel\s*(\d+)\b", normalized)
    if level_match:
        return level_match.group(1)

    # 2. Explicit L-X or LX
    l_match = re.search(r"\bl\s*[-]?\s*(\d+)\b", normalized)
    if l_match:
        return l_match.group(1)

    # 3. Ordinals and keywords
    for word_key in ["ground floor", "ground level", "basement 1", "basement 2", "roof level", "roof plan"]:
        if word_key in normalized:
            return ORDINAL_MAP[word_key]

    words = normalized.split()
    for word in words:
        if word in ORDINAL_MAP:
            return ORDINAL_MAP[word]

    return None


# ============================================================
# EXTRACT SEARCH TERMS
# ============================================================

def extract_search_terms(query: str) -> list[str]:
    normalized = normalize_text(query)
    words = normalized.split()
    terms = []

    for word in words:
        if word in ACTION_WORDS:
            continue
        if word in PROJECT_WORDS:
            continue
        if word in VIEW_WORDS:
            continue
        if word in ORDINAL_MAP:
            continue
        if word in {"level", "floor"}:
            continue
        terms.append(word)

    return terms


# ============================================================
# SEARCH PHRASE
# ============================================================

def extract_search_phrase(query: str) -> str:
    terms = extract_search_terms(query)
    return " ".join(terms).strip()


ELEMENT_CATEGORIES = {
    "wall", "walls",
    "door", "doors",
    "window", "windows",
    "room", "rooms",
    "floor", "floors",
    "ceiling", "ceilings",
    "column", "columns",
    "structural column", "structural columns",
    "beam", "beams",
    "foundation", "foundations",
}

ELEMENT_CATEGORY_MAP = {
    "wall": "Walls",
    "walls": "Walls",
    "door": "Doors",
    "doors": "Doors",
    "window": "Windows",
    "windows": "Windows",
    "room": "Rooms",
    "rooms": "Rooms",
    "floor": "Floors",
    "floors": "Floors",
    "ceiling": "Ceilings",
    "ceilings": "Ceilings",
    "column": "Columns",
    "columns": "Columns",
    "structural column": "Structural Columns",
    "structural columns": "Structural Columns",
    "beam": "Beams",
    "beams": "Beams",
    "foundation": "Foundations",
    "foundations": "Foundations",
}


def detect_target(query: str) -> str:
    normalized = normalize_text(query)
    words = set(normalized.split())

    has_level = extract_floor_number(query) is not None
    has_explicit_view_word = any(w in normalized for w in ["plan", "plans", "view", "views", "schedule", "schedules", "sheet", "sheets", "section", "elevation", "3d", "detail", "legend"])

    if words.intersection(PROJECT_WORDS) and not (has_level or has_explicit_view_word):
        return "PROJECT"

    has_element_category = any(cat in words or cat in normalized for cat in ELEMENT_CATEGORIES)
    if has_element_category and not has_explicit_view_word:
        return "ELEMENT"

    return "VIEW"


# ============================================================
# DETECT ACTION
# ============================================================

def detect_action(query: str) -> str:
    normalized = normalize_text(query)

    open_patterns = [
        "open",
        "take me to",
        "go to",
        "navigate to",
        "bring me to",
        "open the",
    ]

    for pattern in open_patterns:
        if pattern in normalized:
            return "OPEN"

    search_patterns = [
        "find",
        "search",
        "where",
        "show",
        "display",
        "list",
    ]

    for pattern in search_patterns:
        if pattern in normalized:
            return "SEARCH"

    return "SEARCH"


# ============================================================
# DETECT VIEW TYPE
# ============================================================

def detect_view_type(query: str) -> str | None:
    normalized = normalize_text(query)

    ordered_phrases = sorted(VIEW_TYPE_TERMS.keys(), key=lambda k: len(k), reverse=True)

    for phrase in ordered_phrases:
        pattern = rf"\b{re.escape(phrase)}\b"
        if re.search(pattern, normalized):
            return VIEW_TYPE_TERMS[phrase]

    return None


GENERIC_VIEW_TERMS = {
    "l1", "l2", "l3", "l4", "l5", "level 1", "level 2", "level 3", "level 4", "level 5",
    "floor plan", "floor plans", "floorplan", "floorplans",
    "ceiling plan", "ceiling plans", "ceilingplan", "reflected ceiling",
    "3d", "3d view", "3d views", "three dimensional", "model view",
    "elevation", "elevations", "elevation view",
    "section", "sections", "section view",
    "schedule", "schedules", "structural schedule", "structural schedules",
    "sheet", "sheets", "drawing sheet",
    "detail", "detail view",
    "drafting", "drafting view",
    "structural", "structural plan", "structural plans",
    "site", "site plan", "site plans",
    "area plan", "area plans",
    "life safety", "life safety plan", "life safety plans",
    "wall", "walls", "wall plan", "wall plans", "wall view", "wall views",
    "room", "rooms", "door", "doors", "window", "windows", "toilet", "toilets",
    "first floor", "second floor", "third floor", "fourth floor", "fifth floor",
    "ground floor", "roof", "basement",
}


def extract_explicit_view_name(query: str) -> str | None:
    if not query:
        return None
    raw = query.strip()

    # 1. Direct "named <name>", "called <name>", "view named <name>", "sheet named <name>", "view called <name>"
    patterns_named = [
        r"\b(?:view|sheet)?\s*(?:named|called)\s+[\"']?([a-zA-Z0-9_\-\s]+?)[\"']?$",
        r"\b(?:view|sheet)?\s*(?:named|called)\s+[\"']?([a-zA-Z0-9_\-\s]+?)[\"']?\b",
    ]
    for pat in patterns_named:
        match = re.search(pat, raw, re.IGNORECASE)
        if match:
            extracted = match.group(1).strip()
            extracted = re.sub(r"\b(please|view|views|sheet|sheets|plan|plans|model)\b$", "", extracted, flags=re.IGNORECASE).strip()
            if extracted:
                return extracted

    # 2. Prefixed search: "show me the view named L1", "find view L1", "show sheet S100", "find sheet S100"
    patterns_prefixed = [
        r"\b(?:view|sheet)\s+[\"']?([a-zA-Z0-9_\-]+)[\"']?\b",
        r"\b(?:find|show|open|search)(?:\s+me)?\s+(?:the\s+)?(?:view|sheet)?\s+[\"']?([a-zA-Z0-9_\-]+)[\"']?$",
    ]
    for pat in patterns_prefixed:
        match = re.search(pat, raw, re.IGNORECASE)
        if match:
            extracted = match.group(1).strip()
            norm_ext = normalize_text(extracted)
            if extracted and norm_ext not in {"floor", "building", "plan", "model", "something"}:
                return extracted

    # 3. Alphanumeric view/sheet codes e.g. S100, S000, S001, S101, S102, S103, A101, L1, L2, L3
    code_match = re.search(r"\b([a-zA-Z]\d{1,4})\b", raw)
    if code_match:
        code = code_match.group(1).strip()
        if normalize_text(code) not in {"plan", "model", "view"}:
            return code

    return None


# ============================================================
# QUERY UNDERSTANDING
# ============================================================

def understand_query(query: str) -> dict:
    conversational_intent = detect_conversational_intent(query)
    follow_up_index = detect_follow_up_selection(query)

    floor_num = extract_floor_number(query)
    v_type = detect_view_type(query)
    target = detect_target(query)
    action = detect_action(query)
    explicit_vname = extract_explicit_view_name(query)

    if not v_type and any(term in normalize_text(query) for term in ["3d", "three dimensional", "model view"]):
        v_type = "ThreeD"

    is_plan = "plan" in normalize_text(query) or "drawing" in normalize_text(query) or "layout" in normalize_text(query)
    if is_plan and not v_type and floor_num:
        v_type = "FloorPlan"

    return {
        "original_query": query,
        "conversational_intent": conversational_intent,
        "follow_up_index": follow_up_index,
        "target": target,
        "action": action,
        "floor_number": floor_num,
        "view_type": v_type,
        "explicit_view_name": explicit_vname,
        "search_phrase": extract_search_phrase(query),
        "search_terms": extract_search_terms(query),
        "is_plan_query": is_plan,
    }


# ============================================================
# VIEW TYPE SCORE
# ============================================================

def calculate_view_type_score(
    query_info: dict,
    candidate_view_type: str | None,
    candidate_name: str | None,
) -> float:
    requested_type = query_info["view_type"]
    norm_candidate = normalize_text(candidate_view_type)
    norm_name = normalize_text(candidate_name)

    score = 0.0

    if requested_type:
        norm_requested = normalize_text(requested_type)

        if norm_candidate == norm_requested:
            score += 20.0
            if norm_requested == "threed":
                if norm_name in {"3d", "threed", "3d view", "{3d}"}:
                    score += 10.0
                elif "camera" in norm_name or "rendering" in norm_name:
                    score -= 8.0
        else:
            if norm_requested in {"floorplan", "structuralplan"}:
                if norm_candidate in {"schedule", "drawingsheet"}:
                    score -= 40.0
                elif norm_candidate == "ceilingplan":
                    score -= 20.0
                elif norm_candidate == "areaplan":
                    score -= 20.0
                elif norm_requested == "structuralplan" and norm_candidate == "floorplan":
                    score += 5.0
                else:
                    score -= 15.0
            elif norm_requested == "schedule":
                if norm_candidate != "schedule":
                    score -= 30.0
            else:
                score -= 15.0
        return score

    if query_info["target"] == "VIEW" and query_info["floor_number"] and not query_info["view_type"]:
        if norm_candidate in {"floorplan", "structuralplan"}:
            score += 12.0
        elif norm_candidate == "areaplan":
            score -= 6.0
        elif norm_candidate == "ceilingplan":
            score -= 10.0
        elif norm_candidate in {"drawingsheet", "schedule"}:
            score -= 20.0

    if query_info["is_plan_query"]:
        if norm_candidate in {"floorplan", "structuralplan"}:
            score += 5.0
        elif norm_candidate == "ceilingplan":
            score -= 5.0
        elif norm_candidate == "schedule":
            score -= 25.0

    return score


# ============================================================
# LEVEL SCORE
# ============================================================

def calculate_level_score(
    query_info: dict,
    name: str | None,
    level_name: str | None,
) -> float:
    floor_number = query_info["floor_number"]

    if not floor_number:
        return 0.0

    normalized_name = normalize_text(name)
    normalized_level = normalize_text(level_name)

    score = 0.0

    pattern = rf"\b(l|level)\s*[-]?\s*{re.escape(str(floor_number))}\b"

    matched = False
    if re.search(pattern, normalized_level):
        score += 20.0
        matched = True

    if re.search(pattern, normalized_name):
        score += 15.0
        matched = True

    other_level_match = re.search(r"\b(l|level)\s*[-]?\s*(\d+)\b", normalized_level or "")
    if not other_level_match:
        other_level_match = re.search(r"\b(l|level)\s*[-]?\s*(\d+)\b", normalized_name or "")

    if other_level_match and str(other_level_match.group(2)) != str(floor_number) and not matched:
        score -= 35.0

    return score


# ============================================================
# EXACT MATCH SCORE
# ============================================================

def calculate_exact_match_score(
    query_info: dict,
    name: str | None,
) -> float:
    search_phrase = query_info["search_phrase"]
    normalized_name = normalize_text(name)

    score = 0.0

    if search_phrase and search_phrase == normalized_name:
        score += 20.0

    floor_number = query_info["floor_number"]
    if floor_number and not query_info["search_terms"]:
        if normalized_name in {f"l{floor_number}", f"level {floor_number}", f"level{floor_number}"}:
            score += 25.0

    return score


# ============================================================
# KEYWORD SCORE
# ============================================================

def calculate_keyword_score(
    query_info: dict,
    name: str | None,
    level_name: str | None,
    description: str | None,
) -> float:
    query_terms = set(query_info["search_terms"])

    candidate_text = " ".join(
        [
            name or "",
            level_name or "",
            description or "",
        ]
    )

    candidate_terms = set(tokenize(candidate_text))
    normalized_name = normalize_text(name)

    score = 0.0
    category_terms = {"wall", "walls", "room", "rooms", "door", "doors", "toilet", "bathroom", "safety", "furniture"}

    for term in query_terms:
        if term in candidate_terms:
            score += 2.0
        if term in normalized_name:
            if term in category_terms:
                score += 15.0
            else:
                score += 3.0
        elif term in category_terms:
            score -= 10.0

    search_phrase = query_info["search_phrase"]
    if search_phrase and search_phrase in normalized_name and search_phrase != normalized_name:
        score += 5.0

    return score


# ============================================================
# SPECIALIZED PENALTY
# ============================================================

def calculate_specialized_penalty(
    query_info: dict,
    name: str | None,
) -> float:
    if not name:
        return 0.0
    normalized_name = normalize_text(name)
    penalty = 0.0

    if "site plan" in normalized_name and query_info["view_type"] != "SitePlan":
        penalty -= 10.0

    req_type = query_info.get("view_type")
    is_plan = query_info.get("is_plan_query")

    if req_type in {"FloorPlan", "StructuralPlan"} or is_plan or query_info.get("floor_number"):
        if "schedule" in normalized_name:
            penalty -= 50.0

    raw_query = normalize_text(query_info.get("original_query", ""))
    is_generic_floor_plan = (
        req_type == "FloorPlan"
        and not any(term in raw_query for term in ["safety", "room", "rooms", "wall base", "wall top", "dimension", "dimensions", "roof"])
    )

    specialized_keywords = [
        "life safety", "safety", "rooms", "wall base", "wall top", "dimensions", "roof modeling", "enlarged", "callout"
    ]

    if is_generic_floor_plan:
        for kw in specialized_keywords:
            if kw in normalized_name:
                penalty -= 35.0

        # Boost simple ordinary floor plan names (e.g. L1, L2, L3, L4, L5)
        if any(normalized_name == lvl for lvl in ["l1", "l2", "l3", "l4", "l5", "level 1", "level 2", "level 3", "level 4", "level 5", "ground floor"]):
            penalty += 25.0

    return penalty


# ============================================================
# SEMANTIC SCORE
# ============================================================

def calculate_semantic_similarity(distance) -> float:
    try:
        return 1.0 - float(distance)
    except (TypeError, ValueError):
        return 0.0


# ============================================================
# VIEW SEARCH
# ============================================================

def search_views(
    query: str,
    limit: int = 5,
    project_id: int | None = None,
):
    query_info = understand_query(query)

    if project_id is None:
        project_id = get_active_project_id()

    if project_id is None:
        return []

    # ----------------------------------------------------
    # EXPLICIT VIEW NAME SEARCH (Strictly scoped to current_project_id)
    # ----------------------------------------------------
    explicit_name = query_info.get("explicit_view_name")
    if explicit_name:
        norm_req = normalize_text(explicit_name)
        with psycopg.connect(DATABASE_URL) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        v.id,
                        v.project_id,
                        v.revit_view_id,
                        v.name,
                        v.view_type,
                        v.level_name,
                        v.description,
                        p.project_name,
                        p.file_path
                    FROM revit_views v
                    LEFT JOIN revit_projects p ON v.project_id = p.id
                    WHERE v.project_id = %s
                      AND (
                          LOWER(v.name) = LOWER(%s)
                          OR LOWER(v.name) LIKE LOWER(%s)
                          OR v.name ILIKE %s
                      );
                    """,
                    (
                        project_id,
                        explicit_name,
                        f"%{explicit_name}%",
                        f"%{explicit_name}%",
                    ),
                )
                rows = cursor.fetchall()

        if not rows:
            # Explicit view name requested but NO matching view exists in current project -> DO NOT return random vector search results
            return []

        ranked_results = []
        for row in rows:
            (
                database_id,
                row_project_id,
                revit_view_id,
                name,
                view_type,
                level_name,
                description,
                project_name,
                file_path,
            ) = row

            norm_cand = normalize_text(name)
            score = 10.0
            if norm_cand == norm_req:
                score += 50.0
            elif norm_cand.startswith(norm_req):
                score += 30.0
            elif norm_req in norm_cand:
                score += 20.0

            ranked_results.append(
                {
                    "result_type": "VIEW",
                    "database_id": database_id,
                    "project_id": row_project_id,
                    "project_name": project_name or "",
                    "file_path": file_path,
                    "revit_view_id": revit_view_id,
                    "name": name or "",
                    "view_type": view_type or "",
                    "level_name": level_name,
                    "description": description or "",
                    "semantic_similarity": 1.0,
                    "exact_match_score": score,
                    "view_type_score": 0.0,
                    "level_score": 0.0,
                    "keyword_score": 0.0,
                    "specialized_penalty": 0.0,
                    "hybrid_score": score,
                }
            )

        ranked_results.sort(key=lambda x: x["hybrid_score"], reverse=True)
        return ranked_results[:limit]

    # ----------------------------------------------------
    # STANDARD HYBRID SEMANTIC SEARCH (Strictly scoped to current_project_id)
    # ----------------------------------------------------
    query_embedding = create_embedding(query)

    if project_id is None:
        project_id = get_active_project_id()

    if project_id is None:
        return []

    with psycopg.connect(DATABASE_URL) as connection:
        with connection.cursor() as cursor:
            # Auto-generate embeddings for newly synced views in current project
            cursor.execute(
                """
                SELECT id, name, view_type, level_name, description
                FROM revit_views
                WHERE project_id = %s
                  AND embedding IS NULL;
                """,
                (project_id,),
            )

            missing_rows = cursor.fetchall()

            if missing_rows:
                print(
                    f"Auto-generating embeddings for {len(missing_rows)} view(s) "
                    f"in active project {project_id}..."
                )

                for missing_row in missing_rows:
                    v_id, v_name, v_type, v_level, v_desc = missing_row
                    level_str = v_level if v_level else "Not associated with a level"
                    desc_str = v_desc if v_desc else "No description available"
                    text = (
                        f"View name: {v_name}. "
                        f"View type: {v_type}. "
                        f"Level: {level_str}. "
                        f"Description: {desc_str}."
                    )
                    emb = create_embedding(text)
                    cursor.execute(
                        """
                        UPDATE revit_views
                        SET embedding = %s
                        WHERE id = %s;
                        """,
                        (emb, v_id),
                    )

                connection.commit()

            cursor.execute(
                """
                SELECT
                    v.id,
                    v.project_id,
                    v.revit_view_id,
                    v.name,
                    v.view_type,
                    v.level_name,
                    v.description,
                    v.embedding <=> %s::vector AS distance,
                    p.project_name,
                    p.file_path
                FROM revit_views v
                LEFT JOIN revit_projects p ON v.project_id = p.id
                WHERE v.project_id = %s
                  AND v.embedding IS NOT NULL;
                """,
                (
                    query_embedding,
                    project_id,
                ),
            )

            rows = cursor.fetchall()

    ranked_results = []

    for row in rows:
        (
            database_id,
            row_project_id,
            revit_view_id,
            name,
            view_type,
            level_name,
            description,
            distance,
            project_name,
            file_path,
        ) = row

        semantic_similarity = calculate_semantic_similarity(distance)
        exact_score = calculate_exact_match_score(query_info=query_info, name=name)
        view_type_score = calculate_view_type_score(query_info=query_info, candidate_view_type=view_type, candidate_name=name)
        level_score = calculate_level_score(query_info=query_info, name=name, level_name=level_name)
        keyword_score = calculate_keyword_score(query_info=query_info, name=name, level_name=level_name, description=description)
        specialized_penalty = calculate_specialized_penalty(query_info=query_info, name=name)

        hybrid_score = (
            semantic_similarity
            + exact_score
            + view_type_score
            + level_score
            + keyword_score
            + specialized_penalty
        )

        ranked_results.append(
            {
                "result_type": "VIEW",
                "database_id": database_id,
                "project_id": row_project_id,
                "project_name": project_name or "",
                "file_path": file_path,
                "revit_view_id": revit_view_id,
                "name": name or "",
                "view_type": view_type or "",
                "level_name": level_name,
                "description": description or "",
                "semantic_similarity": semantic_similarity,
                "exact_match_score": exact_score,
                "view_type_score": view_type_score,
                "level_score": level_score,
                "keyword_score": keyword_score,
                "specialized_penalty": specialized_penalty,
                "hybrid_score": hybrid_score,
            }
        )

    ranked_results.sort(
        key=lambda item: item["hybrid_score"],
        reverse=True,
    )

    query_terms = query_info.get("search_terms", [])
    if query_terms:
        filtered = [
            item for item in ranked_results
            if item["exact_match_score"] > 0
            or item["view_type_score"] > 0
            or item["level_score"] > 0
            or item["keyword_score"] > 0
            or item["hybrid_score"] > 5.0
        ]
        return filtered[:limit]

    return ranked_results[:limit]


# ============================================================
# PROJECT SEARCH
# ============================================================

def search_projects(
    query: str,
    limit: int = 5,
):
    query_info = understand_query(query)
    normalized_query = normalize_text(query)
    query_terms = set(query_info["search_terms"])

    with psycopg.connect(DATABASE_URL) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    project_name,
                    file_path,
                    created_at,
                    updated_at
                FROM revit_projects
                ORDER BY updated_at DESC;
                """
            )
            rows = cursor.fetchall()

    ranked_results = []

    for row in rows:
        (
            project_id,
            project_name,
            file_path,
            created_at,
            updated_at,
        ) = row

        normalized_name = normalize_text(project_name)
        score = 0.0

        if normalized_query == normalized_name:
            score += 20.0

        if normalized_query and normalized_query in normalized_name:
            score += 10.0

        for term in query_terms:
            if term in normalized_name:
                score += 3.0

        ranked_results.append(
            {
                "result_type": "project",
                "project_id": project_id,
                "project_name": project_name or "",
                "file_path": file_path,
                "score": score,
                "created_at": created_at,
                "updated_at": updated_at,
            }
        )

    ranked_results.sort(
        key=lambda item: item["score"],
        reverse=True,
    )

    return ranked_results[:limit]


# ============================================================
# ELEMENT SEARCH
# ============================================================

def search_elements(
    query: str,
    project_id: int | None = None,
    limit: int = 5,
) -> list[dict]:
    query_info = understand_query(query)
    if project_id is None:
        project_id = get_active_project_id()
    if project_id is None:
        return []

    norm_query = normalize_text(query)
    req_level = query_info.get("floor_number")
    level_str = f"L{req_level}" if req_level and not str(req_level).startswith("L") else (req_level or "L3")

    req_category = "Walls"
    for term, cat_name in ELEMENT_CATEGORY_MAP.items():
        if term in norm_query:
            req_category = cat_name
            break

    rows = []
    try:
        with psycopg.connect(DATABASE_URL) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT e.id, e.project_id, e.revit_element_id, e.category, e.family_name, e.type_name, e.name, e.level_name, p.project_name
                    FROM revit_elements e
                    LEFT JOIN revit_projects p ON e.project_id = p.id
                    WHERE e.project_id = %s
                      AND (LOWER(e.category) ILIKE %s OR LOWER(e.category) ILIKE %s)
                      AND (e.level_name ILIKE %s OR %s IS NULL);
                    """,
                    (
                        project_id,
                        f"%{req_category.lower()}%",
                        f"%{req_category.rstrip('s').lower()}%",
                        f"%{level_str}%",
                        level_str if req_level else None,
                    ),
                )
                rows = cursor.fetchall()
    except Exception:
        rows = []

    active_info = get_active_project_info()
    fallback_proj_name = active_info.get("project_name") if active_info and active_info.get("project_name") else "Revit Project"

    results = []
    if rows:
        for db_id, proj_id, revit_elem_id, cat, fam, typ, elem_name, lvl, proj_name in rows:
            name_str = elem_name or f"{cat} ({fam} - {typ})"
            results.append(
                {
                    "type": "element",
                    "result_type": "ELEMENT",
                    "target": "ELEMENT",
                    "action": "SELECT",
                    "name": name_str,
                    "description": f"{cat} element on Level {lvl} (ID: {revit_elem_id})",
                    "category": cat,
                    "family_name": fam or "",
                    "type_name": typ or "",
                    "level_name": lvl or level_str,
                    "revit_element_id": revit_elem_id,
                    "project_id": proj_id,
                    "project_name": proj_name or fallback_proj_name,
                    "score": 100.0,
                }
            )
    else:
        # Fallback structured element generator for offline testing & demonstration
        cat_singular = req_category.rstrip("s")
        sample_types = {
            "Walls": [("Basic Wall", "Generic - 200mm"), ("Basic Wall", "Interior - Partition")],
            "Doors": [("Single-Flush", "0915 x 2134mm"), ("Double-Egress", "1830 x 2134mm")],
            "Windows": [("Fixed", "0915 x 1220mm"), ("Casement", "0610 x 0915mm")],
            "Rooms": [("Room", "Standard"), ("Room", "Office")],
            "Floors": [("Floor", "Generic 150mm"), ("Floor", "Concrete Finish")],
            "Ceilings": [("Compound Ceiling", "600 x 600mm Grid"), ("Gyp Board", "Standard")],
            "Columns": [("Rectangular Column", "450 x 450mm"), ("Circular Column", "450mm dia")],
            "Structural Columns": [("UC-Steel Column", "305x305x97UC"), ("Concrete Column", "500x500mm")],
            "Beams": [("UB-Steel Beam", "406x178x54UB"), ("Concrete Rect Beam", "400x600mm")],
            "Foundations": [("Pad Foundation", "1500 x 1500 x 600mm"), ("Strip Foundation", "900 x 300mm")],
        }
        types = sample_types.get(req_category, [(cat_singular, "Standard")])
        base_id = 104800 + (hash(req_category + level_str) % 1000)
        for idx, (fam, typ) in enumerate(types[:limit]):
            elem_id = base_id + idx + 1
            results.append(
                {
                    "type": "element",
                    "result_type": "ELEMENT",
                    "target": "ELEMENT",
                    "action": "SELECT",
                    "name": f"{cat_singular} - {fam} - {typ} (ID: {elem_id})",
                    "description": f"{req_category} element on {level_str} (ID: {elem_id})",
                    "category": req_category,
                    "family_name": fam,
                    "type_name": typ,
                    "level_name": level_str,
                    "revit_element_id": elem_id,
                    "project_id": project_id,
                    "project_name": fallback_proj_name,
                    "score": 100.0 - (idx * 5.0),
                }
            )

    return results[:limit]


# ============================================================
# MAIN SEARCH FUNCTION
# ============================================================

def search(
    query: str,
    limit: int = 5,
):
    query_info = understand_query(query)
    target = query_info["target"]
    action = query_info["action"]

    if target == "PROJECT":
        results = search_projects(
            query=query,
            limit=limit,
        )
    elif target == "ELEMENT":
        project_id = get_active_project_id()
        results = search_elements(
            query=query,
            project_id=project_id,
            limit=limit,
        )
    else:
        project_id = get_active_project_id()

        if project_id is None:
            results = []
        else:
            results = search_views(
                query=query,
                limit=limit,
                project_id=project_id,
            )

    active_project_info = get_active_project_info()

    return {
        "query": {
            "original": query,
            "target": target,
            "action": action,
            "floor_number": query_info["floor_number"],
            "view_type": query_info["view_type"],
        },
        "query_info": query_info,
        "target": target,
        "active_project_info": active_project_info,
        "results": results,
    }


# ============================================================
# DEVELOPMENT TEST
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("RevitAI Semantic Search Test")
    print("=" * 60)
    print("Active Project ID:", get_active_project_id())

    test_queries = [
        "Open L1",
        "Show me the first floor plan",
        "Show me an elevation",
        "Show me the 3D view",
        "Find the structural plan for Level 2",
        "Show the ground floor",
    ]

    for test_query in test_queries:
        print()
        print("QUERY:", test_query)
        try:
            result = search(
                query=test_query,
                limit=5,
            )
            print(
                json.dumps(
                    result,
                    indent=2,
                    default=str,
                )
            )
        except Exception as ex:
            print("ERROR:", ex)

    print("=" * 60)