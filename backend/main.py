import os
from typing import List, Optional
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.semantic_search import (
    get_active_project_id,
    get_active_project_info,
    search,
    understand_query,
)


# ============================================================
# FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title="RevitAI Backend",
    version="3.0.0",
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
# SESSION CONTEXT (For Conversational Follow-ups)
# ============================================================

SESSION_CONTEXT = {
    "project_id": None,
    "results": [],
    "current_level": None,
    "current_view_type": None,
    "current_category": None,
}


# ============================================================
# REQUEST MODEL
# ============================================================

class ChatRequest(BaseModel):
    message: str


# ============================================================
# SEARCH RESULT MODEL
# ============================================================

class SearchResult(BaseModel):
    type: str
    result_type: Optional[str] = None
    name: str
    description: str
    action: str
    project_id: int
    project_name: Optional[str] = None
    file_path: Optional[str] = None
    view_type: Optional[str] = None
    level_name: Optional[str] = None
    revit_view_id: Optional[int] = None
    revit_element_id: Optional[int] = None
    category: Optional[str] = None
    family_name: Optional[str] = None
    type_name: Optional[str] = None
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
    success: bool = True
    type: str = "message"
    intent: Optional[str] = "GENERAL_CONVERSATION"
    message: str
    response: str
    target: str = "CONVERSATION"
    results: List[SearchResult] = []


# ============================================================
# ROOT ENDPOINT
# ============================================================

@app.get("/")
def root():
    return {
        "message": "RevitAI backend is running",
        "version": "3.0.0",
    }


# ============================================================
# CURRENT PROJECT ENDPOINT
# ============================================================

@app.get("/current-project")
def current_project():
    info = get_active_project_info()
    if info and info.get("success"):
        return {
            "success": True,
            "live": info.get("live", False),
            "project_id": info.get("project_id"),
            "project_name": info.get("project_name"),
            "file_path": info.get("file_path"),
            "synced": info.get("synced", False),
        }
    return {
        "success": False,
        "live": False,
        "message": "No active Revit project is currently connected.",
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
    user_message = request.message.strip()

    if not user_message:
        return {
            "success": True,
            "type": "message",
            "intent": "CLARIFICATION_REQUIRED",
            "message": "Please enter a message.",
            "response": "Please enter a message.",
            "target": "CONVERSATION",
            "results": [],
        }

    try:
        print()
        print("=" * 70)
        print("CHAT REQUEST")
        print("=" * 70)
        print("User message:", user_message)

        # ----------------------------------------------------
        # DYNAMIC ACTIVE PROJECT DETECTION & CONTEXT INVALIDATION
        # ----------------------------------------------------
        active_id = get_active_project_id()

        if (
            SESSION_CONTEXT.get("project_id") is not None
            and active_id is not None
            and SESSION_CONTEXT.get("project_id") != active_id
        ):
            print(
                f"Active Revit project changed from {SESSION_CONTEXT.get('project_id')} to {active_id}. "
                f"Invalidating previous project search context."
            )
            SESSION_CONTEXT["results"] = []
            SESSION_CONTEXT["current_level"] = None
            SESSION_CONTEXT["current_view_type"] = None
            SESSION_CONTEXT["current_category"] = None
            SESSION_CONTEXT["project_id"] = active_id
        elif active_id is not None and SESSION_CONTEXT.get("project_id") is None:
            SESSION_CONTEXT["project_id"] = active_id

        from backend.gemini_service import classify_intent_with_gemini

        classification = classify_intent_with_gemini(user_message, SESSION_CONTEXT)
        intent = classification.get("intent", "CLARIFICATION_REQUIRED")
        confidence = classification.get("confidence", 0.0)
        entities = classification.get("entities", {}) or {}
        conv_response = classification.get("conversationalResponse")

        print("Classified Intent:", intent, f"(confidence: {confidence})")

        # ----------------------------------------------------
        # 1. GENERAL_CONVERSATION
        # ----------------------------------------------------
        if intent == "GENERAL_CONVERSATION":
            msg = conv_response or "Hello! 👋 I am your RevitAI Assistant. How can I help you navigate or find views in your Revit model today?"
            return {
                "success": True,
                "type": "message",
                "intent": "GENERAL_CONVERSATION",
                "message": msg,
                "response": msg,
                "target": "CONVERSATION",
                "results": [],
            }

        # ----------------------------------------------------
        # 2. PROJECT_INFO ("What project am I working on?", "Which project is open?")
        # ----------------------------------------------------
        if intent == "PROJECT_INFO":
            # Check if query actually targets an explicit view/sheet entity code (e.g., "show file L3", "open file SD105")
            from backend.semantic_search import search_exact_entity_project_scoped
            exact_entities = search_exact_entity_project_scoped(user_message, active_id)
            has_strong_exact_match = exact_entities and exact_entities[0].get("exact_match_score", 0) >= 95.0
            
            if not has_strong_exact_match:
                active_info = get_active_project_info()
                if active_info and active_info.get("success") and active_info.get("project_name"):
                    proj_name = active_info.get("project_name")
                    msg = f"You are currently working on **{proj_name}**."
                else:
                    msg = "No active Revit project is currently connected or open."

                return {
                    "success": True,
                    "type": "message",
                    "intent": "PROJECT_INFO",
                    "message": msg,
                    "response": msg,
                    "target": "CONVERSATION",
                    "results": [],
                }
            else:
                intent = "REVIT_SEARCH"

        # ----------------------------------------------------
        # 3. HELP
        # ----------------------------------------------------
        if intent == "HELP":
            msg = conv_response or (
                "I can help you search and open views in your active Revit project using natural language.\n\n"
                "Examples you can try:\n"
                "• 'Open L1' or 'Open Level 1'\n"
                "• 'Show me the first floor plan'\n"
                "• 'Show me the 3D view'\n"
                "• 'Find elevations' or 'Find sections'"
            )
            return {
                "success": True,
                "type": "message",
                "intent": "HELP",
                "message": msg,
                "response": msg,
                "target": "CONVERSATION",
                "results": [],
            }

        # ----------------------------------------------------
        # 4. CLARIFICATION_REQUIRED (Low confidence or ambiguous)
        # ----------------------------------------------------
        if intent == "CLARIFICATION_REQUIRED" or confidence < 0.75:
            msg = conv_response or (
                "I'm not sure which Revit view you're looking for. "
                "Could you specify a level or view type? For example: 'Open L1 floor plan' or 'Show 3D view'."
            )
            return {
                "success": True,
                "type": "clarification",
                "intent": "CLARIFICATION_REQUIRED",
                "message": msg,
                "response": msg,
                "target": "CONVERSATION",
                "results": [],
            }

        # ----------------------------------------------------
        # 5. FOLLOW-UP SELECTION ("Open the first one", "Open #2")
        # ----------------------------------------------------
        result_idx = entities.get("resultIndex")
        if intent == "FOLLOW_UP" and result_idx is not None:
            current_active_id = get_active_project_id()

            if (
                SESSION_CONTEXT.get("results")
                and SESSION_CONTEXT.get("project_id") is not None
                and current_active_id is not None
                and SESSION_CONTEXT.get("project_id") == current_active_id
            ):
                previous_results = SESSION_CONTEXT["results"]
                if 0 <= result_idx < len(previous_results):
                    selected_result = dict(previous_results[result_idx])
                    selected_result["action"] = "OPEN"
                    msg = f"Opening view #{result_idx + 1}: {selected_result['name']}."

                    return {
                        "success": True,
                        "type": "search_results",
                        "intent": "REVIT_ACTION",
                        "message": msg,
                        "response": msg,
                        "target": "VIEW",
                        "results": [selected_result],
                    }
                else:
                    msg = f"Result index #{result_idx + 1} is out of range. Only {len(previous_results)} view(s) were returned in the last search."
                    return {
                        "success": True,
                        "type": "clarification",
                        "intent": "CLARIFICATION_REQUIRED",
                        "message": msg,
                        "response": msg,
                        "target": "CONVERSATION",
                        "results": [],
                    }
            else:
                msg = (
                    "The active Revit project has changed or there are no previous search results "
                    "for this project. Please search for a view first, such as 'Show me floor plans'."
                )
                return {
                    "success": True,
                    "type": "clarification",
                    "intent": "CLARIFICATION_REQUIRED",
                    "message": msg,
                    "response": msg,
                    "target": "CONVERSATION",
                    "results": [],
                }

        # ----------------------------------------------------
        # 6. REVIT_SEARCH / REVIT_ACTION / FOLLOW_UP SEARCH
        # ----------------------------------------------------
        if entities.get("level"):
            SESSION_CONTEXT["current_level"] = entities["level"]
        if entities.get("viewType"):
            SESSION_CONTEXT["current_view_type"] = entities["viewType"]
        if entities.get("category"):
            SESSION_CONTEXT["current_category"] = entities["category"]

        action = entities.get("action") or "SEARCH"

        # Build query string, inheriting previous context for follow-up corrections (e.g. "no, I meant L5")
        if intent == "FOLLOW_UP" and entities.get("level"):
            ctx_cat = SESSION_CONTEXT.get("current_category") or ""
            ctx_vt = SESSION_CONTEXT.get("current_view_type") or ""
            query_for_search = f"{entities['level']} {ctx_cat} {ctx_vt} plan".strip()
        else:
            query_for_search = classification.get("normalizedQuery") or user_message

        search_limit = 1 if action.upper() == "OPEN" else 5

        search_response = search(
            query=query_for_search,
            limit=search_limit,
        )

        target = search_response.get("target", "VIEW")
        raw_results = search_response.get("results", [])

        # NO RESULTS HANDLING
        if not raw_results:
            active_info = search_response.get("active_project_info")
            query_info = search_response.get("query_info", {}) or {}
            explicit_vname = query_info.get("explicit_view_name")

            if explicit_vname:
                message = f"I couldn't find an entity named '{explicit_vname}' in the current Revit project."
            elif active_info and not active_info.get("success"):
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
                message = f'I could not find a Revit project matching "{user_message}".'
            else:
                message = f'I could not find a matching Revit view for "{user_message}".'

            return {
                "success": True,
                "type": "clarification",
                "intent": "CLARIFICATION_REQUIRED",
                "message": message,
                "response": message,
                "target": target,
                "results": [],
            }

        # NORMALIZE RESULTS
        normalized_results = []
        for result in raw_results:
            raw_res_type = result.get(
                "result_type",
                result.get("type", target.lower()),
            )
            canonical_res_type = raw_res_type.upper() if raw_res_type else "VIEW"
            result_name = result.get("name") or result.get("project_name") or ""
            result_description = result.get("description") or ""
            result_project_id = result.get("project_id") or 0

            normalized_result = {
                "type": result.get("type", canonical_res_type.lower()),
                "result_type": canonical_res_type,
                "action": action,
                "name": result_name,
                "description": result_description,
                "project_id": result_project_id,
                "project_name": result.get("project_name"),
                "file_path": result.get("file_path"),
                "view_type": result.get("view_type"),
                "level_name": result.get("level_name"),
                "revit_view_id": result.get("revit_view_id"),
                "revit_element_id": result.get("revit_element_id"),
                "category": result.get("category"),
                "family_name": result.get("family_name"),
                "type_name": result.get("type_name"),
                "score": result.get("score"),
            }
            normalized_results.append(normalized_result)

        # UPDATE SESSION CONTEXT FOR FOLLOW-UPS
        current_active_id = get_active_project_id()
        SESSION_CONTEXT["project_id"] = current_active_id
        SESSION_CONTEXT["results"] = normalized_results

        # USER-FACING RESPONSE MESSAGE
        if target == "ELEMENT":
            cat_name = normalized_results[0].get("category", "element") if normalized_results else "element"
            lvl_name = normalized_results[0].get("level_name") if normalized_results else None
            lvl_str = f" on {lvl_name}" if lvl_name else ""
            response_message = f"I found {len(normalized_results)} {cat_name.lower()} element(s){lvl_str}."
        elif action.upper() == "OPEN":
            if len(normalized_results) == 1:
                response_message = f"Found {normalized_results[0]['name']} in the active project."
            else:
                response_message = f"I found {len(normalized_results)} matching views."
        else:
            vtype_str = normalized_results[0].get("view_type", "view") if normalized_results else "view"
            response_message = f"I found {len(normalized_results)} matching {vtype_str} result(s)."


        return {
            "success": True,
            "type": "search_results",
            "intent": intent,
            "message": response_message,
            "response": response_message,
            "target": target,
            "results": normalized_results,
        }

    except Exception as e:
        import traceback
        print()
        print("=" * 70)
        print("CHAT ERROR")
        print("=" * 70)
        print("Error:", str(e))
        traceback.print_exc()
        print("=" * 70)

        return {
            "success": False,
            "type": "error",
            "intent": "ERROR",
            "message": "Backend error: " + str(e),
            "response": "Backend error: " + str(e),
            "target": "ERROR",
            "results": [],
        }


# ============================================================
# REVIT ACTION PROXY ENDPOINT
# ============================================================

class RevitActionRequest(BaseModel):
    action: str = "OPEN"
    name: Optional[str] = None
    type: Optional[str] = None
    description: Optional[str] = None
    revit_view_id: Optional[int] = None
    revit_element_id: Optional[int] = None
    project_id: Optional[int] = None
    file_path: Optional[str] = None


@app.post("/revit-action")
def execute_revit_action(request: RevitActionRequest):
    import urllib.request
    import json

    ports = [8765, 8766, 8767, 8768, 8769, 8770]
    payload = request.model_dump(exclude_none=True)
    json_data = json.dumps(payload).encode("utf-8")

    for port in ports:
        try:
            url = f"http://127.0.0.1:{port}/"
            req = urllib.request.Request(
                url,
                data=json_data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                if response.status == 200:
                    res_body = response.read().decode("utf-8")
                    return json.loads(res_body)
        except Exception:
            continue

    return {
        "success": False,
        "message": "Could not communicate with the Revit plugin. Please check that Revit is open and active.",
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