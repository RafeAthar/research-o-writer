"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import type { Project, StyleProfile } from "@/lib/types";

export default function StylePage({ params }: { params: { id: string } }) {
  const projectId = Number(params.id);
  const [project, setProject] = useState<Project | null>(null);
  const [profile, setProfile] = useState<StyleProfile | null>(null);
  const [samples, setSamples] = useState<string[]>([""]);
  const [profileMd, setProfileMd] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [generating, setGenerating] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const p = await api<Project>(`/api/v1/projects/${projectId}`);
        setProject(p);
        const sp = await api<StyleProfile | null>(
          `/api/v1/projects/${projectId}/style`,
        );
        if (sp) {
          setProfile(sp);
          setSamples(sp.samples.length ? sp.samples : [""]);
          setProfileMd(sp.profile_md ?? "");
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      }
    })();
  }, [projectId]);

  const save = async () => {
    setSaving(true);
    setError(null);
    try {
      const sp = await api<StyleProfile>(
        `/api/v1/projects/${projectId}/style`,
        {
          method: "PUT",
          body: JSON.stringify({
            name: profile?.name ?? "default",
            samples: samples.map((s) => s.trim()).filter(Boolean),
            profile_md: profileMd.trim() ? profileMd : null,
          }),
        },
      );
      setProfile(sp);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  };

  const generate = async () => {
    setGenerating(true);
    setError(null);
    try {
      // Save samples first so the backend has them.
      await save();
      const sp = await api<StyleProfile>(
        `/api/v1/projects/${projectId}/style/generate`,
        { method: "POST" },
      );
      setProfile(sp);
      setProfileMd(sp.profile_md ?? "");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setGenerating(false);
    }
  };

  const remove = async () => {
    if (!confirm("Remove the style profile for this project?")) return;
    try {
      await api<void>(`/api/v1/projects/${projectId}/style`, {
        method: "DELETE",
      });
      setProfile(null);
      setProfileMd("");
      setSamples([""]);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  if (!project)
    return <div className="p-6 text-sm text-neutral-500">Loading…</div>;

  return (
    <div className="mx-auto max-w-3xl p-6">
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-xl font-semibold">{project.title} — style memory</h1>
        <Link
          href={`/projects/${projectId}`}
          className="text-sm text-blue-600 hover:underline"
        >
          ← back to project
        </Link>
      </div>
      <p className="mb-4 text-sm text-neutral-600 dark:text-neutral-400">
        Paste 1–5 representative samples of your past writing (a chapter, an
        essay, a thread). Generate a style profile from them and we'll inject
        it into chats scoped to this project so drafts mimic your voice.
      </p>
      {error && (
        <div className="mb-3 rounded border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </div>
      )}

      <h2 className="mb-2 mt-6 text-sm font-semibold uppercase tracking-wide text-neutral-500">
        Samples
      </h2>
      {samples.map((s, i) => (
        <div key={i} className="mb-3 flex gap-2">
          <textarea
            value={s}
            onChange={(e) =>
              setSamples((arr) =>
                arr.map((x, j) => (j === i ? e.target.value : x)),
              )
            }
            placeholder={`Sample ${i + 1}…`}
            rows={6}
            className="flex-1 rounded border border-neutral-300 p-2 text-sm dark:border-neutral-700 dark:bg-neutral-900"
          />
          <button
            onClick={() =>
              setSamples((arr) =>
                arr.length === 1 ? [""] : arr.filter((_, j) => j !== i),
              )
            }
            className="self-start rounded border border-neutral-300 px-2 py-1 text-xs hover:bg-neutral-100 dark:border-neutral-700 dark:hover:bg-neutral-800"
          >
            Remove
          </button>
        </div>
      ))}
      <button
        onClick={() => setSamples((arr) => [...arr, ""])}
        className="mb-4 rounded border border-neutral-300 px-2 py-1 text-xs hover:bg-neutral-100 dark:border-neutral-700 dark:hover:bg-neutral-800"
      >
        + Add sample
      </button>

      <h2 className="mb-2 mt-6 text-sm font-semibold uppercase tracking-wide text-neutral-500">
        Profile
      </h2>
      <textarea
        value={profileMd}
        onChange={(e) => setProfileMd(e.target.value)}
        rows={10}
        placeholder="Generated profile will appear here, or write one by hand."
        className="w-full rounded border border-neutral-300 p-2 font-mono text-xs dark:border-neutral-700 dark:bg-neutral-900"
      />

      <div className="mt-4 flex flex-wrap gap-2">
        <button
          onClick={save}
          disabled={saving}
          className="rounded bg-neutral-800 px-3 py-1 text-sm text-white hover:bg-neutral-900 disabled:opacity-50 dark:bg-neutral-200 dark:text-neutral-900"
        >
          {saving ? "Saving…" : "Save"}
        </button>
        <button
          onClick={generate}
          disabled={generating || saving}
          className="rounded bg-blue-600 px-3 py-1 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
          title="Save samples and run the LLM style-distillation pass"
        >
          {generating ? "Generating…" : "Generate from samples"}
        </button>
        {profile && (
          <button
            onClick={remove}
            className="rounded border border-red-300 px-3 py-1 text-sm text-red-700 hover:bg-red-50"
          >
            Delete profile
          </button>
        )}
      </div>
    </div>
  );
}
