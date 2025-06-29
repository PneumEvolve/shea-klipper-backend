from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from database import get_db
from models import Project, ProjectTask, User
from schemas import ProjectCreate, Project as ProjectSchema, ProjectTaskCreate, ProjectTask as ProjectTaskSchema
from routers.auth import get_current_user_dependency

router = APIRouter(prefix="/projects", tags=["Projects"])

# --- Projects ---

@router.get("/", response_model=List[ProjectSchema])
def get_projects(db: Session = Depends(get_db), user: User = Depends(get_current_user_dependency)):
    return db.query(Project).filter(Project.user_id == user.id).all()

@router.get("/{project_id}", response_model=ProjectSchema)
def get_project(project_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user_dependency)):
    project = db.query(Project).filter(Project.id == project_id, Project.user_id == user.id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project

@router.post("/", response_model=ProjectSchema)
def create_project(project: ProjectCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    db_project = Project(user_id=user.id, **project.dict())
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    return db_project

@router.put("/{project_id}", response_model=ProjectSchema)
def update_project(project_id: UUID, project_data: ProjectCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user_dependency)):
    project = db.query(Project).filter(Project.id == project_id, Project.user_id == user.id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    for key, value in project_data.dict().items():
        setattr(project, key, value)
    db.commit()
    db.refresh(project)
    return project

@router.delete("/{project_id}")
def delete_project(project_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    project = db.query(Project).filter(Project.id == project_id, Project.user_id == user.id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    db.delete(project)
    db.commit()
    return {"message": "Project deleted successfully"}

# --- Tasks ---

@router.post("/{project_id}/tasks", response_model=ProjectTaskSchema)
def add_task(project_id: UUID, task: ProjectTaskCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user_dependency)):
    project = db.query(Project).filter(Project.id == project_id, Project.user_id == user.id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    db_task = ProjectTask(project_id=project_id, **task.dict())
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    return db_task

@router.put("/tasks/{task_id}", response_model=ProjectTaskSchema)
def update_task(task_id: UUID, task_data: ProjectTaskCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    task = db.query(ProjectTask).join(Project).filter(ProjectTask.id == task_id, Project.user_id == user.id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    for key, value in task_data.dict().items():
        setattr(task, key, value)
    db.commit()
    db.refresh(task)
    return task

@router.delete("/tasks/{task_id}")
def delete_task(task_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user_dependency)):
    task = db.query(ProjectTask).join(Project).filter(ProjectTask.id == task_id, Project.user_id == user.id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    db.delete(task)
    db.commit()
    return {"message": "Task deleted successfully"}