'use client';

import { useMemo, useState } from 'react';
import { supabase } from '@/lib/supabase';

type RenderMode = 'auto' | 'editable' | 'image_fallback' | 'hybrid_overlay';

type ReviewSlide = {
  page_id: number;
  archetype: string;
  width: number;
  height: number;
  element_count: number;
  text_count: number;
  image_count: number;
  table_count: number;
  default_render_mode: RenderMode;
  current_render_mode: RenderMode;
  confidence: {
    archetype: number;
    render_mode: number;
    semantic_roles: number;
  };
};

type ReviewPayload = {
  request_id: string;
  filename: string;
  output_folder: string;
  slide_count: number;
  slides: ReviewSlide[];
};

type GeneratePayload = {
  request_id: string;
  status: string;
  status_url: string;
  overrides_applied: number;
};

type JobStatusPayload = {
  request_id: string;
  filename: string;
  review_status?: {
    status: string;
    stage: string;
    message: string;
    error?: string | null;
  };
  generate_status?: {
    status: string;
    stage: string;
    message: string;
    error?: string | null;
    download_url?: string;
    overrides_applied?: number;
  };
  review?: ReviewPayload | null;
  download_url?: string | null;
};

const API_BASE = process.env.NEXT_PUBLIC_BACKEND_API_BASE ?? 'http://127.0.0.1:8001';
const POLL_INTERVAL_MS = 1200;
const RENDER_MODE_OPTIONS: Array<{ value: RenderMode; label: string }> = [
  { value: 'auto', label: 'Auto' },
  { value: 'editable', label: 'Editable' },
  { value: 'image_fallback', label: 'Image Fallback' },
  { value: 'hybrid_overlay', label: 'Hybrid Overlay' },
];

export default function Home() {
  const [file, setFile] = useState<File | null>(null);
  const [status, setStatus] = useState<string>('');
  const [uploading, setUploading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [review, setReview] = useState<ReviewPayload | null>(null);
  const [overrides, setOverrides] = useState<Record<number, RenderMode>>({});
  const [downloadUrl, setDownloadUrl] = useState<string>('');
  const [error, setError] = useState<string>('');

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      setFile(e.target.files[0]);
    }
  };

  const sleep = (ms: number) => new Promise((resolve) => window.setTimeout(resolve, ms));

  const fetchJobStatus = async (requestId: string): Promise<JobStatusPayload> => {
    const response = await fetch(`${API_BASE}/status/${requestId}`);
    if (!response.ok) {
      let errorMessage = 'Failed to fetch job status';
      try {
        const payload = (await response.json()) as { detail?: string; error?: string };
        errorMessage = payload.detail || payload.error || errorMessage;
      } catch {
        const text = await response.text();
        if (text) {
          errorMessage = text;
        }
      }
      throw new Error(errorMessage);
    }
    return response.json();
  };

  const syncReviewState = (reviewPayload: ReviewPayload) => {
    setReview(reviewPayload);
    setOverrides(
      Object.fromEntries(
        reviewPayload.slides.map((slide) => [slide.page_id, slide.current_render_mode])
      ) as Record<number, RenderMode>
    );
  };

  const pollReviewUntilReady = async (requestId: string) => {
    while (true) {
      const job = await fetchJobStatus(requestId);
      const reviewStatus = job.review_status;
      if (reviewStatus?.message) {
        setStatus(reviewStatus.message);
      }
      if (reviewStatus?.status === 'failed') {
        throw new Error(reviewStatus.error || reviewStatus.message || 'Review preparation failed');
      }
      if (reviewStatus?.status === 'completed' && job.review) {
        syncReviewState(job.review);
        setStatus(`Review ready for ${job.review.slide_count} slides.`);
        return;
      }
      await sleep(POLL_INTERVAL_MS);
    }
  };

  const pollGenerateUntilReady = async (requestId: string) => {
    while (true) {
      const job = await fetchJobStatus(requestId);
      const generateStatus = job.generate_status;
      if (generateStatus?.message) {
        setStatus(generateStatus.message);
      }
      if (job.review) {
        syncReviewState(job.review);
      }
      if (generateStatus?.status === 'failed') {
        throw new Error(generateStatus.error || generateStatus.message || 'Generation failed');
      }
      if (generateStatus?.status === 'completed' && job.download_url) {
        setDownloadUrl(`${API_BASE}${job.download_url}`);
        setStatus(`PPTX generated. Overrides applied: ${generateStatus.overrides_applied ?? 0}.`);
        return;
      }
      await sleep(POLL_INTERVAL_MS);
    }
  };

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    setError('');
    setDownloadUrl('');
    setReview(null);
    setOverrides({});
    setStatus('Uploading and preparing review...');

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch(`${API_BASE}/convert/review`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        let errorMessage = 'Review conversion failed';
        try {
          const payload = (await response.json()) as { detail?: string; error?: string };
          errorMessage = payload.detail || payload.error || errorMessage;
        } catch {
          const text = await response.text();
          if (text) {
            errorMessage = text;
          }
        }
        throw new Error(errorMessage);
      }

      const data = (await response.json()) as { request_id: string; status: string; status_url: string; error?: string };
      if (data.error) {
        throw new Error(data.error);
      }
      setStatus('Review job queued...');
      await pollReviewUntilReady(data.request_id);
    } catch (error) {
      console.error(error);
      setError(error instanceof Error ? error.message : 'Error uploading file');
      setStatus('Review preparation failed');
    } finally {
      setUploading(false);
    }
  };

  const handleOverrideChange = (pageId: number, renderMode: RenderMode) => {
    setOverrides((current) => ({
      ...current,
      [pageId]: renderMode,
    }));
  };

  const handleGenerate = async () => {
    if (!review) return;
    setGenerating(true);
    setError('');
    setDownloadUrl('');
    setStatus('Generating PPTX with selected overrides...');

    try {
      const response = await fetch(`${API_BASE}/generate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          request_id: review.request_id,
          template: 'default',
          overrides: review.slides.map((slide) => ({
            page_id: slide.page_id,
            render_mode: overrides[slide.page_id] ?? slide.current_render_mode,
          })),
        }),
      });

      if (!response.ok) {
        let errorMessage = 'Generation failed';
        try {
          const payload = (await response.json()) as { detail?: string; error?: string };
          errorMessage = payload.detail || payload.error || errorMessage;
        } catch {
          const text = await response.text();
          if (text) {
            errorMessage = text;
          }
        }
        throw new Error(errorMessage);
      }

      const data: GeneratePayload = await response.json();
      setStatus('Generation job queued...');
      await pollGenerateUntilReady(data.request_id);
    } catch (error) {
      console.error(error);
      setError(error instanceof Error ? error.message : 'Generation failed');
      setStatus('Generation failed');
    } finally {
      setGenerating(false);
    }
  };

  const handleLogin = async () => {
    const { error } = await supabase.auth.signInWithOAuth({
      provider: 'google',
    })
    if (error) console.error(error)
  }

  const overrideCount = useMemo(() => {
    if (!review) return 0;
    return review.slides.filter(
      (slide) => (overrides[slide.page_id] ?? slide.current_render_mode) !== slide.default_render_mode
    ).length;
  }, [overrides, review]);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-50 font-[family-name:var(--font-geist-sans)]">
      <main className="mx-auto flex min-h-screen w-full max-w-7xl flex-col gap-8 px-6 py-10 lg:px-10">
        <section className="rounded-3xl border border-white/10 bg-white/5 p-6 shadow-2xl shadow-slate-950/40 backdrop-blur">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl space-y-3">
              <p className="text-sm font-medium uppercase tracking-[0.24em] text-cyan-300">Review Workspace</p>
              <h1 className="text-4xl font-semibold tracking-tight text-white">PDF2PPT Conversion Review UI</h1>
              <p className="text-sm leading-6 text-slate-300">
                Upload a PDF, inspect page-level conversion metadata, choose render modes, and generate the final PPTX.
              </p>
            </div>

            <button
              onClick={handleLogin}
              className="rounded-xl border border-cyan-400/40 bg-cyan-400/10 px-4 py-2 text-sm font-medium text-cyan-100 transition hover:bg-cyan-400/20"
            >
              Login with Google
            </button>
          </div>
        </section>

        <section className="grid gap-6 lg:grid-cols-[minmax(0,1.2fr)_minmax(320px,0.8fr)]">
          <div className="rounded-3xl border border-white/10 bg-slate-900/80 p-6 shadow-xl shadow-slate-950/30">
            <div className="flex flex-col gap-4">
              <div>
                <h2 className="text-xl font-semibold text-white">Start a review job</h2>
                <p className="mt-1 text-sm text-slate-400">
                  Upload a PDF to parse slides and prepare page-level review metadata before final generation.
                </p>
              </div>

              <div className="flex flex-col gap-3 md:flex-row md:items-center">
                <input
                  type="file"
                  accept=".pdf"
                  onChange={handleFileChange}
                  className="block w-full rounded-xl border border-white/10 bg-slate-950 px-4 py-3 text-sm text-slate-200 file:mr-4 file:rounded-lg file:border-0 file:bg-cyan-400/15 file:px-3 file:py-2 file:text-sm file:font-medium file:text-cyan-100 hover:file:bg-cyan-400/25"
                />
                <button
                  onClick={handleUpload}
                  disabled={!file || uploading}
                  className="rounded-xl bg-cyan-400 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-300 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {uploading ? 'Preparing Review...' : 'Upload for Review'}
                </button>
              </div>
            </div>
          </div>

          <div className="rounded-3xl border border-white/10 bg-slate-900/80 p-6 shadow-xl shadow-slate-950/30">
            <h2 className="text-xl font-semibold text-white">Job summary</h2>
            <div className="mt-4 space-y-3 text-sm text-slate-300">
              <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                <p className="text-slate-400">Status</p>
                <p className="mt-1 font-mono text-cyan-100">{status || 'Idle'}</p>
              </div>

              {review && (
                <>
                  <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                    <p className="text-slate-400">Request ID</p>
                    <p className="mt-1 font-mono text-xs text-slate-100">{review.request_id}</p>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                      <p className="text-slate-400">Slides</p>
                      <p className="mt-1 text-2xl font-semibold text-white">{review.slide_count}</p>
                    </div>
                    <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                      <p className="text-slate-400">Overrides</p>
                      <p className="mt-1 text-2xl font-semibold text-white">{overrideCount}</p>
                    </div>
                  </div>
                </>
              )}

              {error && (
                <div className="rounded-2xl border border-rose-500/40 bg-rose-500/10 p-4 text-rose-100">
                  {error}
                </div>
              )}

              {downloadUrl && (
                <a
                  href={downloadUrl}
                  className="inline-flex w-full items-center justify-center rounded-xl bg-emerald-400 px-4 py-3 text-sm font-semibold text-slate-950 transition hover:bg-emerald-300"
                >
                  Download Generated PPTX
                </a>
              )}
            </div>
          </div>
        </section>

        {review && (
          <section className="rounded-3xl border border-white/10 bg-slate-900/80 p-6 shadow-xl shadow-slate-950/30">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
              <div>
                <h2 className="text-2xl font-semibold text-white">Page-by-page review</h2>
                <p className="mt-1 text-sm text-slate-400">
                  Validate inferred archetypes and choose the best render mode for each slide before generating the deck.
                </p>
              </div>

              <button
                onClick={handleGenerate}
                disabled={generating}
                className="rounded-xl bg-white px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-slate-200 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {generating ? 'Generating PPTX...' : 'Generate Final PPTX'}
              </button>
            </div>

            <div className="mt-6 grid gap-4 xl:grid-cols-2">
              {review.slides.map((slide) => {
                const selectedMode = overrides[slide.page_id] ?? slide.current_render_mode;

                return (
                  <article
                    key={slide.page_id}
                    className="rounded-3xl border border-white/10 bg-gradient-to-br from-slate-900 via-slate-900 to-slate-800 p-5 shadow-lg shadow-slate-950/20"
                  >
                    <div className="flex flex-col gap-4">
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <p className="text-xs font-medium uppercase tracking-[0.2em] text-cyan-300">
                            Slide {slide.page_id}
                          </p>
                          <h3 className="mt-1 text-lg font-semibold text-white">{slide.archetype}</h3>
                          <p className="mt-1 text-xs text-slate-400">
                            {Math.round(slide.width)} × {Math.round(slide.height)} · {slide.element_count} elements
                          </p>
                        </div>
                        <div className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-slate-200">
                          Default: {slide.default_render_mode}
                        </div>
                      </div>

                      <div className="grid grid-cols-3 gap-3 text-sm">
                        <div className="rounded-2xl border border-white/10 bg-white/5 p-3">
                          <p className="text-slate-400">Text</p>
                          <p className="mt-1 text-lg font-semibold text-white">{slide.text_count}</p>
                        </div>
                        <div className="rounded-2xl border border-white/10 bg-white/5 p-3">
                          <p className="text-slate-400">Images</p>
                          <p className="mt-1 text-lg font-semibold text-white">{slide.image_count}</p>
                        </div>
                        <div className="rounded-2xl border border-white/10 bg-white/5 p-3">
                          <p className="text-slate-400">Tables</p>
                          <p className="mt-1 text-lg font-semibold text-white">{slide.table_count}</p>
                        </div>
                      </div>

                      <div className="grid gap-3 md:grid-cols-3">
                        <div className="rounded-2xl border border-white/10 bg-white/5 p-3">
                          <p className="text-xs uppercase tracking-[0.16em] text-slate-400">Archetype</p>
                          <p className="mt-2 text-sm font-semibold text-white">
                            {Math.round(slide.confidence.archetype * 100)}%
                          </p>
                        </div>
                        <div className="rounded-2xl border border-white/10 bg-white/5 p-3">
                          <p className="text-xs uppercase tracking-[0.16em] text-slate-400">Render</p>
                          <p className="mt-2 text-sm font-semibold text-white">
                            {Math.round(slide.confidence.render_mode * 100)}%
                          </p>
                        </div>
                        <div className="rounded-2xl border border-white/10 bg-white/5 p-3">
                          <p className="text-xs uppercase tracking-[0.16em] text-slate-400">Semantic Roles</p>
                          <p className="mt-2 text-sm font-semibold text-white">
                            {Math.round(slide.confidence.semantic_roles * 100)}%
                          </p>
                        </div>
                      </div>

                      <div className="rounded-2xl border border-white/10 bg-slate-950/70 p-4">
                        <label className="block text-xs font-medium uppercase tracking-[0.18em] text-slate-400">
                          Render mode override
                        </label>
                        <select
                          value={selectedMode}
                          onChange={(event) => handleOverrideChange(slide.page_id, event.target.value as RenderMode)}
                          className="mt-3 w-full rounded-xl border border-white/10 bg-slate-900 px-4 py-3 text-sm text-slate-100 outline-none transition focus:border-cyan-400"
                        >
                          {RENDER_MODE_OPTIONS.map((option) => (
                            <option key={option.value} value={option.value}>
                              {option.label}
                            </option>
                          ))}
                        </select>
                      </div>
                    </div>
                  </article>
                );
              })}
            </div>
          </section>
        )}
      </main>
    </div>
  );
}
