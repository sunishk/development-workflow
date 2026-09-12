"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { FolderGit2, Plus, RefreshCw, X } from "lucide-react";
import { AppHeader } from "@/components/AppChrome";
import { Kanban } from "@/components/Kanban";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
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
  const [workingBranch, setWorkingBranch] = useState("");
  const [creating, setCreating] = useState(false);
  const [showCreateForm, setShowCreateForm] = useState(false);
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

  const resetCreateForm = () => {
    setTitle("");
    setDescription("");
    setWorkingBranch("");
    setShowCreateForm(false);
  };

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
        {!showCreateForm ? (
          <div className="flex items-center justify-between rounded-xl border border-border bg-card px-4 py-3 shadow-xs">
            <div>
              <p className="text-sm font-medium">Create development job</p>
              <p className="mt-0.5 text-xs text-muted-foreground">
                Describe the requirement for {project?.name ?? "this repository"}; the workflow will implement and validate it.
              </p>
            </div>
            <Button type="button" onClick={() => setShowCreateForm(true)}>
              <Plus className="size-4" /> New requirement
            </Button>
          </div>
        ) : (
          <form
            className="rounded-xl border border-border bg-card p-5 shadow-xs"
            onSubmit={async (event) => {
              event.preventDefault();
              if (!title.trim() || !description.trim() || !workingBranch.trim()) return;
              setCreating(true);
              setError(null);
              try {
                await api.createJob({
                  project_id: projectId,
                  title: title.trim(),
                  description: description.trim(),
                  working_branch: workingBranch.trim(),
                });
                resetCreateForm();
                await load();
              } catch (err) {
                setError(err instanceof Error ? err.message : "Unable to create job");
              } finally {
                setCreating(false);
              }
            }}
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-sm font-semibold">Create development job</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  Repository: <span className="font-medium text-foreground">{project?.name ?? "Loading…"}</span>
                  {project?.base_branch ? ` · base ${project.base_branch}` : ""}
                </p>
              </div>
              <Button type="button" variant="ghost" size="sm" onClick={resetCreateForm} disabled={creating}>
                <X className="size-4" /> Cancel
              </Button>
            </div>

            <div className="mt-5 grid gap-4">
              <label className="grid gap-1.5">
                <span className="text-sm font-medium">Title *</span>
                <Input
                  placeholder="Add validation for external payments"
                  value={title}
                  onChange={(event) => setTitle(event.target.value)}
                  autoFocus
                />
              </label>

              <label className="grid gap-1.5">
                <span className="text-sm font-medium">Working branch *</span>
                <Input
                  placeholder="feature/payment-validation"
                  value={workingBranch}
                  onChange={(event) => setWorkingBranch(event.target.value)}
                  autoCapitalize="none"
                  autoCorrect="off"
                  spellCheck={false}
                />
                <span className="text-xs text-muted-foreground">
                  A new branch will be created from {project?.base_branch ?? "the project base branch"}. Existing branch names are not reused automatically.
                </span>
              </label>

              <label className="grid gap-1.5">
                <span className="text-sm font-medium">Requirement *</span>
                <Textarea
                  placeholder={
                    "Describe the change in detail. Include expected behavior, constraints, and acceptance criteria.\n\nExample:\n- transactionId must be mandatory for external payments\n- Return HTTP 400 when missing\n- Existing internal payment flow must remain unchanged\n- Add or update automated tests"
                  }
                  value={description}
                  onChange={(event) => setDescription(event.target.value)}
                  rows={10}
                />
                <span className="text-xs text-muted-foreground">
                  Paste the full story or requirement here. Multi-line acceptance criteria are supported.
                </span>
              </label>
            </div>

            <div className="mt-5 flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={resetCreateForm} disabled={creating}>
                Cancel
              </Button>
              <Button type="submit" disabled={creating || !title.trim() || !workingBranch.trim() || !description.trim()}>
                <Plus className="size-4" /> {creating ? "Starting…" : "Start development"}
              </Button>
            </div>
          </form>
        )}
        {error && <p className="mt-3 text-sm text-red-700">{error}</p>}
      </div>

      {jobs.length === 0 ? (
        <div className="mx-auto max-w-md px-4 py-24 text-center">
          <p className="text-sm font-medium">No jobs on the line</p>
          <p className="mt-1 text-sm text-muted-foreground">
            Add a requirement to start the Python implementation and validation workflow.
          </p>
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
