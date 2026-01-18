"""
FastAPI webhook application for GitLab PR review using Ollama.
"""
import logging
import os
import re
from typing import Optional, Tuple
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI, Request, HTTPException, Header, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import gitlab
from config import OLLAMA_BASE_URL, OLLAMA_MODEL, GITLAB_URL, GITLAB_PRIVATE_TOKEN, GITLAB_PROJECT_ID

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="GitLab PR Reviewer", version="1.0.0")

# Custom Review Prompt - hardcoded for easy deployment
PROMPT = """
You are reviewing GitLab merge requests for table definition YAML files. 

VALIDATION RULES:

**Table Name:**
- Must be lowercase, snake_case (e.g., customer_orders, sales_data_2024)
- Must start with letter/number (not underscore)
- No spaces, hyphens, uppercase, or special characters except underscore
- Must be descriptive (not "a", "test", "table1")
- Cannot be SQL reserved words

**Namespace:**
- Must be lowercase, snake_case
- No spaces, hyphens, uppercase, or special characters except underscore
- Must start with letter/number

**Columns (Schema Fields):**
- Field names must follow snake_case convention
- Must be lowercase, descriptive
- No spaces, hyphens, uppercase in field names

OUTPUT FORMAT (use EXACTLY this format, keep it SHORT):

```
🔍 Code Review Summary

Table Name Check: [PASS / FAIL]
Reason: [one line reason if FAIL, or "OK" if PASS]

Namespace Check: [PASS / FAIL]
Reason: [one line reason if FAIL, or "OK" if PASS]

Column Check: [PASS / FAIL]
Reason: [one line reason if FAIL, or "OK" if PASS]

Action: [APPROVE / REQUEST CHANGES]
```

IMPORTANT:
- Keep output SHORT and CONCISE - one line per check
- Only include reasons if there are failures
- If all checks PASS, use "OK" for reasons
- Block merge if ANY check FAILS
"""


class GitLabClient:
    def __init__(self, project_id=None, project_path=None):
        """
        Gitlab login.

        Args:
            project_id: Optional project ID (numeric). If not provided, uses GITLAB_PROJECT_ID from config.
            project_path: Optional project path (e.g., "group/project"). If provided, uses this instead of project_id.
        """
        self.gl = gitlab.Gitlab(GITLAB_URL, private_token=GITLAB_PRIVATE_TOKEN)
        self.gl.auth()
        
        if project_path:
            # Get project by path (namespace/project-name)
            self.project = self.gl.projects.get(project_path)
            logging.info(f"Connected to GitLab project by path: {project_path}")
        else:
            project_id = project_id or GITLAB_PROJECT_ID
            self.project = self.gl.projects.get(int(project_id))
            logging.info(f"Connected to GitLab project {project_id}")

    def get_merge_request(self, mr_id):
        """Fetching Merge Request information."""
        return self.project.mergerequests.get(int(mr_id))

    def get_merge_request_diff(self, mr_id):
        """Fetching diff for the Merge Request."""
        mr = self.get_merge_request(mr_id)
        changes = mr.changes()
        return "\n".join([change["diff"] for change in changes["changes"]])

    def add_comment_to_mr(self, mr_id, comment):
        """Adding a review comment to the Merge Request."""
        mr = self.get_merge_request(mr_id)
        mr.notes.create({"body": comment})
        logging.info(f"Added review comment to MR {mr_id}.")


class MergeRequestWebhook(BaseModel):
    """GitLab webhook payload structure for merge request events."""
    object_kind: str
    event_type: Optional[str] = None
    object_attributes: Optional[dict] = None
    merge_request: Optional[dict] = None
    project: Optional[dict] = None


def call_ollama_api(prompt: str, model: str = OLLAMA_MODEL) -> str:
    """
    Call Ollama API to generate a response.
    
    Args:
        prompt: The prompt to send to Ollama
        model: The model name to use (default: from config)
    
    Returns:
        The generated response text
    """
    url = f"{OLLAMA_BASE_URL}/api/generate"

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False
    }

    try:
        with httpx.Client(timeout=120.0) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            result = response.json()
            return result.get("response", "No response from Ollama")
    except httpx.TimeoutException:
        logger.error("Ollama API request timed out")
        return "Error: Request to Ollama timed out. Please try again."
    except httpx.RequestError as e:
        logger.error(f"Error calling Ollama API: {e}")
        return f"Error: Failed to connect to Ollama API at {OLLAMA_BASE_URL}"
    except Exception as e:
        logger.error(f"Unexpected error calling Ollama API: {e}")
        return f"Error: {str(e)}"


def parse_gitlab_pr_url(pr_url: str) -> Tuple[Optional[str], Optional[int]]:
    """
    Parse a GitLab PR URL to extract project path and merge request ID.
    
    Args:
        pr_url: GitLab merge request URL (e.g., https://gitlab.com/group/project/-/merge_requests/123)
    
    Returns:
        Tuple of (project_path, mr_id) or (None, None) if parsing fails
    """
    try:
        # Parse URL
        parsed = urlparse(pr_url)
        
        # Extract path (e.g., /group/project/-/merge_requests/123)
        path = parsed.path
        
        # Match pattern: /namespace/project/-/merge_requests/MR_ID
        pattern = r'/(.+?)/-/merge_requests/(\d+)'
        match = re.search(pattern, path)
        
        if match:
            project_path = match.group(1)  # e.g., "group/project" or "group/subgroup/project"
            mr_id = int(match.group(2))
            return project_path, mr_id
        
        logger.error(f"Could not parse GitLab PR URL: {pr_url}")
        return None, None
    
    except Exception as e:
        logger.error(f"Error parsing GitLab PR URL {pr_url}: {e}")
        return None, None


def review_merge_request(gitlab_client: GitLabClient, mr_id: int, mr_title: str = None) -> dict:
    """
    Perform a review on a merge request.
    
    Args:
        gitlab_client: GitLabClient instance
        mr_id: Merge request ID (iid)
        mr_title: Optional merge request title
    
    Returns:
        Dictionary with review status and message
    """
    try:
        # Get merge request info if title not provided
        if not mr_title:
            mr = gitlab_client.get_merge_request(mr_id)
            mr_title = mr.title
        
        # Get merge request diff
        try:
            diff = gitlab_client.get_merge_request_diff(mr_id)
            if not diff:
                logger.warning(f"No diff found for MR {mr_id}")
                return {
                    "status": "error",
                    "message": f"No changes found in MR {mr_id}"
                }
        except Exception as e:
            logger.error(f"Error fetching diff for MR {mr_id}: {e}")
            return {
                "status": "error",
                "message": f"Failed to fetch MR diff: {str(e)}"
            }
        
        # Use hardcoded prompt
        custom_prompt = PROMPT.strip()
        
        # Build complete review prompt
        mr_info = {
            "title": mr_title,
            "iid": mr_id
        }
        
        review_prompt = build_review_prompt(custom_prompt, diff, mr_info)
        
        # Call Ollama API
        logger.info(f"Calling Ollama API with model: {OLLAMA_MODEL}")
        ollama_response = call_ollama_api(review_prompt, OLLAMA_MODEL)
        
        if ollama_response.startswith("Error:"):
            logger.error(f"Ollama API error: {ollama_response}")
            comment = f"⚠️ **Automated Review Error**\n\n{ollama_response}\n\nPlease check the reviewer service logs."
        else:
            # Format the review comment
            comment = f"""🤖 **Automated Code Review** (via Ollama {OLLAMA_MODEL})

{ollama_response}

---
*This review was generated automatically by the GitLab PR Reviewer service.*
"""
        
        # Post comment to GitLab MR
        try:
            gitlab_client.add_comment_to_mr(mr_id, comment)
            logger.info(f"Successfully posted review comment to MR {mr_id}")
            return {
                "status": "success",
                "message": f"Review completed for MR {mr_id}",
                "mr_id": mr_id
            }
        except Exception as e:
            logger.error(f"Error posting comment to MR {mr_id}: {e}")
            return {
                "status": "error",
                "message": f"Failed to post comment: {str(e)}"
            }
    
    except Exception as e:
        logger.error(f"Error reviewing MR {mr_id}: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"Internal error: {str(e)}"
        }


def build_review_prompt(custom_prompt: str, diff: str, mr_info: dict) -> str:
    """
    Build the complete prompt by combining custom prompt with PR diff.
    
    Args:
        custom_prompt: The custom review instructions
        diff: The PR diff content
        mr_info: Merge request information
    
    Returns:
        Complete prompt string
    """
    mr_title = mr_info.get("title", "N/A")
    mr_id = mr_info.get("iid", "N/A")

    prompt = f"""You are a code reviewer for a GitLab merge request.

{custom_prompt}

## Merge Request Information
- Title: {mr_title}
- MR ID: {mr_id}

## Code Changes (Diff)

{diff}

---

Please review the code changes above according to the instructions provided. Focus on table naming conventions and other validation rules. Provide your review feedback in a clear, structured format.
"""
    return prompt


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "GitLab PR Reviewer",
        "ollama_model": OLLAMA_MODEL
    }


@app.get("/health")
async def health():
    """Health check endpoint with Ollama connectivity check."""
    try:
        url = f"{OLLAMA_BASE_URL}/api/tags"
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            return {
                "status": "healthy",
                "ollama": "connected",
                "model": OLLAMA_MODEL
            }
    except Exception as e:
        logger.warning(f"Ollama health check failed: {e}")
        return {
            "status": "degraded",
            "ollama": "not_available",
            "model": OLLAMA_MODEL,
            "error": str(e)
        }


@app.post("/review")
@app.get("/review")
async def review_pr_manual(pr_url: str = Query(..., description="GitLab merge request URL")):
    """
    Manually trigger a review for a GitLab merge request by providing the PR URL.
    Supports both GET and POST methods for flexibility.
    
    Examples:
        POST /review?pr_url=https://gitlab.com/group/project/-/merge_requests/123
        GET /review?pr_url=https://gitlab.com/group/project/-/merge_requests/123
    
    Args:
        pr_url: Full GitLab merge request URL
    
    Returns:
        JSON response with review status
    """
    try:
        logger.info(f"Manual review requested for PR URL: {pr_url}")
        
        # Parse the PR URL to extract project path and MR ID
        project_path, mr_id = parse_gitlab_pr_url(pr_url)
        
        if not project_path or not mr_id:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid GitLab PR URL. Expected format: https://gitlab.com/group/project/-/merge_requests/123"
            )
        
        logger.info(f"Parsed URL - Project: {project_path}, MR ID: {mr_id}")
        
        # Initialize GitLab client with project path
        try:
            gitlab_client = GitLabClient(project_path=project_path)
        except Exception as e:
            logger.error(f"Error connecting to GitLab project {project_path}: {e}")
            raise HTTPException(
                status_code=404,
                detail=f"Project not found: {project_path}. Check project path and access token."
            )
        
        # Perform the review
        result = review_merge_request(gitlab_client, mr_id)
        
        status_code = 200 if result["status"] == "success" else 500
        return JSONResponse(
            status_code=status_code,
            content=result
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing manual review: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.post("/webhook/gitlab")
async def gitlab_webhook(
        request: Request,
        x_gitlab_token: Optional[str] = Header(None)
):
    """
    Handle GitLab webhook for merge request events.
    
    This endpoint:
    1. Receives webhook payload from GitLab
    2. Extracts merge request information and diff
    3. Calls Ollama API with custom prompt
    4. Posts review comment to GitLab PR
    """
    try:
        # Parse webhook payload
        payload = await request.json()
        logger.info(f"Received webhook: {payload.get('object_kind', 'unknown')}")

        # Handle different webhook event types
        event_type = payload.get("event_type") or payload.get("object_kind")

        # Process merge request events
        if event_type in ["merge_request", "Merge Request Hook"]:
            mr_data = payload.get("object_attributes") or payload.get("merge_request", {})
            mr_id = mr_data.get("iid")
            action = mr_data.get("action", "")

            # Only process open/update events (not close/merge)
            if action not in ["open", "update", "reopen"]:
                logger.info(f"Skipping MR {mr_id} with action: {action}")
                return JSONResponse(
                    status_code=200,
                    content={"message": f"Skipped MR {mr_id} - action: {action}"}
                )

            if not mr_id:
                raise HTTPException(status_code=400, detail="Missing merge request ID")

            logger.info(f"Processing merge request #{mr_id}")

            # Get project ID from webhook payload (preferred) or use config
            project_data = payload.get("project", {})
            project_id = project_data.get("id") or project_data.get("project_id")

            # Initialize GitLab client
            gitlab_client = GitLabClient(project_id=project_id)

            # Get merge request diff
            try:
                diff = gitlab_client.get_merge_request_diff(mr_id)
                if not diff:
                    logger.warning(f"No diff found for MR {mr_id}")
                    return JSONResponse(
                        status_code=200,
                        content={"message": f"No changes found in MR {mr_id}"}
                    )
            except Exception as e:
                logger.error(f"Error fetching diff for MR {mr_id}: {e}")
                raise HTTPException(status_code=500, detail=f"Failed to fetch MR diff: {str(e)}")

            # Use the shared review function
            mr_title = mr_data.get("title", "")
            result = review_merge_request(gitlab_client, mr_id, mr_title)
            
            status_code = 200 if result["status"] == "success" else 500
            return JSONResponse(
                status_code=status_code,
                content=result
            )

        else:
            logger.info(f"Unhandled event type: {event_type}")
            return JSONResponse(
                status_code=200,
                content={"message": f"Event type {event_type} not processed"}
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


def main():
    """Main entry point for running the webhook server."""
    import uvicorn

    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        "webhook:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        log_level="info"
    )


if __name__ == "__main__":
    main()
