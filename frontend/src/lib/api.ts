export type Project = { id:string; name:string; local_path:string|null; base_branch:string };
export type Job = { job_id:string; project_id:string|null; title:string; description:string; workflow_name:string|null; status:string; stage:string; error:string|null; local_path:string|null; base_branch:string|null; workspace_path:string|null; workspace_branch:string|null };
export type WorkflowEvent = { id:number; event_type:string; stage:string|null; message:string|null; worker_id:string|null; duration_ms:number|null; created_at:string };
export type JobStreamMessage = {kind:"snapshot";jobs:Job[]}|{kind:"job";job:Job;event:WorkflowEvent};
export type StageMetric = { stage:string; attempts:number; completed_attempts:number; failed_attempts:number; total_duration_ms:number; last_duration_ms:number|null };
export type CodingProviderStatus = { provider:string; available:boolean; executable?:string|null; model?:string|null; message:string };
export type WorkspaceStatus = { branch:string; changed_files:string[]; clean:boolean };
const API_BASE_URL=process.env.NEXT_PUBLIC_API_BASE_URL??"http://localhost:8000/api";
async function request<T>(path:string,init?:RequestInit):Promise<T>{const response=await fetch(`${API_BASE_URL}${path}`,{...init,headers:{"Content-Type":"application/json",...(init?.headers??{})},cache:"no-store"});if(!response.ok){let detail=`${response.status} ${response.statusText}`;try{const body=await response.json() as {detail?:string};detail=body.detail??detail}catch{}throw new Error(detail)}return await response.json() as T}
export const api={
 listProjects:()=>request<Project[]>("/projects"), getProject:(id:string)=>request<Project>(`/projects/${id}`),
 browseProject:()=>request<{path:string}>("/projects/browse",{method:"POST"}),
 createProject:(input:{name:string;local_path:string})=>request<Project>("/projects",{method:"POST",body:JSON.stringify(input)}),
 listJobs:(id:string)=>request<Job[]>(`/jobs?project_id=${encodeURIComponent(id)}`), listAllJobs:()=>request<Job[]>("/jobs"),
 jobsStreamUrl:(id:string)=>`${API_BASE_URL}/jobs/stream?project_id=${encodeURIComponent(id)}`,
 createJob:(input:{project_id:string;title:string;description:string;working_branch:string;workflow_name:string})=>request<Job>("/jobs",{method:"POST",body:JSON.stringify(input)}),
 getJob:(id:string)=>request<Job>(`/jobs/${id}`), getEvents:(id:string)=>request<WorkflowEvent[]>(`/jobs/${id}/events`),
 getMetrics:(id:string)=>request<StageMetric[]>(`/jobs/${id}/metrics`), getWorkspaceStatus:(id:string)=>request<WorkspaceStatus>(`/jobs/${id}/workspace/status`),
 getWorkspaceDiff:(id:string)=>request<{diff:string}>(`/jobs/${id}/workspace/diff`), retryJob:(id:string)=>request<Job>(`/jobs/${id}/retry`,{method:"POST"}),
 getCodingProviderStatus:()=>request<CodingProviderStatus>("/coding-provider/status")};
