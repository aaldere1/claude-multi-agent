#!/usr/bin/env python3
"""
FastAPI server for the Multi-Agent Orchestrator.

Run with: uvicorn server:app --reload
Or: python server.py
"""

import os
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from orchestrator import Orchestrator, load_file_context

load_dotenv()

app = FastAPI(
    title="Claude Multi-Agent Orchestrator",
    description="API for autonomous code development and review",
    version="0.1.0"
)

# CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory task storage (use Redis/DB in production)
tasks = {}


class TaskRequest(BaseModel):
    task: str
    files: Optional[list[str]] = None
    context_type: str = "general"
    max_iterations: int = 5


class TaskResponse(BaseModel):
    task_id: str
    status: str
    message: str


class TaskResult(BaseModel):
    task_id: str
    status: str
    success: Optional[bool] = None
    iterations: Optional[int] = None
    final_code: Optional[str] = None
    note: Optional[str] = None


def run_orchestrator_task(task_id: str, request: TaskRequest):
    """Background task to run the orchestrator."""
    try:
        tasks[task_id]["status"] = "running"

        # Load file context
        file_context = None
        if request.files:
            file_context = load_file_context(request.files)

        # Run orchestrator
        orchestrator = Orchestrator(
            context_type=request.context_type,
            verbose=False
        )
        result = orchestrator.run(
            task=request.task,
            file_context=file_context,
            max_iterations=request.max_iterations
        )

        tasks[task_id].update({
            "status": "completed",
            "success": result["success"],
            "iterations": result["iterations"],
            "final_code": result["final_code"],
            "note": result.get("note")
        })

    except Exception as e:
        tasks[task_id].update({
            "status": "failed",
            "note": str(e)
        })


@app.get("/")
def root():
    return {"status": "ok", "service": "Claude Multi-Agent Orchestrator"}


@app.post("/api/orchestrate", response_model=TaskResponse)
def start_orchestration(request: TaskRequest, background_tasks: BackgroundTasks):
    """
    Start an autonomous development-review loop.
    Returns immediately with a task_id to poll for results.
    """
    import uuid
    task_id = str(uuid.uuid4())[:8]

    tasks[task_id] = {
        "status": "queued",
        "request": request.model_dump()
    }

    background_tasks.add_task(run_orchestrator_task, task_id, request)

    return TaskResponse(
        task_id=task_id,
        status="queued",
        message="Task queued. Poll /api/task/{task_id} for results."
    )


@app.post("/api/orchestrate/sync", response_model=TaskResult)
def orchestrate_sync(request: TaskRequest):
    """
    Run orchestration synchronously (blocks until complete).
    Use for short tasks or when you need immediate results.
    """
    # Load file context
    file_context = None
    if request.files:
        file_context = load_file_context(request.files)

    # Run orchestrator
    orchestrator = Orchestrator(
        context_type=request.context_type,
        verbose=False
    )
    result = orchestrator.run(
        task=request.task,
        file_context=file_context,
        max_iterations=request.max_iterations
    )

    return TaskResult(
        task_id="sync",
        status="completed",
        success=result["success"],
        iterations=result["iterations"],
        final_code=result["final_code"],
        note=result.get("note")
    )


@app.get("/api/task/{task_id}", response_model=TaskResult)
def get_task_status(task_id: str):
    """Get the status and result of a task."""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    task = tasks[task_id]
    return TaskResult(
        task_id=task_id,
        status=task["status"],
        success=task.get("success"),
        iterations=task.get("iterations"),
        final_code=task.get("final_code"),
        note=task.get("note")
    )


@app.get("/api/tasks")
def list_tasks():
    """List all tasks and their statuses."""
    return {
        task_id: {"status": task["status"]}
        for task_id, task in tasks.items()
    }


if __name__ == "__main__":
    import uvicorn
    host = os.getenv("SERVER_HOST", "127.0.0.1")
    port = int(os.getenv("SERVER_PORT", "8000"))
    uvicorn.run(app, host=host, port=port)
