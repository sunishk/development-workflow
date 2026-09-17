"use client";

import { useRouter } from "next/navigation";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { Job } from "@/lib/api";

const LANES = [
  { id: "intake", label: "Intake", n: "00" },
  { id: "requirements", label: "Requirements", n: "01" },
  { id: "tech_spec", label: "Tech spec", n: "02" },
  { id: "tasks", label: "Tasks", n: "03" },
  { id: "repository", label: "Repository", n: "04" },
  { id: "implementation", label: "Implementation", n: "05" },
  { id: "validation", label: "Validation", n: "06" },
] as const;

type LaneId = (typeof LANES)[number]["id"];

function laneFor(job: Job): LaneId {
  switch (job.stage) {
    case "CREATED":
    case "INTAKE":
      return "intake";
    case "REQUIREMENTS":
      return "requirements";
    case "TECH_SPEC":
      return "tech_spec";
    case "TASKS":
      return "tasks";
    case "REPOSITORY_PREPARATION":
    case "REPOSITORY_ANALYSIS":
      return "repository";
    case "IMPLEMENT":
      return "implementation";
    case "VALIDATE":
      return "validation";
    default:
      return "intake";
  }
}

export function Kanban({ projectId, jobs }: { projectId: string; jobs: Job[] }) {
  const router = useRouter();
  // This is an execution board, not the historical dashboard. Successful
  // terminal jobs remain available on the landing dashboard/job details but
  // must not appear as if they are still executing in their last stage.
  const executionJobs = jobs.filter((job) => job.status !== "COMPLETED");

  return (
    <div className="grid grid-cols-1 gap-3 overflow-x-auto p-4 md:grid-cols-3 xl:grid-cols-7">
      {LANES.map((lane) => {
        const laneJobs = executionJobs.filter((job) => laneFor(job) === lane.id);
        return (
          <section key={lane.id} className="flex min-h-[62vh] min-w-[220px] flex-col rounded-xl bg-muted/50 p-2">
            <header className="flex items-baseline justify-between px-2 py-2">
              <h3 className="text-[11px] font-medium tracking-[0.14em] text-muted-foreground uppercase">
                <span className="mr-1.5 font-mono text-[10px] opacity-60">{lane.n}</span>
                {lane.label}
              </h3>
              <span className="font-mono text-[11px] text-muted-foreground">{laneJobs.length}</span>
            </header>
            <div className="flex flex-1 flex-col gap-2">
              {laneJobs.map((job) => {
                const running = ["QUEUED", "DISPATCHING", "RUNNING"].includes(job.status);
                const failed = job.status === "FAILED";
                return (
                  <button
                    key={job.job_id}
                    type="button"
                    onClick={() => router.push(`/board/${job.job_id}?project=${projectId}`)}
                    className={cn(
                      "rounded-lg border bg-card p-3 text-left shadow-xs transition-all hover:-translate-y-px hover:shadow-sm",
                      running && "border-sky-200 ring-1 ring-sky-100",
                      failed && "border-red-200",
                    )}
                  >
                    <p className="line-clamp-3 text-sm font-medium leading-snug">{job.title}</p>
                    <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
                      {running && (
                        <Badge variant="queued">
                          <span className="mr-1 size-1.5 animate-pulse rounded-full bg-sky-600" />
                          {job.status === "QUEUED" ? "Queued" : `Running · ${job.stage}`}
                        </Badge>
                      )}
                      {failed && <Badge variant="failed">Failed · {job.stage}</Badge>}
                      {job.base_branch && <Badge variant="outline">{job.base_branch}</Badge>}
                    </div>
                    {failed && job.error && (
                      <p className="mt-2 line-clamp-3 font-mono text-[11px] leading-snug text-red-800">
                        {job.error.split("\n")[0]}
                      </p>
                    )}
                    {job.workspace_branch && (
                      <p className="mt-2 truncate font-mono text-[11px] text-muted-foreground">{job.workspace_branch}</p>
                    )}
                  </button>
                );
              })}
            </div>
          </section>
        );
      })}
    </div>
  );
}
