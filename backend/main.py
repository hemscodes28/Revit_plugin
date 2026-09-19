from typing import List, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.semantic_search import (
    search,
    understand_query,
)


# ============================================================
# FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title="RevitAI Backend",
    version="2.2.0",
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# REQUEST MODEL
# ============================================================

class ChatRequest(BaseModel):
    message: str


# ============================================================
# SEARCH RESULT MODEL
# ============================================================

class SearchResult(BaseModel):

    # --------------------------------------------------------
    # IMPORTANT
    # Electron / C# expects "type"
    # --------------------------------------------------------

    type: str

    # --------------------------------------------------------
    # Basic information
    # --------------------------------------------------------

    name: str

    description: str

    action: str

    # --------------------------------------------------------
    # Project information
    # --------------------------------------------------------

    project_id: int

    project_name: Optional[str] = None

    file_path: Optional[str] = None

    # --------------------------------------------------------
    # View information
    # --------------------------------------------------------

    view_type: Optional[str] = None

    level_name: Optional[str] = None

    revit_view_id: Optional[int] = None

    # --------------------------------------------------------
    # Search score
    # --------------------------------------------------------

    score: Optional[float] = None

    semantic_similarity: Optional[float] = None

    exact_match_score: Optional[float] = None

    view_type_score: Optional[float] = None

    level_score: Optional[float] = None

    keyword_score: Optional[float] = None

    specialized_penalty: Optional[float] = None

    hybrid_score: Optional[float] = None


# ============================================================
# CHAT RESPONSE MODEL
# ============================================================

class ChatResponse(BaseModel):

    response: str

    target: str

    results: List[SearchResult]


# ============================================================
# ROOT ENDPOINT
# ============================================================

@app.get("/")
def root():

    return {
        "message": "RevitAI backend is running",
        "version": "2.2.0",
    }


# ============================================================
# CHAT ENDPOINT
# ============================================================

@app.post(
    "/chat",
    response_model=ChatResponse,
)
def chat(
    request: ChatRequest,
):

    # ========================================================
    # CLEAN USER MESSAGE
    # ========================================================

    user_message = request.message.strip()

    # ========================================================
    # EMPTY MESSAGE
    # ========================================================

    if not user_message:

        return {
            "response": "Please enter a message.",
            "target": "VIEW",
            "results": [],
        }

    try:

        print()
        print("=" * 70)
        print("CHAT REQUEST")
        print("=" * 70)

        print(
            "User message:",
            user_message,
        )

        # ====================================================
        # UNDERSTAND QUERY BEFORE SEARCH
        # ====================================================
        #
        # This is important because we need to know whether
        # the user wants to OPEN something or simply SEARCH.
        #
        # OPEN:
        #     "Open L1"
        #     "Open first floor"
        #
        # SEARCH:
        #     "Find L1 views"
        #     "Show me all floor plans"
        #
        # OPEN requests return only the best result.
        # SEARCH requests can return multiple results.
        # ====================================================

        query_info = understand_query(
            user_message
        )

        action = query_info.get(
            "action",
            "SEARCH",
        )

        target_from_query = query_info.get(
            "target",
            "VIEW",
        )

        print()
        print("QUERY UNDERSTANDING")
        print("=" * 70)

        print(
            "Target:",
            target_from_query,
        )

        print(
            "Action:",
            action,
        )

        print(
            "Floor:",
            query_info.get(
                "floor_number"
            ),
        )

        print(
            "View type:",
            query_info.get(
                "view_type"
            ),
        )

        print(
            "Search phrase:",
            query_info.get(
                "search_phrase"
            ),
        )

        # ====================================================
        # SEARCH LIMIT
        # ====================================================
        #
        # OPEN -> one best result
        #
        # SEARCH -> five results
        #
        # This prevents:
        #
        # Open L1
        #
        # from showing:
        #
        # L1
        # L1
        # L1
        # L1
        # L1
        #
        # Instead it shows only the best matching view.
        # ====================================================

        if (
            action.upper()
            == "OPEN"
        ):

            search_limit = 1

        else:

            search_limit = 5

        print()
        print(
            "Search limit:",
            search_limit,
        )

        # ====================================================
        # SEMANTIC SEARCH
        # ====================================================

        search_response = search(
            query=user_message,
            limit=search_limit,
        )

        print()
        print("SEARCH RESPONSE")
        print("=" * 70)

        print(
            search_response
        )

        # ====================================================
        # GET TARGET
        # ====================================================

        target = search_response.get(
            "target",
            target_from_query,
        )

        # ====================================================
        # GET RESULTS
        # ====================================================

        raw_results = search_response.get(
            "results",
            [],
        )

        # ====================================================
        # NO RESULTS
        # ====================================================

        if not raw_results:

            print()
            print("NO RESULTS")
            print("=" * 70)

            active_info = search_response.get("active_project_info")

            if active_info and not active_info.get("success"):
                message = active_info.get(
                    "message",
                    "No active Revit project is currently available."
                )
            elif active_info and active_info.get("success") and not active_info.get("synced"):
                proj_name = active_info.get("project_name") or "the active project"
                message = (
                    f"The active Revit project '{proj_name}' is not synchronized yet. "
                    f"Please click 'Sync Views' in the RevitAI tab in Revit."
                )
            elif target == "PROJECT":

                message = (
                    f'I could not find a Revit project '
                    f'matching "{user_message}".'
                )

            else:

                message = (
                    f'I could not find a matching Revit view '
                    f'for "{user_message}".'
                )

            return {
                "response": message,
                "target": target,
                "results": [],
            }

        # ====================================================
        # NORMALIZE RESULTS
        # ====================================================
        #
        # semantic_search.py returns:
        #
        # result_type
        #
        # But the C# / Electron layer expects:
        #
        # type
        #
        # We convert it here.
        #
        # We also put "action" directly inside each result.
        # ====================================================

        normalized_results = []

        for result in raw_results:

            # ------------------------------------------------
            # RESULT TYPE
            # ------------------------------------------------

            result_type = result.get(
                "result_type",
                result.get(
                    "type",
                    target.lower(),
                ),
            )

            # ------------------------------------------------
            # RESULT NAME
            # ------------------------------------------------

            result_name = (
                result.get(
                    "name"
                )
                or result.get(
                    "project_name"
                )
                or ""
            )

            # ------------------------------------------------
            # DESCRIPTION
            # ------------------------------------------------

            result_description = (
                result.get(
                    "description"
                )
                or ""
            )

            # ------------------------------------------------
            # PROJECT ID
            # ------------------------------------------------

            result_project_id = (
                result.get(
                    "project_id"
                )
                or 0
            )

            # ------------------------------------------------
            # CREATE NORMALIZED RESULT
            # ------------------------------------------------

            normalized_result = {

                # ============================================
                # C# / ELECTRON COMPATIBILITY
                # ============================================

                "type":
                    result_type,

                "action":
                    action,

                # ============================================
                # BASIC INFORMATION
                # ============================================

                "name":
                    result_name,

                "description":
                    result_description,

                # ============================================
                # PROJECT
                # ============================================

                "project_id":
                    result_project_id,

                "project_name":
                    result.get(
                        "project_name"
                    ),

                "file_path":
                    result.get(
                        "file_path"
                    ),

                # ============================================
                # VIEW
                # ============================================

                "view_type":
                    result.get(
                        "view_type"
                    ),

                "level_name":
                    result.get(
                        "level_name"
                    ),

                "revit_view_id":
                    result.get(
                        "revit_view_id"
                    ),

                # ============================================
                # SCORES
                # ============================================

                "score":
                    result.get(
                        "score"
                    ),

                "semantic_similarity":
                    result.get(
                        "semantic_similarity"
                    ),

                "exact_match_score":
                    result.get(
                        "exact_match_score"
                    ),

                "view_type_score":
                    result.get(
                        "view_type_score"
                    ),

                "level_score":
                    result.get(
                        "level_score"
                    ),

                "keyword_score":
                    result.get(
                        "keyword_score"
                    ),

                "specialized_penalty":
                    result.get(
                        "specialized_penalty"
                    ),

                "hybrid_score":
                    result.get(
                        "hybrid_score"
                    ),
            }

            normalized_results.append(
                normalized_result
            )

        # ====================================================
        # DEBUG OUTPUT
        # ====================================================

        print()
        print("NORMALIZED RESULTS")
        print("=" * 70)

        for index, result in enumerate(
            normalized_results,
            start=1,
        ):

            print()
            print(
                f"Result {index}"
            )

            print(
                "  Type:",
                result["type"],
            )

            print(
                "  Action:",
                result["action"],
            )

            print(
                "  Name:",
                result["name"],
            )

            print(
                "  Description:",
                result["description"],
            )

            print(
                "  Project ID:",
                result["project_id"],
            )

            print(
                "  Project Name:",
                result["project_name"],
            )

            print(
                "  Revit View ID:",
                result["revit_view_id"],
            )

            print(
                "  View Type:",
                result["view_type"],
            )

            print(
                "  Level:",
                result["level_name"],
            )

            print(
                "  Hybrid Score:",
                result["hybrid_score"],
            )

        print()
        print("=" * 70)

        print(
            "Final result count:",
            len(normalized_results),
        )

        print(
            "Final target:",
            target,
        )

        print(
            "Final action:",
            action,
        )

        print("=" * 70)

        # ====================================================
        # USER-FACING RESPONSE
        # ====================================================

        if (
            action.upper()
            == "OPEN"
        ):

            if len(normalized_results) == 1:

                response_message = (
                    "I found the best matching Revit view."
                )

            else:

                response_message = (
                    f"I found {len(normalized_results)} "
                    f"matching Revit views."
                )

        else:

            response_message = (
                f"Search completed successfully. "
                f"Found {len(normalized_results)} "
                f"result(s)."
            )

        # ====================================================
        # FINAL RESPONSE
        # ====================================================

        return {
            "response":
                response_message,

            "target":
                target,

            "results":
                normalized_results,
        }

    # ========================================================
    # ERROR HANDLING
    # ========================================================

    except Exception as e:

        import traceback

        print()
        print("=" * 70)
        print("CHAT ERROR")
        print("=" * 70)

        print(
            "Error:",
            str(e),
        )

        traceback.print_exc()

        print("=" * 70)

        return {
            "response":
                "Backend error: "
                + str(e),

            "target":
                "ERROR",

            "results":
                [],
        }


# ============================================================
# DIRECT START
# ============================================================

if __name__ == "__main__":

    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
    )