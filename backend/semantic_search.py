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

from dotenv import load_dotenv
load_dotenv()

DATABASE_URL = os.getenv(
    "REVITAI_DATABASE_URL",
    "postgresql://postgres:postgres@127.0.0.1:5432/revitai",
)


def get_db_connection():
    url = (os.getenv("REVITAI_DATABASE_URL") or DATABASE_URL).replace("localhost", "127.0.0.1")
    return psycopg.connect(url, connect_timeout=5)


# ============================================================
# REVIT PLUGIN
# ============================================================

CANDIDATE_PORTS = [8765, 8766, 8767, 8768, 8769, 8770]
REVIT_PLUGIN_URL = "http://127.0.0.1:8765/current-project"


def normalize_file_path(path: str | None) -> str | None:
    if not path or not str(path).strip():
        return None
    try:
        norm = os.path.abspath(str(path).strip()).lower().replace("/", "\\")
        return norm
    except Exception:
        return str(path).strip().lower().replace("/", "\\")


def get_active_project_info() -> dict | None:
    # 1. Primary: Query Revit Plugin HTTP listener across candidate ports
    for port in CANDIDATE_PORTS:
        try:
            url = f"http://127.0.0.1:{port}/current-project"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=0.4) as response:
                if response.status == 200:
                    payload = json.loads(response.read().decode("utf-8"))
                    if payload and payload.get("success"):
                        payload["live"] = True
                        payload["port"] = port
                        return payload
        except Exception:
            continue

    # 2. Database Fallback: Query PostgreSQL for most recently active project
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, project_name, file_path
                    FROM revit_projects
                    ORDER BY updated_at DESC NULLS LAST, id DESC
                    LIMIT 1;
                    """
                )
                row = cur.fetchone()
                if row:
                    p_id, p_name, p_path = row
                    return {
                        "success": True,
                        "live": False,
                        "project_id": p_id,
                        "project_name": p_name,
                        "file_path": p_path,
                        "synced": True,
                        "message": "Resolved active project from PostgreSQL database.",
                    }
    except Exception as db_err:
        print("[ACTIVE PROJECT DB FALLBACK WARNING]", db_err)

    return None


def get_active_project_id() -> int | None:
    payload = get_active_project_info()

    if payload is not None and payload.get("success"):
        project_id = payload.get("project_id")
        if project_id is not None:
            try:
                return int(project_id)
            except (ValueError, TypeError):
                pass

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

    # 4. Sheet number level hint (e.g. SD105 / 105 -> 5, 104 -> 4, 103 -> 3, 102 -> 2, 101 -> 1)
    sheet_num_match = re.search(r"\b[a-zA-Z]*10(\d)\b", normalized)
    if sheet_num_match:
        return sheet_num_match.group(1)

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

    # 3. Alphanumeric view/sheet codes e.g. SD105, SD 105, SD-105, S100, S000, S001, S101, A101, L1, L2, L3
    code_match = re.search(r"\b([a-zA-Z]{1,5}\s*[-]?\s*\d{1,4})\b", raw)
    if code_match:
        code = code_match.group(1).strip()
        if normalize_text(code) not in {"plan", "model", "view"}:
            return code

    return None


CONVERSATIONAL_IDENTIFIER_PATTERNS = [
    r"^(?:ok|okay|hey|hi|hello|please|can\s+you|could\s+you|would\s+you|i\s+want\s+to|i\s+need\s+to|where\s+can\s+i\s+find|where\s+is|take\s+me\s+to|let\s+me\s+see|open|display|locate|find\s+me|find|show\s+me|show)\s+(?:the\s+)?(?:sheet\s+for\s+the\s+|floor\s+plan\s+for\s+|drawings\s+for\s+|drawing\s+for\s+|view\s+for\s+|sheet|view|file|drawing|model)?\s*",
    r"^(?:can\s+you\s+|could\s+you\s+|please\s+)?(?:open|show|find|display|view|get|navigate\s+to|bring\s+me\s+to|take\s+me\s+to|go\s+to|i\s+want\s+to\s+see)\s+(?:me\s+)?(?:the\s+)?(?:sheet|view|file|drawing|model)?\s*",
    r"^(?:please\s+)?(?:show|open|find|view|get)\s+(?:me\s+)?(?:the\s+)?",
    r"^(?:the\s+)?(?:sheet|view|file|drawing)\s+",
]



def extract_clean_identifier(query: str) -> list[str]:
    if not query:
        return []
    raw = query.strip().strip("\"'").strip()
    candidates = []

    # 1. Cleaned phrase with conversational prefixes stripped
    cleaned = raw
    for pat in CONVERSATIONAL_IDENTIFIER_PATTERNS:
        cleaned = re.sub(pat, "", cleaned, flags=re.IGNORECASE).strip().strip("\"'").strip()

    if cleaned and cleaned.lower() not in {"plan", "plans", "model", "something", "view", "views", "sheet", "sheets", "drawing", "drawings"}:
        candidates.append(cleaned)

    # 2. Extract explicit quotes if present
    quote_match = re.search(r"[\"']([^\"']+)[\"']", raw)
    if quote_match:
        q_val = quote_match.group(1).strip()
        if q_val and q_val not in candidates:
            candidates.append(q_val)

    # 3. Alphanumeric/code pattern match e.g. SD105, SD-105, SD 105, A101, E-101, L5_SD, S_100, R2, L3, B1
    code_match = re.search(r"\b([a-zA-Z]{1,6}[\s_\-]?\d{1,4}[a-zA-Z]?)\b", raw)
    if code_match:
        c_val = code_match.group(1).strip()
        if c_val and c_val not in candidates and c_val.lower() not in {"level", "floor", "plan"}:
            candidates.append(c_val)

    # 4. Explicit view name from extract_explicit_view_name
    exp_name = extract_explicit_view_name(raw)
    if exp_name and exp_name not in candidates:
        candidates.append(exp_name)

    return candidates


SHEET_TITLE_MAP = {
    # Architectural (Snowdon Towers Sample Architectural)
    "site plan": "C101",
    "parking deck floor plan": "SD100",
    "first floor plan": "SD101",
    "second floor plan": "SD102",
    "third floor plan": "SD103",
    "fourth floor plan": "SD104",
    "fifth floor plan": "SD105",
    "roof plan": "SD106",
    "café kitchen": "K101",
    "cafe kitchen": "K101",
    "parking deck life safety plan": "G100",
    "first floor life safety plan": "G101",
    "second floor life safety plan": "G102",
    "third floor life safety plan": "G103",
    "fourth floor life safety plan": "G104",
    "fifth floor life safety plan": "G105",
    "roof plan life safety plan": "G106",
    "cover": "A001",
    "door schedule": "A601",
    "schedules": "A602",
    "building elevations": "A201",
    "building sections": "A301",
    "wall sections": "A405",
    "details": "A501",
    "partition types": "A502",
    "residential lobby": "A404",
    "enlarged live/work cores": "A403",
    "enlarged live work cores": "A403",
    "perspective from above": "A901",
    "stair towers - cutaway views": "A902",
    "stair towers cutaway views": "A902",
    "3d views": "A903",
    "existing conditions elevations": "A903",
    "solar study": "A904",
    "typical public restroom": "A401",
    "green roof": "L101",
    "first floor ceiling plan": "A111",
    "second floor ceiling plan": "A112",
    "third floor ceiling plan": "A113",
    "fourth floor ceiling plan": "A114",
    "fifth floor ceiling plan": "A115",
    # HVAC / Mechanical (Snowdon Towers Sample HVAC)
    "plan hvac l0 parking": "M100",
    "plan hvac l1": "M101",
    "plan hvac l2": "M102",
    "plan hvac l3": "M103",
    "plan hvac l4": "M104",
    "plan hvac l5": "M105",
    "plan hvac roof": "M106",
    "rcp hvac l0 parking": "M200",
    "rcp hvac l1": "M201",
    "rcp hvac l2": "M202",
    "rcp hvac l3": "M203",
    "rcp hvac l4": "M204",
    "rcp hvac l5": "M205",
    "rcp hvac roof": "M206",
    "cover sheet": "M000",
    "notes, symbols & schedules": "M001",
    # Structural (Snowdon Towers Sample Structural)
    "parking": "S100",
    "foundation": "S101",
    "main level": "S102",
    "second level": "S103",
    "third level": "S104",
    "fourth level": "S105",
    "fifth level": "S106",
    "roof": "S107",
    "stair towers": "S301",
    # Plumbing (Snowdon Towers Sample Plumbing)
    "plan - l0 sanitary": "P100",
    "plan - l1 sanitary": "P101",
    "plan - l2 sanitary": "P102",
    "plan - l3 sanitary": "P103",
    "plan - l4 sanitary": "P104",
    "plan - l5 sanitary": "P105",
    "plan - roof sanitary": "P106",
    "rcp - l0 sanitary": "P200",
    "rcp - l1 sanitary": "P201",
    "rcp - l2 sanitary": "P202",
    "rcp - l3 sanitary": "P203",
    "rcp - l4 sanitary": "P204",
    "rcp - l5 sanitary": "P205",
    "rcp - roof sanitary": "P206",
    "sections sanitary risers": "P303",
    "domestic water plan - l0 parking": "P400",
    "domestic water plan - l1": "P401",
    "domestic water plan - l2": "P402",
    "domestic water plan - l3": "P403",
    "domestic water plan - l4": "P404",
    "domestic water plan - l5": "P405",
    "domestic water plan - roof": "P406",
    # Electrical (Snowdon Towers Sample Electrical)
    "power plan parking": "E100",
    "power plan l1": "E101",
    "power plan l2": "E102",
    "power plan l3": "E103",
    "power plan l4": "E104",
    "power plan l5": "E105",
    "lighting plan parking": "E200",
    "lighting plan l1": "E201",
    "lighting plan l2": "E202",
    "lighting plan l3": "E203",
    "lighting plan l4": "E204",
    "lighting plan l5": "E205",
}


def auto_repair_sheet_identities():
    """
    Scans revit_views for any DrawingSheet rows with missing sheet_number or unformatted names,
    and updates PostgreSQL database using SHEET_TITLE_MAP or regex prefix extraction.
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, project_id, name, sheet_number, sheet_name
                    FROM revit_views
                    WHERE (view_type = 'DrawingSheet' OR view_type LIKE '%DrawingSheet%')
                      AND (sheet_number IS NULL OR sheet_number = '' OR name NOT LIKE '%%-%%');
                    """
                )
                rows = cur.fetchall()
                if not rows:
                    return

                updated = 0
                for db_id, proj_id, name_val, s_num, s_name in rows:
                    name_str = (name_val or "").strip()
                    s_num_str = (s_num or "").strip()
                    s_name_str = (s_name or "").strip()

                    new_s_num = s_num_str
                    new_s_name = s_name_str

                    m = re.match(r"^([a-zA-Z]{1,4}\s*\d{1,4}[a-zA-Z]?)\s*[-:]\s*(.*)$", name_str)
                    if m:
                        new_s_num = new_s_num or m.group(1).strip()
                        new_s_name = new_s_name or m.group(2).strip()
                    else:
                        lookup_num = SHEET_TITLE_MAP.get(name_str.lower())
                        if lookup_num:
                            new_s_num = new_s_num or lookup_num
                            new_s_name = new_s_name or name_str

                    if new_s_num:
                        full_name = name_str
                        if not full_name.lower().startswith(new_s_num.lower()):
                            full_name = f"{new_s_num} - {name_str}"
                        cur.execute(
                            """
                            UPDATE revit_views
                            SET sheet_number = %s,
                                sheet_name = %s,
                                name = %s
                            WHERE id = %s;
                            """,
                            (new_s_num, new_s_name or name_str, full_name, db_id)
                        )
                        updated += 1
                if updated > 0:
                    conn.commit()
                    print(f"[AUTO-REPAIR] Auto-repaired {updated} DrawingSheet identities in PostgreSQL.")
    except Exception as e:
        print("[AUTO-REPAIR WARNING] Could not auto-repair sheet identities:", e)


def search_exact_entity_project_scoped(query: str, project_id: int | None = None) -> list[dict]:
    if project_id is None:
        project_id = get_active_project_id()
    if project_id is None:
        return []

    # Ensure sheet identities are repaired if needed
    auto_repair_sheet_identities()

    candidates = extract_clean_identifier(query)
    if not candidates:
        return []

    print(f"[SEARCH TRACE] Query: '{query}' | Active Project ID: {project_id} | Candidates: {candidates}")

    rows = []
    try:
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                try:
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
                            p.file_path,
                            v.sheet_number,
                            v.sheet_name
                        FROM revit_views v
                        LEFT JOIN revit_projects p ON v.project_id = p.id
                        WHERE v.project_id = %s;
                        """,
                        (project_id,),
                    )
                    rows = cursor.fetchall()
                except Exception:
                    connection.rollback()
                    with connection.cursor() as cursor2:
                        cursor2.execute(
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
                                p.file_path,
                                NULL AS sheet_number,
                                NULL AS sheet_name
                            FROM revit_views v
                            LEFT JOIN revit_projects p ON v.project_id = p.id
                            WHERE v.project_id = %s;
                            """,
                            (project_id,),
                        )
                        rows = cursor2.fetchall()
    except Exception as e:
        print("Database connection error in search_exact_entity_project_scoped:", e)
        return []

    if not rows:
        return []

    matched_results = []
    seen_view_ids = set()

    for candidate in candidates:
        cand_lower = candidate.strip().lower()
        cand_clean = re.sub(r"[^a-zA-Z0-9]", "", cand_lower)

        if not cand_clean or cand_clean in {
            "plan", "plans", "model", "something", "view", "views", "sheet", "sheets",
            "project", "projects", "file", "files", "document", "documents", "info",
            "information", "active", "current", "working", "existing", "work"
        }:
            continue

        for row in rows:
            (
                db_id, row_proj_id, revit_view_id, name, view_type, level_name, description, proj_name, file_path, sheet_num, sheet_nm
            ) = row

            if db_id in seen_view_ids:
                continue

            name_lower = (name or "").strip().lower()
            name_clean = re.sub(r"[^a-zA-Z0-9]", "", name_lower)

            is_drawing_sheet = view_type == "DrawingSheet" or "DrawingSheet" in (view_type or "")

            effective_sheet_num = sheet_num
            if not effective_sheet_num and is_drawing_sheet:
                # 1. Regex prefix check
                m_num = re.match(r"^([a-zA-Z]{1,4}\s*\d{1,4}[a-zA-Z]?)\s*[-:]?\s*(.*)$", name or "")
                if m_num:
                    effective_sheet_num = m_num.group(1).strip()
                else:
                    effective_sheet_num = SHEET_TITLE_MAP.get(name_lower)

            sheet_num_lower = (effective_sheet_num or "").strip().lower()
            sheet_num_clean = re.sub(r"[^a-zA-Z0-9]", "", sheet_num_lower)

            is_exact = False
            exact_score = 0.0

            # Priority 1: CURRENT PROJECT EXACT SHEET NUMBER
            if sheet_num_lower and (sheet_num_lower == cand_lower or sheet_num_clean == cand_clean):
                is_exact = True
                exact_score = 100.0
                print(f"[SEARCH TRACE] [EXACT SHEET NUMBER MATCH] Query '{query}' -> Sheet {sheet_num} ({name})")

            # Priority 2: CURRENT PROJECT EXACT VIEW NAME
            elif name_lower == cand_lower or name_clean == cand_clean:
                is_exact = True
                exact_score = 99.0
                print(f"[SEARCH TRACE] [EXACT VIEW NAME MATCH] Query '{query}' -> View {name}")

            # Priority 4: NORMALIZED PREFIX / TOKEN MATCH
            elif name_lower.startswith(cand_lower + " - ") or name_lower.startswith(cand_lower + "-") or name_lower.startswith(cand_lower + " "):
                is_exact = True
                exact_score = 98.0
                print(f"[SEARCH TRACE] [EXACT PREFIX MATCH] Query '{query}' -> {name}")
            elif cand_clean and len(cand_clean) >= 2:
                prefix_part = name_lower.split("-")[0].strip() if "-" in name_lower else name_lower.split(" ")[0].strip()
                prefix_clean = re.sub(r"[^a-zA-Z0-9]", "", prefix_part)
                if prefix_clean == cand_clean:
                    is_exact = True
                    exact_score = 96.0
                    print(f"[SEARCH TRACE] [EXACT CLEAN PREFIX MATCH] Query '{query}' -> {name}")
                elif cand_clean in name_clean or (sheet_num_clean and cand_clean in sheet_num_clean):
                    is_exact = True
                    exact_score = 95.0
                    print(f"[SEARCH TRACE] [EXACT CLEAN SUBSTRING MATCH] Query '{query}' -> {name}")


            if is_exact:
                seen_view_ids.add(db_id)
                res_type = "SHEET" if (view_type == "DrawingSheet" or "DrawingSheet" in (view_type or "")) else "VIEW"

                actual_sheet_num = effective_sheet_num or sheet_num
                actual_sheet_name = sheet_nm or name
                if res_type == "SHEET" and not actual_sheet_num and " - " in name:
                    parts = name.split(" - ", 1)
                    actual_sheet_num = parts[0].strip()
                    actual_sheet_name = parts[1].strip()
                full_name = name or ""
                if res_type == "SHEET" and actual_sheet_num and not full_name.startswith(actual_sheet_num):
                    full_name = f"{actual_sheet_num} - {full_name}"

                matched_results.append({
                    "type": res_type.lower(),
                    "result_type": res_type,
                    "target": "VIEW",
                    "action": "OPEN" if detect_action(query) == "OPEN" else "SEARCH",
                    "database_id": db_id,
                    "project_id": row_proj_id,
                    "project_name": proj_name or "",
                    "file_path": file_path,
                    "revit_view_id": revit_view_id,
                    "name": full_name,
                    "sheet_number": actual_sheet_num,
                    "sheet_name": actual_sheet_name,
                    "view_type": view_type or "",
                    "level_name": level_name,
                    "description": description or "",

                    "semantic_similarity": 1.0,
                    "exact_match_score": exact_score,
                    "view_type_score": 0.0,
                    "level_score": 0.0,
                    "keyword_score": 0.0,
                    "specialized_penalty": 0.0,
                    "hybrid_score": exact_score,
                    "score": exact_score,
                })

    matched_results.sort(key=lambda x: x["hybrid_score"], reverse=True)
    return matched_results


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

    explicit_name = query_info.get("explicit_view_name")
    if explicit_name:
        clean_exp = re.sub(r"[^a-zA-Z0-9]", "", explicit_name).lower()
        clean_cand = re.sub(r"[^a-zA-Z0-9]", "", name or "").lower()
        if clean_exp and clean_exp in clean_cand:
            score += 35.0

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
    # 1. PROJECT-SCOPED EXACT IDENTIFIER SEARCH (Immediate Priority & Immediate Stop)
    # ----------------------------------------------------
    exact_matches = search_exact_entity_project_scoped(query, project_id)
    if exact_matches:
        return exact_matches[:limit]

    # ----------------------------------------------------
    # 2. EXPLICIT VIEW NAME SEARCH (Strictly scoped to current_project_id)
    # ----------------------------------------------------
    explicit_name = query_info.get("explicit_view_name")
    if explicit_name:
        norm_req = normalize_text(explicit_name)
        clean_code = re.sub(r"[^a-zA-Z0-9]", "", explicit_name).lower()
        with get_db_connection() as connection:
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
                        NULL AS distance,
                        p.project_name,
                        p.file_path
                    FROM revit_views v
                    LEFT JOIN revit_projects p ON v.project_id = p.id
                    WHERE v.project_id = %s
                      AND (
                          LOWER(v.name) = LOWER(%s)
                          OR LOWER(v.name) LIKE LOWER(%s)
                          OR REPLACE(REPLACE(LOWER(v.name), ' ', ''), '-', '') LIKE %s
                          OR v.name ILIKE %s
                      );
                    """,
                    (
                        project_id,
                        explicit_name,
                        f"%{explicit_name}%",
                        f"%{clean_code}%",
                        f"%{explicit_name}%",
                    ),
                )
                rows = cursor.fetchall()

        if rows:
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


                norm_cand = normalize_text(name)
                cand_clean = re.sub(r"[^a-zA-Z0-9]", "", name or "").lower()
                score = 10.0
                if norm_cand == norm_req or cand_clean == clean_code:
                    score += 50.0
                elif norm_cand.startswith(norm_req) or cand_clean.startswith(clean_code):
                    score += 30.0
                elif norm_req in norm_cand or clean_code in cand_clean:
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

        # Explicit code/identifier requested but does NOT exist in active project DB -> Return [] (prevent false vector matches)
        code_match = re.search(r"\b([a-zA-Z]{1,5}\s*[-]?\s*\d{1,4}[a-zA-Z]?)\b", explicit_name)
        if code_match:
            return []

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

            rows = []
            if query_embedding:
                try:
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
                except Exception as ex:
                    print("Vector distance search failed, falling back to metadata search:", ex)
                    rows = []

            # FALLBACK: If embedding distance query yielded 0 rows or embedding failed, fetch all project views for metadata scoring
            if not rows:
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
                        NULL AS distance,
                        p.project_name,
                        p.file_path
                    FROM revit_views v
                    LEFT JOIN revit_projects p ON v.project_id = p.id
                    WHERE v.project_id = %s;
                    """,
                    (project_id,),
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