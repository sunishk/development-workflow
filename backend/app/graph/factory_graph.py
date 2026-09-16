from time import perf_counter
from typing import Callable, TypedDict
from uuid import UUID
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from app.core.config import settings
from app.graph.test_hooks import failure_controller
from app.services.coding_agent_service import coding_agent_service
from app.services.command_service import command_service
from app.services.event_service import event_service
from app.services.repository_analysis_service import RepositoryProfile, repository_analysis_service
from app.services.repository_service import repository_service

class WorkflowState(TypedDict):
    job_id: str; title: str; description: str; workflow_name: str; stage: str; status: str
    requirements: str; tech_spec: str; tasks: list[str]; local_path: str | None; base_branch: str
    workspace_path: str | None; workspace_branch: str | None; repository_profile: dict | None
    implementation_attempts: int; validation_feedback: str | None; validation_passed: bool | None

def _run_stage(stage: str, state: WorkflowState, operation: Callable[[WorkflowState], WorkflowState]) -> WorkflowState:
    job_id=UUID(state["job_id"]); started=perf_counter(); event_service.record(job_id,f"{stage}_STARTED",stage=stage)
    try: result=operation(state)
    except Exception as exc:
        event_service.record(job_id,f"{stage}_FAILED",stage=stage,message=str(exc),duration_ms=(perf_counter()-started)*1000); raise
    event_service.record(job_id,f"{stage}_COMPLETED",stage=stage,duration_ms=(perf_counter()-started)*1000); return result

def intake(s):
    def op(x):
        if failure_controller.should_fail("INTAKE"): raise RuntimeError("Simulated failure at INTAKE")
        return {**x,"stage":"INTAKE","status":"RUNNING"}
    return _run_stage("INTAKE",s,op)
def requirements(s):
    return _run_stage("REQUIREMENTS",s,lambda x:{**x,"stage":"REQUIREMENTS","requirements":x["description"]})
def tech_spec(s):
    return _run_stage("TECH_SPEC",s,lambda x:{**x,"stage":"TECH_SPEC","tech_spec":f"Technical analysis for: {x['title']}"})
def tasks(s):
    return _run_stage("TASKS",s,lambda x:{**x,"stage":"TASKS","tasks":["Analyze the existing implementation","Implement the required change","Add or update tests"]})
def repository_preparation(s):
    def op(x):
        if failure_controller.should_fail("REPOSITORY_PREPARATION"): raise RuntimeError("Simulated failure at REPOSITORY_PREPARATION")
        if not x.get("local_path"): raise RuntimeError("Local project path is missing")
        if not x.get("workspace_branch"): raise RuntimeError("Working branch is missing")
        w=repository_service.prepare_workspace(UUID(x["job_id"]),x["local_path"],x.get("base_branch") or "main",x["workspace_branch"])
        return {**x,"stage":"REPOSITORY_PREPARATION","workspace_path":str(w.path),"workspace_branch":w.branch}
    return _run_stage("REPOSITORY_PREPARATION",s,op)
def repository_analysis(s):
    return _run_stage("REPOSITORY_ANALYSIS",s,lambda x:{**x,"stage":"REPOSITORY_ANALYSIS","repository_profile":repository_analysis_service.analyze(UUID(x["job_id"])).to_dict()})
def implement(s):
    def op(x):
        if not x.get("repository_profile"): raise RuntimeError("Repository profile is missing")
        attempt=int(x.get("implementation_attempts") or 0)+1
        coding_agent_service.implement(UUID(x["job_id"]),title=x["title"],description=x["description"],tasks=x["tasks"],profile=RepositoryProfile(**x["repository_profile"]),workflow_name=x["workflow_name"],validation_feedback=x.get("validation_feedback"))
        return {**x,"stage":"IMPLEMENT","implementation_attempts":attempt,"validation_passed":None}
    return _run_stage("IMPLEMENT",s,op)
def validate(s):
    def op(x):
        p=repository_analysis_service.analyze(UUID(x["job_id"])); commands=[]
        if settings.run_install_before_validation and p.install_command: commands.append(p.install_command)
        if p.test_command: commands.append(p.test_command)
        if p.build_command: commands.append(p.build_command)
        if not commands: raise RuntimeError("No validation command could be detected for this repository")
        failures=[]
        for command in commands:
            r=command_service.run(UUID(x["job_id"]),command)
            if not r.succeeded:
                failures.append(f"$ {' '.join(command)}\n{r.stdout[-3000:]}\n{r.stderr[-3000:]}"); break
        if failures:
            feedback="\n".join(failures); attempts=int(x.get("implementation_attempts") or 0)
            if attempts>=settings.max_implementation_attempts: raise RuntimeError(f"Validation failed after {attempts} implementation attempts:\n{feedback}")
            return {**x,"stage":"VALIDATE","repository_profile":p.to_dict(),"validation_feedback":feedback,"validation_passed":False}
        return {**x,"stage":"VALIDATE","repository_profile":p.to_dict(),"validation_feedback":None,"validation_passed":True,"status":"COMPLETED"}
    return _run_stage("VALIDATE",s,op)
def _after_validate(s): return "end" if s.get("validation_passed") else "implement"
def build_graph(checkpointer: BaseCheckpointSaver):
    g=StateGraph(WorkflowState)
    for n,f in [("intake",intake),("requirements",requirements),("tech_spec",tech_spec),("tasks",tasks),("repository_preparation",repository_preparation),("repository_analysis",repository_analysis),("implement",implement),("validate",validate)]: g.add_node(n,f)
    g.add_edge(START,"intake"); g.add_edge("intake","requirements"); g.add_edge("requirements","tech_spec"); g.add_edge("tech_spec","tasks"); g.add_edge("tasks","repository_preparation"); g.add_edge("repository_preparation","repository_analysis"); g.add_edge("repository_analysis","implement"); g.add_edge("implement","validate"); g.add_conditional_edges("validate",_after_validate,{"implement":"implement","end":END})
    return g.compile(checkpointer=checkpointer)
