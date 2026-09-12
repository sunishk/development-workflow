"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ChevronRight, FolderOpen, FolderGit2, LayoutDashboard } from "lucide-react";
import { AppHeader } from "@/components/AppChrome";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, type Project } from "@/lib/api";

export default function OpenPage() {
  const router = useRouter();
  const [projects, setProjects] = useState<Project[]>([]);
  const [name, setName] = useState("");
  const [localPath, setLocalPath] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [browsing, setBrowsing] = useState(false);

  const load = async () => {
    try {
      setProjects(await api.listProjects());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load projects");
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const browse = async () => {
    setBrowsing(true);
    setError(null);
    try {
      const result = await api.browseProject();
      setLocalPath(result.path);
      if (!name.trim()) {
        setName(result.path.split("/").filter(Boolean).pop() ?? "Project");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to select project folder");
    } finally {
      setBrowsing(false);
    }
  };

  return (
    <div className="min-h-screen">
      <AppHeader
        right={
          <Button variant="ghost" size="sm" onClick={() => router.push("/dashboard")}>
            <LayoutDashboard className="size-3.5" /> Dashboard
          </Button>
        }
      />
      <main className="mx-auto max-w-2xl px-4 py-12">
        <p className="mb-2 text-[11px] font-medium tracking-[0.16em] text-muted-foreground uppercase">01 · Workspace</p>
        <h1 className="text-3xl font-semibold tracking-tight">Open a local project</h1>
        <p className="mt-2 max-w-lg text-sm text-muted-foreground">
          Select an existing local Git project. Software Factory creates an isolated worktree so the coding agent never edits your working directory directly.
        </p>

        <div className="mt-8 rounded-xl border border-border bg-card shadow-xs">
          <div className="border-b border-border p-5">
            <div className="flex items-center gap-2 text-sm font-medium">
              <FolderGit2 className="size-4" />
              Local project
            </div>
          </div>
          <form
            className="flex flex-col gap-4 p-5"
            onSubmit={async (event) => {
              event.preventDefault();
              if (!localPath.trim()) return;
              setSaving(true);
              setError(null);
              try {
                const project = await api.createProject({
                  name: name.trim() || localPath.trim().split("/").filter(Boolean).pop() || "Project",
                  local_path: localPath.trim(),
                });
                router.push(`/board?project=${project.id}`);
              } catch (err) {
                setError(err instanceof Error ? err.message : "Unable to open local project");
              } finally {
                setSaving(false);
              }
            }}
          >
            <Field label="Project name">
              <Input placeholder="payment-service" value={name} onChange={(event) => setName(event.target.value)} />
            </Field>
            <Field label="Local project folder">
              <div className="flex gap-2">
                <Input
                  placeholder="/Users/you/Projects/payment-service"
                  value={localPath}
                  onChange={(event) => setLocalPath(event.target.value)}
                />
                <Button type="button" variant="outline" onClick={() => void browse()} disabled={browsing}>
                  <FolderOpen className="size-4" />
                  {browsing ? "Opening…" : "Browse"}
                </Button>
              </div>
            </Field>
            <p className="text-xs text-muted-foreground">
              The folder must be the root of a Git repository and should have no uncommitted changes when a development job starts.
            </p>
            <Button type="submit" disabled={saving || !localPath.trim()}>
              <FolderOpen className="size-4" />
              {saving ? "Opening…" : "Open project"}
            </Button>
            {error && <p className="text-sm text-red-700">{error}</p>}
          </form>
        </div>

        <section className="mt-10">
          <p className="mb-3 text-[11px] font-medium tracking-[0.16em] text-muted-foreground uppercase">Recent</p>
          <div className="flex flex-col gap-2">
            {projects.length === 0 && <p className="text-sm text-muted-foreground">No projects yet.</p>}
            {projects.map((project) => (
              <button
                key={project.id}
                type="button"
                onClick={() => router.push(`/board?project=${project.id}`)}
                className="group flex items-center justify-between rounded-xl border border-border bg-card px-4 py-3 text-left shadow-xs transition-colors hover:bg-muted/50"
              >
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{project.name}</span>
                    <Badge variant="outline">{project.base_branch}</Badge>
                  </div>
                  <p className="truncate font-mono text-xs text-muted-foreground">{project.local_path ?? "Legacy project — reopen locally"}</p>
                </div>
                <ChevronRight className="size-4 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
              </button>
            ))}
          </div>
        </section>
      </main>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="space-y-1.5">
      <span className="text-sm font-medium">{label}</span>
      {children}
    </label>
  );
}
