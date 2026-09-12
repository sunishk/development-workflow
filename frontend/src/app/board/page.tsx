"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { FolderGit2, Plus, RefreshCw } from "lucide-react";
import { AppHeader } from "@/components/AppChrome";
import { Kanban } from "@/components/Kanban";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, type CodingProviderStatus, type Job, type Project } from "@/lib/api";

function BoardInner() {
  const params = useSearchParams();
  const router = useRouter();
  const projectId = params.get("project");
  const [project, setProject] = useState<Project | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [provider, setProvider] = useState<CodingProviderStatus | null>(null);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    if (!projectId) return;
    try {
      const [projectData, jobsData, providerData] = await Promise.all([
        api.getProject(projectId),
        api.listJobs(projectId),
        api.getCodingProviderStatus().catch(() => null),
      ]);
      setProject(projectData);
      setJobs(jobsData);
      setProvider(providerData);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load board");
    }
  };

  useEffect(() => {
    if (!projectId) {
      router.replace("/open");
      return;
    }
    void load();
    const timer = window.setInterval(() => void load(), 3000);
    return () => window.clearInterval(timer);
  }, [projectId]);

  if (!projectId) return null;

  return (
    <div className="flex min-h-screen flex-col">
      <AppHeader
        left={<span className="hidden truncate text-sm text-muted-foreground sm:inline">{project?.name}</span>}
        right={
          <>
            {provider && (
              <Badge variant={provider.available ? "success" : "failed"}>
                {provider.provider} · {provider.available ? "ready" : "unavailable"}
              </Badge>
            )}
            <Button variant="ghost" size="sm" onClick={() => void load()}>
              <RefreshCw className="size-3.5" /> Refresh
            </Button>
            <Button variant="ghost" size="sm" onClick={() => router.push("/open")}>
              <FolderGit2 className="size-3.5" /> Repos
            </Button>
          </>
        }
      />

      <div className="mx-auto w-full max-w-[1600px] px-4 pt-5">
        <form
          className="flex flex-col gap-2 rounded-xl border border-border bg-card p-2 shadow-xs sm:flex-row sm:items-center"
          onSubmit={async (event) => {
            event.preventDefault();
            if (!title.trim() || !description.trim()) return;
            setCreating(true);
            setError(null);
            try {
              await api.createJob({ project_id: projectId, title: title.trim(), description: description.trim() });
              setTitle("");
              setDescription("");
              await load();
            } catch (err) {
              setError(err instanceof Error ? err.message : "Unable to create job");
            } finally {
              setCreating(false);
            }
          }}
        >
          <Input
            className="border-0 shadow-none focus:ring-0"
            placeholder="New job title"
            value={title}
            onChange={(event) => setTitle(event.target.value)}
          />
          <Input
            className="border-0 shadow-none focus:ring-0"
            placeholder="Brief requirements…"
            value={description}
            onChange={(event) => setDescription(event.target.value)}
          />
          <Button type="submit" disabled={creating || !title.trim() || !description.trim()} className="shrink-0">
            <Plus className="size-4" /> {creating ? "Creating…" : "Create job"}
          </Button>
        </form>
        {error && <p className="mt-3 text-sm text-red-700">{error}</p>}
      </div>

      {jobs.length === 0 ? (
        <div className="mx-auto max-w-md px-4 py-24 text-center">
          <p className="text-sm font-medium">No jobs on the line</p>
          <p className="mt-1 text-sm text-muted-foreground">Create a requirement above to start the Python workflow.</p>
        </div>
      ) : (
        <Kanban projectId={projectId} jobs={jobs} />
      )}
    </div>
  );
}

export default function BoardPage() {
  return (
    <Suspense>
      <BoardInner />
    </Suspense>
  );
}
