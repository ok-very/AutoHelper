"""
AutoMail API Server
FastAPI backend for email triage with Gemini drafts and Outlook integration.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import uvicorn

from gemini_draft import compress_thread, generate_draft, EmailContext
from outlook_com import create_reply_draft, check_outlook_available
from monday_api import search_boards, find_board_by_project, create_task_from_email
from onedrive_files import push_attachment_to_project, push_multiple_attachments, get_project_folders
from datetime import datetime

app = FastAPI(title="AutoMail API", version="1.0.0")

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Models ---

class EmailData(BaseModel):
    id: str
    subject: str
    sender: str = ""
    senderName: str = ""
    project: str = ""
    municipality: Optional[str] = None
    stage: Optional[str] = None
    bodyText: str = ""

class ThreadData(BaseModel):
    emails: List[EmailData]
    templates: Optional[List[str]] = None

class DraftRequest(BaseModel):
    to: str
    subject: str
    body: str
    cc: Optional[str] = None

class MondayTaskRequest(BaseModel):
    developer: str
    project: str
    task_name: str
    description: str = ""
    due_date: Optional[str] = None
    status: Optional[str] = None

class AttachmentInfo(BaseModel):
    path: str
    subfolder: Optional[str] = None

class AttachmentPushRequest(BaseModel):
    developer: str
    project: str
    attachments: List[AttachmentInfo]
    email_date: Optional[str] = None  # YYYY-MM-DD format


# --- Routes ---

@app.get("/")
def root():
    return {"status": "ok", "service": "AutoMail API"}


@app.get("/api/outlook/status")
def outlook_status():
    """Check if Outlook is available"""
    return check_outlook_available()


@app.post("/api/draft/generate")
def generate_draft_route(thread: ThreadData):
    """Generate a draft reply using Gemini API"""
    if not thread.emails:
        raise HTTPException(status_code=400, detail="No emails provided")
    
    # Convert to format expected by compress_thread
    emails_dict = [
        {
            "subject": e.subject,
            "fromName": e.senderName,
            "from": e.sender,
            "projectName": e.project,
            "municipality": e.municipality,
            "stage": e.stage,
            "bodyText": e.bodyText,
        }
        for e in thread.emails
    ]
    
    try:
        context = compress_thread(emails_dict)
        result = generate_draft(context, thread.templates)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/draft/send-to-outlook")
def send_to_outlook(draft: DraftRequest):
    """Send a draft to Outlook's Drafts folder"""
    result = create_reply_draft(
        original_sender=draft.to,
        original_subject=draft.subject,
        reply_body=draft.body,
        cc=draft.cc
    )
    
    if not result.get("success"):
        raise HTTPException(
            status_code=500, 
            detail=result.get("error", "Failed to create draft")
        )
    
    return result


# --- Monday.com Routes ---

@app.get("/api/monday/boards")
def get_boards(search: str = ""):
    """Get boards from Monday.com workspace (optionally filtered)"""
    return search_boards(search if search else "")


@app.get("/api/monday/board/{developer}/{project}")
def get_board(developer: str, project: str):
    """Find a board by Developer - Project pattern"""
    result = find_board_by_project(developer, project)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@app.post("/api/monday/task")
def create_monday_task(task: MondayTaskRequest):
    """Create a task on the appropriate Monday.com board"""
    result = create_task_from_email(
        developer=task.developer,
        project=task.project,
        task_name=task.task_name,
        description=task.description,
        due_date=task.due_date,
        status=task.status
    )
    
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    
    return result


# --- OneDrive Routes ---

@app.get("/api/onedrive/folders")
def list_project_folders():
    """List all project folders in OneDrive"""
    folders = get_project_folders()
    return {"folders": folders, "count": len(folders)}


@app.post("/api/onedrive/push")
def push_attachments(request: AttachmentPushRequest):
    """
    Push email attachments to OneDrive project folder.
    
    Process:
    1. Search Monday.com for matching board to get Developer - Project
    2. Resolve the correct OneDrive folder (or create it)
    3. Copy files with date prefix, skip duplicates
    """
    # Parse email date if provided
    email_date = None
    if request.email_date:
        try:
            email_date = datetime.strptime(request.email_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    
    # Step 1: Cross-reference with Monday.com
    monday_board_name = None
    resolved_developer = request.developer
    resolved_project = request.project
    
    if request.project:
        monday_result = find_board_by_project(request.project)
        if "board" in monday_result:
            board = monday_result["board"]
            monday_board_name = board.get("name")
            resolved_developer = board.get("developer", request.developer)
            resolved_project = board.get("project", request.project)
    
    # Step 2: Resolve folder using cross-reference
    from onedrive_files import resolve_project_folder
    folder_result = resolve_project_folder(
        developer=resolved_developer,
        project=resolved_project,
        monday_board_name=monday_board_name,
        create_if_missing=True
    )
    
    # Step 3: Push attachments to resolved folder
    attachments = [{"path": a.path, "subfolder": a.subfolder} for a in request.attachments]
    
    result = push_multiple_attachments(
        attachments=attachments,
        developer=resolved_developer,
        project=resolved_project,
        email_date=email_date
    )
    
    # Add folder resolution info to response
    result["folder"] = {
        "path": folder_result["path"],
        "name": folder_result["folder_name"],
        "method": folder_result["method"],
        "created": folder_result["created"]
    }
    
    return result

# --- Monday Email Routes ---

class PostEmailRequest(BaseModel):
    item_id: str
    subject: str
    sender: str
    body: str
    received_date: Optional[str] = None
    attachments: list[str] = []


@app.get("/api/monday/items-for-project/{project_name}")
def get_monday_items_suggestions(project_name: str, limit: int = 10):
    """
    Get Monday.com item suggestions for a project.
    Used to populate dropdown when user wants to post email to Monday.
    """
    from monday_api import get_items_for_project
    result = get_items_for_project(project_name, limit=limit)
    
    if "error" in result and "suggestions" not in result:
        raise HTTPException(status_code=404, detail=result["error"])
    
    return result


@app.post("/api/monday/post-email")
def post_email_to_monday(request: PostEmailRequest):
    """
    Post an email thread to a Monday.com item as an update.
    """
    from monday_api import post_email_to_item
    
    result = post_email_to_item(
        item_id=request.item_id,
        subject=request.subject,
        sender=request.sender,
        body=request.body,
        received_date=request.received_date,
        attachments=request.attachments
    )
    
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    
    return result


# --- Run ---

if __name__ == "__main__":
    print("Starting AutoMail API Server...")
    print("Docs: http://localhost:8000/docs")
    uvicorn.run(app, host="0.0.0.0", port=8000)
