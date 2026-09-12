"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { ArrowLeft, RefreshCw, RotateCcw } from "lucide-react";
import { AppHeader } from "@/components/AppChrome";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  api,
  type Job,
  type StageMetric,
  type WorkflowEvent,
  type WorkspaceStatus,
} from "@/lib/api";

function JobDetailsInner() {
  const params = useParams<{ id: string }>();
  const search = useSearchParams();
  const router = useRouter();
  const projectId = search.get("project");
  const jobId = params.id;
  const [job, setJob] = useState<Job | null>(null);
  const [events, setEvents] = useState<WorkflowEvent[]>([]);
  const [metrics, setMetrics] = useState<StageMetric[]>([]);
  const [workspace, setWorkspace] = useState<WorkspaceStatus | null>(null);
  const [diff, setDiff] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [retrying, setRetrying] = useState(false);

  const load = async () => {
    try {
      const [jobData, eventData, metricData] = await Promise.all([
        api.getJob(jobId),
        api.getEvents(jobId),
        api.getMetrics(jobId),
      ]);
      setJob(jobData);
      setEvents(eventData);
      setMetrics(metricData);
      setError(null);

      if (jobData.workspace_path) {
        const [statusData, diffData] = await Promise.all([
          api.getWorkspaceStatus(jobId).catch(() => null),
          api.getWorkspaceDiff(jobId).catch(() => ({ diff: "" })),
        ]);
        setWorkspace(statusData);
        setDiff(diffData.diff);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load job");
    }
  };

  useEffect(() => {
    void load();
    const timer = window.setInterval(() => void load(), 2500);
    return () => window.clearInterval(timer);
  }, [jobId]);

  const implementationSummary = useMemo(
    () => [...events].reverse().find((event) => event.event_type === "CODING_AGENT_COMPLETED")?.message ?? null,
    [events],
  );

  const validationEvents = useMemo(
    () => events.filter((event) => event.stage === "VALIDATE"),
    [events],
  );

  const back = () => router.push(projectId ? `/board?project=${projectId}` : "/open");

  if (!job && !error) {
    return <div className="p-10 text-sm text-muted-foreground">Loading job…</div>;
  }

  return (
    <div className="min-h-screen">
      <AppHeader
        left={job ? <span className="hidden truncate text-sm text-muted-foreground sm:inline">{job.title}</span> : undefined}
        right={
          <>
            <Button variant="ghost" size="sm" onClick={back}>
              <ArrowLeft className="size-3.5" /> Board
            </Button>
            <Button variant="ghost" size="sm" onClick={() => void load()}>
              <RefreshCw className="size-3.5" /> Refresh
            </Button>
          </>
        }
      />

      <main className="mx-auto grid max-w-[1400px] gap-5 px-4 py-6 lg:grid-cols-[minmax(0,1.5fr)_minmax(320px,0.7fr)]">
        <div className="space-y-5">
          {job && (
            <section className="rounded-xl border bg-card p-5 shadow-xs">
              <div className="flex flex-wrap items-center gap-2">
                <h1 className="text-xl font-semibold tracking-tight">{job.title}</h1>
                <Badge variant={job.status === "COMPLETED" ? "success" : job.status === "FAILED" ? "failed" : "queued"}>
                  {job.status}
                </Badge>
                <Badge variant="outline">{job.stage}</Badge>
              </div>
              <p className="mt-4 whitespace-pre-wrap text-sm leading-6 text-muted-foreground">{job.description}</p>
              <dl className="mt-5 grid gap-3 border-t pt-4 text-xs sm:grid-cols-2">
                <Meta label="Repository" value={job.repository_url ?? "—"} />
                <Meta label="Base branch" value={job.base_branch ?? "—"} />
                <Meta label="Workspace branch" value={job.workspace_branch ?? "Not prepared yet"} />
                <Meta label="Job ID" value={job.job_id} mono />
              </dl>
              {job.status === "FAILED" && job.error && (
                <div className="mt-4 rounded-lg border border-red-200 bg-red-50 p-3 font-mono text-xs whitespace-pre-wrap text-red-800">
                  {job.error}
                </div>
              )}
              {job.status === "FAILED" && (
                <Button
                  className="mt-4"
                  disabled={retrying}
                  onClick={async () => {
                    setRetrying(true);
                    try {
                      await api.retryJob(job.job_id);
                      await load();
                    } finally {
                      setRetrying(false);
                    }
                  }}
                >
                  <RotateCcw className="size-4" /> {retrying ? "Retrying…" : "Retry from checkpoint"}
                </Button>
              )}
            </section>
          )}

          <section className="rounded-xl border bg-card p-5 shadow-xs">
            <p className="text-[11px] font-medium tracking-[0.16em] text-muted-foreground uppercase">Implementation</p>
            <h2 className="mt-1 text-lg font-semibold">Coding agent result</h2>
            <p className="mt-3 text-sm text-muted-foreground">
              {implementationSummary ?? "The coding provider has not completed an implementation attempt yet."}
            </p>
            {workspace && (
              <div className="mt-5">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-medium">Changed files</h3>
                  <Badge variant={workspace.clean ? "outline" : "queued"}>{workspace.clean ? "Clean" : `${workspace.changed_files.length} changed`}</Badge>
                </div>
                <div className="mt-2 rounded-lg bg-muted p-3 font-mono text-xs">
                  {workspace.changed_files.length === 0
                    ? "No changes detected"
                    : workspace.changed_files.map((file) => <div key={file}>{file}</div>)}
                </div>
              </div>
            )}
            {diff && (
              <details className="mt-4">
                <summary className="cursor-pointer text-sm font-medium">View working diff</summary>
                <pre className="mt-2 max-h-[520px] overflow-auto rounded-lg bg-neutral-950 p-4 text-xs leading-5 text-neutral-100">{diff}</pre>
              </details>
            )}
          </section>

          <section className="rounded-xl border bg-card p-5 shadow-xs">
            <p className="text-[11px] font-medium tracking-[0.16em] text-muted-foreground uppercase">Validation</p>
            <h2 className="mt-1 text-lg font-semibold">Build and test attempts</h2>
            <div className="mt-4 space-y-2">
              {validationEvents.length === 0 && <p className="text-sm text-muted-foreground">Validation has not started yet.</p>}
              {validationEvents.map((event) => (
                <div key={event.id} className="rounded-lg border p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="font-mono text-xs">{event.event_type}</span>
                    {event.duration_ms != null && <span className="text-xs text-muted-foreground">{Math.round(event.duration_ms)} ms</span>}
                  </div>
                  {event.message && <pre className="mt-2 overflow-auto whitespace-pre-wrap text-xs text-muted-foreground">{event.message}</pre>}
                </div>
              ))}
            </div>
          </section>
        </div>

        <aside className="space-y-5">
          <section className="rounded-xl border bg-card p-5 shadow-xs">
            <p className="text-[11px] font-medium tracking-[0.16em] text-muted-foreground uppercase">Pipeline</p>
            <div className="mt-4 space-y-2">
              {metrics.length === 0 && <p className="text-sm text-muted-foreground">Stage timing will appear as the workflow runs.</p>}
              {metrics.map((metric) => (
                <div key={metric.stage} className="flex items-center justify-between gap-3 rounded-lg bg-muted px-3 py-2">
                  <div>
                    <p className="text-sm font-medium">{metric.stage}</p>
                    <p className="text-xs text-muted-foreground">{metric.attempts} attempt{metric.attempts === 1 ? "" : "s"}</p>
                  </div>
                  <span className="font-mono text-xs">{Math.round(metric.total_duration_ms)} ms</span>
                </div>
              ))}
            </div>
          </section>

          <section className="rounded-xl border bg-card p-5 shadow-xs">
            <p className="text-[11px] font-medium tracking-[0.16em] text-muted-foreground uppercase">Event history</p>
            <div className="mt-4 max-h-[620px] space-y-3 overflow-auto">
              {[...events].reverse().map((event) => (
                <div key={event.id} className="border-l-2 border-border pl-3">
                  <p className="font-mono text-[11px] font-medium">{event.event_type}</p>
                  <p className="text-[11px] text-muted-foreground">{new Date(event.created_at).toLocaleString()}</p>
                  {event.message && <p className="mt-1 text-xs text-muted-foreground">{event.message}</p>}
                </div>
              ))}
            </div>
          </section>
        </aside>
      </main>
      {error && <div className="fixed bottom-4 right-4 max-w-md rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800 shadow-lg">{error}</div>}
    </div>
  );
}

function Meta({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="min-w-0">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className={mono ? "truncate font-mono" : "truncate"}>{value}</dd>
    </div>
  );
}

export default function JobDetailsPage() {
  return (
    <Suspense>
      <JobDetailsInner />
    </Suspense>
  );
}
