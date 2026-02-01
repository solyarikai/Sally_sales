"""API endpoint to serve tasks from state/tasks.md file."""
import os
import re
from fastapi import APIRouter
from typing import List, Optional
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tasks", tags=["tasks"])


class SubTask(BaseModel):
    text: str
    completed: bool


class Task(BaseModel):
    id: int
    title: str
    description: str
    priority: str  # immediate, high, medium, low
    status: str  # completed, in-progress, pending
    subtasks: List[SubTask]


class TasksResponse(BaseModel):
    tasks: List[Task]
    total: int
    completed: int
    pending: int
    total_subtasks: int
    completed_subtasks: int


def parse_tasks_md(content: str) -> List[Task]:
    """Parse tasks.md content into structured Task objects."""
    tasks = []
    current_priority = "medium"
    current_task = None
    task_id = 0
    
    lines = content.split('\n')
    i = 0
    
    while i < len(lines):
        line = lines[i]
        
        # Detect priority sections
        if line.startswith('## Priority:'):
            priority_match = re.search(r'Priority:\s*(\w+)', line, re.IGNORECASE)
            if priority_match:
                current_priority = priority_match.group(1).lower()
        
        # Detect task headers (### Task N: Title or ### Title)
        elif line.startswith('### '):
            # Save previous task if exists
            if current_task:
                tasks.append(current_task)
            
            # Parse task title
            title_match = re.match(r'### Task (\d+):\s*(.+)', line)
            if title_match:
                task_id = int(title_match.group(1))
                title = title_match.group(2).strip()
            else:
                task_id += 1
                title = line[4:].strip()
            
            # Check if marked complete in title
            is_complete = '✅' in line or 'COMPLETE' in line.upper()
            
            # Remove markers from title
            title = re.sub(r'\s*✅.*', '', title).strip()
            title = re.sub(r'\s*\(.*?\)', '', title).strip()
            
            current_task = Task(
                id=task_id,
                title=title,
                description='',
                priority=current_priority,
                status='completed' if is_complete else 'pending',
                subtasks=[]
            )
        
        # Parse description (line after task header, before subtasks)
        elif current_task and not line.startswith('-') and not line.startswith('#') and line.strip() and not current_task.subtasks:
            if not current_task.description:
                current_task.description = line.strip()
        
        # Parse subtasks (lines starting with - [ ] or - [x])
        elif current_task and line.strip().startswith('- ['):
            checkbox_match = re.match(r'- \[([ xX])\]\s*(.+)', line.strip())
            if checkbox_match:
                is_checked = checkbox_match.group(1).lower() == 'x'
                subtask_text = checkbox_match.group(2)
                # Remove trailing markers like ✅ or dates
                subtask_text = re.sub(r'\s*✅.*', '', subtask_text).strip()
                
                current_task.subtasks.append(SubTask(
                    text=subtask_text,
                    completed=is_checked
                ))
        
        i += 1
    
    # Add last task
    if current_task:
        tasks.append(current_task)
    
    # Update task status based on subtasks
    for task in tasks:
        if task.subtasks:
            completed_count = sum(1 for s in task.subtasks if s.completed)
            if completed_count == len(task.subtasks):
                task.status = 'completed'
            elif completed_count > 0:
                task.status = 'in-progress'
            else:
                task.status = 'pending'
    
    return tasks


@router.get("", response_model=TasksResponse)
async def get_tasks():
    """Get all tasks from state/tasks.md file."""
    
    # Try multiple paths to find tasks.md
    possible_paths = [
        '/app/state/tasks.md',          # Inside Docker container
        'state/tasks.md',                # Relative path
        '../state/tasks.md',             # From backend dir
        '/home/leadokol/magnum-opus-project/repo/state/tasks.md',  # Absolute path
    ]
    
    content = None
    for path in possible_paths:
        try:
            if os.path.exists(path):
                with open(path, 'r') as f:
                    content = f.read()
                logger.info(f"Loaded tasks from: {path}")
                break
        except Exception as e:
            logger.debug(f"Could not read {path}: {e}")
    
    if not content:
        logger.warning("Could not find tasks.md file")
        return TasksResponse(
            tasks=[],
            total=0,
            completed=0,
            pending=0,
            total_subtasks=0,
            completed_subtasks=0
        )
    
    tasks = parse_tasks_md(content)
    
    # Calculate stats
    total = len(tasks)
    completed = sum(1 for t in tasks if t.status == 'completed')
    pending = total - completed
    total_subtasks = sum(len(t.subtasks) for t in tasks)
    completed_subtasks = sum(sum(1 for s in t.subtasks if s.completed) for t in tasks)
    
    return TasksResponse(
        tasks=tasks,
        total=total,
        completed=completed,
        pending=pending,
        total_subtasks=total_subtasks,
        completed_subtasks=completed_subtasks
    )
