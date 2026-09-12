"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, FolderOpen, Plus, RefreshCw } from "lucide-react";
import { AppHeader } from "@/components/AppChrome";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api, type Job, type Project } from "@/lib/api";

export default function DashboardPage() {
  const router = useRouter();
  const [jobs, setJobs] = useState<Job[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    try {
      const [jobData, projectData] = await Promise.all([api.listAllJobs(), api.listProjects()]);
      setJobs(jobData);
      setProjects(projectData);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load dashboard");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const projectById = useMemo(() => new Map(projects.map((project) => [project.id, project])), [projects]);
  const running = jobs.filter((job) => ["QUEUED", "DISPATCHING", "RUNNING"].includes(job.status)).length;
  const completed = jobs.filter((job) => job.status === "COMPLETED").length;
  const failed = jobs.filter((job) => job.status === "FAILED").length;

  const openJob = (job: Job) => {
    const suffix = job.project_id ? `?project=${job.project_id}` : "";
    router.push(`/board/${job.job_id}${suffix}`);
  };

  return (
    <div className="min-h-screen">
      <AppHeader
        right={
          <>
            <Button variant="ghost" size="sm" onClick={() => void load()}>
              <RefreshCw className="size-3.5" /> Refresh
            </Button>
            <Button size="sm" onClick={() => router.push("/open")}>
              <Plus className="size-3.5" /> Open local project
            </Button>
          </>
        }
      />

      <main className="mx-auto w-full max-w-6xl px-4 py-8">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-[11px] font-medium uppercase tracking-[0.16em] text-muted-foreground">Software Factory</p>
            <h1 className="mt-1 text-3xl font-semibold tracking-tight">Workflow dashboard</h1>
            <p className="mt-2 text-sm text-muted-foreground">
              Review previous development runs, reopen a project, or start work on a local repository.
            </p>
          </div>
        </div>

        <section className="mt-7 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <MetricCard label="Total workflows" value={jobs.length} />
          <MetricCard label="Running" value={running} />
          <MetricCard label="Completed" value={completed} />
          <MetricCard label="Failed" value={failed} />
        </section>

        <section className="mt-8 rounded-xl border border-border bg-card shadow-xs">
          <div className="flex items-center justify-between border-b border-border px-5 py-4">
            <div>
              <h2 className="font-semibold">Recent workflows</h2>
              <p className="mt-0.5 text-xs text-muted-foreground">Most recently created development jobs.</p>
            </div>
          </div>

          {loading ? (
            <div className="p-6 text-sm text-muted-foreground">Loading workflows…</div>
          ) : jobs.length === 0 ? (
            <div className="p-8 text-center">
              <p className="text-sm font-medium">No workflows yet</p>
              <p className="mt-1 text-sm text-muted-foreground">Open a local project and create your first requirement.</p>
              <Button className="mt-4" onClick={() => router.push("/open")}>
                <FolderOpen className="size-4" /> Open local project
              </Button>
            </div>
          ) : (
            <div className="divide-y divide-border">
              {jobs.slice(0, 12).map((job) => {
                const project = job.project_id ? projectById.get(job.project_id) : undefined;
                return (
                  <button
                    key={job.job_id}
                    type="button"
                    onClick={() => openJob(job)}
                    className="flex w-full items-center justify-between gap-4 px-5 py-4 text-left transition-colors hover:bg-muted/40"
                  >
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="truncate font-medium">{job.title}</span>
                        <StatusBadge status={job.status} />
                        <Badge variant="outline">{job.stage}</Badge>
                      </div>
                      <p className="mt-1 truncate text-xs text-muted-foreground">
                        {project?.name ?? "Legacy project"}
                        {job.base_branch ? ` · ${job.base_branch}` : ""}
                      </p>
                    </div>
                    <ArrowRight className="size-4 shrink-0 text-muted-foreground" />
                  </button>
                );
              })}
            </div>
          )}
        </section>

        <section className="mt-8">
          <div className="mb-3 flex items-center justify-between">
            <div>
              <h2 className="font-semibold">Projects</h2>
              <p className="mt-0.5 text-xs text-muted-foreground">Previously opened local projects.</p>
            </div>
            <Button variant="outline" size="sm" onClick={() => router.push("/open")}>
              <Plus className="size-3.5" /> Open project
            </Button>
          </div>

          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {projects.map((project) => (
              <button
                key={project.id}
                type="button"
                onClick={() => router.push(`/board?project=${project.id}`)}
                className="rounded-xl border border-border bg-card p-4 text-left shadow-xs transition-colors hover:bg-muted/40"
              >
                <div className="flex items-center justify-between gap-3">
                  <span className="truncate font-medium">{project.name}</span>
                  <ArrowRight className="size-4 shrink-0 text-muted-foreground" />
                </div>
                <p className="mt-2 truncate font-mono text-xs text-muted-foreground">{project.local_path ?? "Legacy project"}</p>
                <div className="mt-3">
                  <Badge variant="outline">{project.base_branch}</Badge>
                </div>
              </button>
            ))}
          </div>
        </section>

        {error && <div className="mt-5 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">{error}</div>}
      </main>
    </div>
  );
}

function MetricCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-xl border border-border bg-card p-4 shadow-xs">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-2 text-2xl font-semibold tracking-tight">{value}</p>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const variant = status === "COMPLETED" ? "success" : status === "FAILED" ? "failed" : "queued";
  return <Badge variant={variant}>{status}</Badge>;
}
