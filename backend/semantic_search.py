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


# Optional development fallback.
#
# If the Revit plugin cannot be reached, this value can be used.
#
# Example:
#
# $env:REVITAI_PROJECT_ID="1"
#
DEVELOPMENT_PROJECT_ID = os.getenv(
    "REVITAI_PROJECT_ID"
)

if DEVELOPMENT_PROJECT_ID:
    try:
        DEVELOPMENT_PROJECT_ID = int(
            DEVELOPMENT_PROJECT_ID
        )
    except ValueError:
        DEVELOPMENT_PROJECT_ID = None


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


def normalize_file_path(path: str | None) -> str | None:
    if not path or not str(path).strip():
        return None
    try:
        norm = os.path.abspath(str(path).strip()).lower().replace("/", "\\")
        return norm
    except Exception:
        return str(path).strip().lower().replace("/", "\\")


def get_active_project_id() -> int | None:

    payload = get_active_project_info()

    if payload is not None:

        if payload.get("success"):

            project_id = payload.get(
                "project_id"
            )

            if project_id is not None:

                try:
                    return int(project_id)
                except (ValueError, TypeError):
                    return None

            else:

                return None

        else:

            return None

    return DEVELOPMENT_PROJECT_ID


# ============================================================
# ORDINAL MAP
# ============================================================

ORDINAL_MAP = {

    "first": "1",
    "second": "2",
    "third": "3",
    "fourth": "4",
    "fifth": "5",
    "sixth": "6",
    "seventh": "7",
    "eighth": "8",
    "ninth": "9",
    "tenth": "10",

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

}


# ============================================================
# VIEW TYPE TERMS
# ============================================================

VIEW_TYPE_TERMS = {

    "floorplan": "FloorPlan",
    "floor plan": "FloorPlan",

    "ceilingplan": "CeilingPlan",
    "ceiling plan": "CeilingPlan",

    "areaplan": "AreaPlan",
    "area plan": "AreaPlan",

    "section": "Section",

    "elevation": "Elevation",

    "3d": "ThreeD",

    "sheet": "DrawingSheet",

    "schedule": "Schedule",

    "detail": "Detail",

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

def normalize_text(
    text: str | None,
) -> str:

    if not text:

        return ""

    text = str(text)

    text = text.lower()

    text = re.sub(
        r"[^a-z0-9\s]",
        " ",
        text,
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


# ============================================================
# TOKENIZE
# ============================================================

def tokenize(
    text: str | None,
) -> list[str]:

    normalized = normalize_text(
        text
    )

    words = normalized.split()

    return [
        word
        for word in words
        if word not in ACTION_WORDS
    ]


# ============================================================
# EXTRACT FLOOR NUMBER
# ============================================================

def extract_floor_number(
    query: str,
):

    normalized = normalize_text(
        query
    )

    # --------------------------------------------------------
    # LEVEL 1
    # --------------------------------------------------------

    level_match = re.search(
        r"\blevel\s*(\d+)\b",
        normalized,
    )

    if level_match:

        return level_match.group(1)

    # --------------------------------------------------------
    # L1
    # --------------------------------------------------------

    l_match = re.search(
        r"\bl\s*[-]?\s*(\d+)\b",
        normalized,
    )

    if l_match:

        return l_match.group(1)

    # --------------------------------------------------------
    # FIRST / SECOND / THIRD...
    # --------------------------------------------------------

    for word, number in ORDINAL_MAP.items():

        pattern = (
            rf"\b{re.escape(word)}\b"
        )

        if re.search(
            pattern,
            normalized,
        ):

            return number

    return None


# ============================================================
# EXTRACT SEARCH TERMS
# ============================================================

def extract_search_terms(
    query: str,
) -> list[str]:

    normalized = normalize_text(
        query
    )

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

        if word in {
            "level",
            "floor",
        }:
            continue

        terms.append(word)

    return terms


# ============================================================
# SEARCH PHRASE
# ============================================================

def extract_search_phrase(
    query: str,
) -> str:

    terms = extract_search_terms(
        query
    )

    return " ".join(
        terms
    ).strip()


# ============================================================
# DETECT TARGET
# ============================================================

def detect_target(
    query: str,
) -> str:

    normalized = normalize_text(
        query
    )

    words = set(
        normalized.split()
    )

    # --------------------------------------------------------
    # Explicit project/file/document/model request
    # --------------------------------------------------------

    if words.intersection(
        PROJECT_WORDS
    ):

        return "PROJECT"

    # --------------------------------------------------------
    # Explicit view request
    # --------------------------------------------------------

    if words.intersection(
        VIEW_WORDS
    ):

        return "VIEW"

    # --------------------------------------------------------
    # Level references normally refer to views
    # --------------------------------------------------------

    if extract_floor_number(
        query
    ):

        return "VIEW"

    # --------------------------------------------------------
    # Default
    # --------------------------------------------------------

    return "VIEW"


# ============================================================
# DETECT ACTION
# ============================================================

def detect_action(
    query: str,
) -> str:

    normalized = normalize_text(
        query
    )

    # --------------------------------------------------------
    # OPEN
    # --------------------------------------------------------

    open_patterns = [

        "open",
        "take me to",
        "go to",
        "navigate to",
        "bring me to",

    ]

    for pattern in open_patterns:

        if pattern in normalized:

            return "OPEN"

    # --------------------------------------------------------
    # SEARCH
    # --------------------------------------------------------

    search_patterns = [

        "find",
        "search",
        "where",
        "show",
        "display",

    ]

    for pattern in search_patterns:

        if pattern in normalized:

            return "SEARCH"

    return "SEARCH"


# ============================================================
# DETECT VIEW TYPE
# ============================================================

def detect_view_type(
    query: str,
) -> str | None:

    normalized = normalize_text(
        query
    )

    ordered_terms = [

        "floor plan",
        "floorplan",

        "ceiling plan",
        "ceilingplan",

        "area plan",
        "areaplan",

        "section",

        "elevation",

        "3d",

        "sheet",

        "schedule",

        "detail",

    ]

    for term in ordered_terms:

        if term in normalized:

            return VIEW_TYPE_TERMS.get(
                term
            )

    return None


# ============================================================
# QUERY UNDERSTANDING
# ============================================================

def understand_query(
    query: str,
) -> dict:

    return {

        "original_query": query,

        "target": detect_target(
            query
        ),

        "action": detect_action(
            query
        ),

        "floor_number":
            extract_floor_number(
                query
            ),

        "view_type":
            detect_view_type(
                query
            ),

        "search_phrase":
            extract_search_phrase(
                query
            ),

        "search_terms":
            extract_search_terms(
                query
            ),

        "is_plan_query":
            "plan"
            in normalize_text(
                query
            ),

    }


# ============================================================
# VIEW TYPE SCORE
# ============================================================

def calculate_view_type_score(
    query_info: dict,
    candidate_view_type: str | None,
) -> float:

    requested_type = (
        query_info[
            "view_type"
        ]
    )

    normalized_candidate = (
        normalize_text(
            candidate_view_type
        )
    )

    score = 0.0

    # --------------------------------------------------------
    # Explicit view type
    # --------------------------------------------------------

    if requested_type:

        normalized_requested = (
            normalize_text(
                requested_type
            )
        )

        if (
            normalized_candidate
            == normalized_requested
        ):

            score += 15.0

        else:

            score -= 8.0

        return score

    # --------------------------------------------------------
    # Generic level navigation
    # --------------------------------------------------------

    if (
        query_info[
            "target"
        ] == "VIEW"
        and query_info[
            "floor_number"
        ]
        and not query_info[
            "view_type"
        ]
    ):

        if (
            normalized_candidate
            == "floorplan"
        ):

            score += 12.0

        elif (
            normalized_candidate
            == "areaplan"
        ):

            score -= 4.0

        elif (
            normalized_candidate
            == "ceilingplan"
        ):

            score -= 7.0

        elif (
            normalized_candidate
            == "drawingsheet"
        ):

            score -= 4.0

    # --------------------------------------------------------
    # Generic plan request
    # --------------------------------------------------------

    if query_info[
        "is_plan_query"
    ]:

        if (
            normalized_candidate
            == "floorplan"
        ):

            score += 5.0

        elif (
            normalized_candidate
            == "ceilingplan"
        ):

            score -= 3.0

        elif (
            normalized_candidate
            == "areaplan"
        ):

            score -= 2.0

    return score


# ============================================================
# LEVEL SCORE
# ============================================================

def calculate_level_score(
    query_info: dict,
    name: str | None,
    level_name: str | None,
) -> float:

    floor_number = (
        query_info[
            "floor_number"
        ]
    )

    if not floor_number:

        return 0.0

    normalized_name = (
        normalize_text(
            name
        )
    )

    normalized_level = (
        normalize_text(
            level_name
        )
    )

    score = 0.0

    # --------------------------------------------------------
    # L1 in level metadata
    # --------------------------------------------------------

    if re.search(
        rf"\bl\s*[-]?\s*"
        rf"{re.escape(floor_number)}\b",
        normalized_level,
    ):

        score += 7.0

    # --------------------------------------------------------
    # L1 in view name
    # --------------------------------------------------------

    if re.search(
        rf"\bl\s*[-]?\s*"
        rf"{re.escape(floor_number)}\b",
        normalized_name,
    ):

        score += 5.0

    # --------------------------------------------------------
    # LEVEL 1
    # --------------------------------------------------------

    if (
        f"level {floor_number}"
        in normalized_level
    ):

        score += 4.0

    return score


# ============================================================
# EXACT MATCH SCORE
# ============================================================

def calculate_exact_match_score(
    query_info: dict,
    name: str | None,
) -> float:

    search_phrase = (
        query_info[
            "search_phrase"
        ]
    )

    normalized_name = (
        normalize_text(
            name
        )
    )

    score = 0.0

    # --------------------------------------------------------
    # Exact phrase
    # --------------------------------------------------------

    if (
        search_phrase
        and search_phrase
        == normalized_name
    ):

        score += 15.0

    # --------------------------------------------------------
    # Exact L<number>
    # --------------------------------------------------------

    l_match = re.fullmatch(
        r"l\s*(\d+)",
        search_phrase or "",
    )

    if l_match:

        requested_level = (
            l_match.group(1)
        )

        candidate_match = (
            re.fullmatch(
                r"l\s*(\d+)",
                normalized_name,
            )
        )

        if candidate_match:

            candidate_level = (
                candidate_match.group(1)
            )

            if (
                requested_level
                == candidate_level
            ):

                score += 20.0

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

    query_terms = set(
        query_info[
            "search_terms"
        ]
    )

    # IMPORTANT:
    # Revit database fields can be NULL.
    # Convert every value to an empty string
    # before joining them.

    candidate_text = " ".join(
        [
            name or "",
            level_name or "",
            description or "",
        ]
    )

    candidate_terms = set(
        tokenize(
            candidate_text
        )
    )

    score = 0.0

    # --------------------------------------------------------
    # Matching terms
    # --------------------------------------------------------

    for term in query_terms:

        if term in candidate_terms:

            score += 2.0

    # --------------------------------------------------------
    # Name-specific matching
    # --------------------------------------------------------

    normalized_name = (
        normalize_text(
            name
        )
    )

    for term in query_terms:

        if term in normalized_name:

            score += 2.0

    # --------------------------------------------------------
    # Full phrase
    # --------------------------------------------------------

    search_phrase = (
        query_info[
            "search_phrase"
        ]
    )

    if (
        search_phrase
        and search_phrase
        in normalized_name
        and search_phrase
        != normalized_name
    ):

        score += 4.0

    return score


# ============================================================
# SPECIALIZED PENALTY
# ============================================================

def calculate_specialized_penalty(
    query_info: dict,
    name: str | None,
) -> float:

    if not (
        query_info[
            "floor_number"
        ]
        and query_info[
            "is_plan_query"
        ]
        and not query_info[
            "view_type"
        ]
    ):

        return 0.0

    normalized_name = (
        normalize_text(
            name
        )
    )

    penalty = 0.0

    # --------------------------------------------------------
    # Site plan
    # --------------------------------------------------------

    if "site plan" in normalized_name:

        penalty -= 8.0

    # --------------------------------------------------------
    # Specialized plans
    # --------------------------------------------------------

    for term in [

        "rooms",
        "room",
        "wall",
        "walls",
        "life safety",
        "kitchen",
        "export",
        "civil",
        "detail",
        "detailed",
        "dimension",
        "dimensions",
        "furniture",
        "electrical",
        "mechanical",
        "plumbing",
        "fire",
        "structural",
        "structure",

    ]:

        if term in normalized_name:

            penalty -= 3.0

    return penalty


# ============================================================
# SEMANTIC SCORE
# ============================================================

def calculate_semantic_similarity(
    distance,
) -> float:

    try:

        return 1 - float(
            distance
        )

    except (
        TypeError,
        ValueError,
    ):

        return 0.0


# ============================================================
# VIEW SEARCH
# ============================================================

def search_views(
    query: str,
    limit: int = 5,
    project_id: int | None = None,
):

    query_info = understand_query(
        query
    )

    query_embedding = create_embedding(
        query
    )

    # --------------------------------------------------------
    # Get active project if not supplied
    # --------------------------------------------------------

    if project_id is None:

        project_id = (
            get_active_project_id()
        )

    if project_id is None:

        return []

    # --------------------------------------------------------
    # Database search
    # --------------------------------------------------------

    with psycopg.connect(
        DATABASE_URL
    ) as connection:

        with connection.cursor() as cursor:

            # ------------------------------------------------
            # Auto-generate embeddings for newly synced views
            # ------------------------------------------------

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
                    v.embedding <=> %s::vector
                        AS distance,
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

    # --------------------------------------------------------
    # Rank results
    # --------------------------------------------------------

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

        semantic_similarity = (
            calculate_semantic_similarity(
                distance
            )
        )

        exact_score = (
            calculate_exact_match_score(
                query_info=query_info,
                name=name,
            )
        )

        view_type_score = (
            calculate_view_type_score(
                query_info=query_info,
                candidate_view_type=view_type,
            )
        )

        level_score = (
            calculate_level_score(
                query_info=query_info,
                name=name,
                level_name=level_name,
            )
        )

        keyword_score = (
            calculate_keyword_score(
                query_info=query_info,
                name=name,
                level_name=level_name,
                description=description,
            )
        )

        specialized_penalty = (
            calculate_specialized_penalty(
                query_info=query_info,
                name=name,
            )
        )

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
                "result_type": "view",

                "database_id":
                    database_id,

                "project_id":
                    row_project_id,

                "project_name":
                    project_name or "",

                "file_path":
                    file_path,

                "revit_view_id":
                    revit_view_id,

                "name":
                    name or "",

                "view_type":
                    view_type or "",

                "level_name":
                    level_name,

                "description":
                    description or "",

                "semantic_similarity":
                    semantic_similarity,

                "exact_match_score":
                    exact_score,

                "view_type_score":
                    view_type_score,

                "level_score":
                    level_score,

                "keyword_score":
                    keyword_score,

                "specialized_penalty":
                    specialized_penalty,

                "hybrid_score":
                    hybrid_score,

            }
        )

    ranked_results.sort(
        key=lambda item:
            item[
                "hybrid_score"
            ],
        reverse=True,
    )

    return ranked_results[
        :limit
    ]


# ============================================================
# PROJECT SEARCH
# ============================================================

def search_projects(
    query: str,
    limit: int = 5,
):

    query_info = understand_query(
        query
    )

    normalized_query = (
        normalize_text(
            query
        )
    )

    query_terms = set(
        query_info[
            "search_terms"
        ]
    )

    with psycopg.connect(
        DATABASE_URL
    ) as connection:

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

        normalized_name = (
            normalize_text(
                project_name
            )
        )

        score = 0.0

        # Exact project name

        if (
            normalized_query
            == normalized_name
        ):

            score += 20.0

        # Query inside project name

        if (
            normalized_query
            and normalized_query
            in normalized_name
        ):

            score += 10.0

        # Individual terms

        for term in query_terms:

            if term in normalized_name:

                score += 3.0

        ranked_results.append(
            {
                "result_type":
                    "project",

                "project_id":
                    project_id,

                "project_name":
                    project_name or "",

                "file_path":
                    file_path,

                "score":
                    score,

                "created_at":
                    created_at,

                "updated_at":
                    updated_at,

            }
        )

    ranked_results.sort(
        key=lambda item:
            item["score"],
        reverse=True,
    )

    return ranked_results[
        :limit
    ]


# ============================================================
# MAIN SEARCH FUNCTION
# ============================================================

def search(
    query: str,
    limit: int = 5,
):

    query_info = understand_query(
        query
    )

    target = query_info[
        "target"
    ]

    action = query_info[
        "action"
    ]

    # --------------------------------------------------------
    # PROJECT SEARCH
    # --------------------------------------------------------

    if target == "PROJECT":

        results = search_projects(
            query=query,
            limit=limit,
        )

    # --------------------------------------------------------
    # VIEW SEARCH
    # --------------------------------------------------------

    else:

        project_id = (
            get_active_project_id()
        )

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

            "original":
                query,

            "target":
                target,

            "action":
                action,

            "floor_number":
                query_info[
                    "floor_number"
                ],

            "view_type":
                query_info[
                    "view_type"
                ],

        },

        "target":
            target,

        "active_project_info":
            active_project_info,

        "results":
            results,

    }


# ============================================================
# DEVELOPMENT TEST
# ============================================================

if __name__ == "__main__":

    print(
        "=" * 60
    )

    print(
        "RevitAI Semantic Search Test"
    )

    print(
        "=" * 60
    )

    print(
        "Active Project ID:",
        get_active_project_id(),
    )

    test_queries = [

        "Open L1",

        "Show me the first floor plan",

        "Show me an elevation",

    ]

    for test_query in test_queries:

        print()
        print(
            "QUERY:",
            test_query,
        )

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

            print(
                "ERROR:",
                ex,
            )

    print(
        "=" * 60
    )