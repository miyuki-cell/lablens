"use client"

import { useState, useCallback } from "react"
import type { AnalyzeResponse, Report, Finding } from "@/types/api"

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "https://api.aspraklablens.me"

type Priority = "LOW" | "MEDIUM" | "HIGH"

const PRIORITY_COLOR: Record<Priority, string> = {
  HIGH:   "text-red-600 bg-red-50 border-red-200",
  MEDIUM: "text-amber-600 bg-amber-50 border-amber-200",
  LOW:    "text-green-700 bg-green-50 border-green-200",
}

const SEVERITY_DOT: Record<Priority, string> = {
  HIGH:   "bg-red-500",
  MEDIUM: "bg-amber-500",
  LOW:    "bg-green-500",
}

function PriorityBadge({ priority }: { priority: Priority }) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded border text-xs font-medium ${PRIORITY_COLOR[priority]}`}>
      {priority}
    </span>
  )
}

// ---------------------------------------------------------------------------
// Upload view
// ---------------------------------------------------------------------------
function UploadView({ onResult }: { onResult: (r: AnalyzeResponse) => void }) {
  const [files, setFiles]         = useState<File[]>([])
  const [dragging, setDragging]   = useState(false)
  const [loading, setLoading]     = useState(false)
  const [error, setError]         = useState<string | null>(null)

  const addFiles = useCallback((incoming: FileList | null) => {
    if (!incoming) return
    const pdfs = Array.from(incoming).filter(f => f.name.toLowerCase().endsWith(".pdf"))
    if (pdfs.length === 0) { setError("Only PDF files are accepted."); return }
    setError(null)
    setFiles(prev => {
      const existing = new Set(prev.map(f => f.name))
      return [...prev, ...pdfs.filter(f => !existing.has(f.name))]
    })
  }, [])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragging(false)
    addFiles(e.dataTransfer.files)
  }, [addFiles])

  const handleAnalyze = async () => {
    if (files.length === 0) return
    setLoading(true)
    setError(null)
    try {
      const form = new FormData()
      files.forEach(f => form.append("files", f))
      const res = await fetch(`${API_BASE}/analyze`, { method: "POST", body: form })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body?.detail?.message ?? `Server error ${res.status}`)
      }
      onResult(await res.json())
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Unknown error")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-xl mx-auto mt-12 space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-[#1f2328]">Upload Practical Reports</h1>
        <p className="text-[#57606a] text-sm mt-1">
          Upload one or more PDF reports. LabLens will analyze each one and rank them by priority.
        </p>
      </div>

      {/* Drop zone */}
      <div
        onDragOver={e => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => document.getElementById("file-input")?.click()}
        className={`border-2 border-dashed rounded-lg px-8 py-12 text-center cursor-pointer transition-colors
          ${dragging ? "border-[#3b82d4] bg-blue-50" : "border-[#e5e7eb] hover:border-[#3b82d4]"}`}
      >
        <input
          id="file-input"
          type="file"
          accept=".pdf"
          multiple
          className="hidden"
          onChange={e => addFiles(e.target.files)}
        />
        <p className="text-[#57606a] text-sm">
          Drop PDF files here, or <span className="text-[#3b82d4]">click to browse</span>
        </p>
      </div>

      {/* File list */}
      {files.length > 0 && (
        <ul className="space-y-1">
          {files.map((f, i) => (
            <li key={i} className="flex items-center justify-between text-sm bg-[#f7f8fa] rounded px-3 py-2">
              <span className="text-[#1f2328] truncate">{f.name}</span>
              <button
                className="text-[#57606a] hover:text-red-500 ml-4 text-xs"
                onClick={e => { e.stopPropagation(); setFiles(prev => prev.filter((_, j) => j !== i)) }}
              >
                remove
              </button>
            </li>
          ))}
        </ul>
      )}

      {error && <p className="text-red-600 text-sm">{error}</p>}

      <button
        onClick={handleAnalyze}
        disabled={files.length === 0 || loading}
        className="w-full py-2.5 rounded bg-[#1f2328] text-white text-sm font-medium
                   hover:bg-[#2d3748] disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
      >
        {loading ? "Analyzing…" : `Analyze ${files.length > 0 ? `${files.length} report${files.length > 1 ? "s" : ""}` : ""}`}
      </button>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Dashboard view
// ---------------------------------------------------------------------------
function DashboardView({
  response,
  onSelect,
  onReset,
}: {
  response: AnalyzeResponse
  onSelect: (r: Report) => void
  onReset: () => void
}) {
  const { summary, reports } = response

  return (
    <div className="space-y-6">
      {/* Summary bar */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-[#1f2328]">Analysis Results</h1>
          <p className="text-[#57606a] text-sm">{summary.total} report{summary.total !== 1 ? "s" : ""} analyzed</p>
        </div>
        <button onClick={onReset} className="text-sm text-[#3b82d4] hover:underline">
          ← Upload more
        </button>
      </div>

      {/* Priority summary */}
      <div className="grid grid-cols-3 gap-3">
        {(["HIGH", "MEDIUM", "LOW"] as Priority[]).map(p => (
          <div key={p} className={`rounded-lg border px-4 py-3 ${PRIORITY_COLOR[p]}`}>
            <div className="text-2xl font-bold">{summary[p]}</div>
            <div className="text-xs font-medium mt-0.5">{p}</div>
          </div>
        ))}
      </div>

      {/* Report list */}
      <div className="border border-[#e5e7eb] rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-[#f7f8fa] border-b border-[#e5e7eb]">
              <th className="text-left px-4 py-2.5 font-medium text-[#57606a]">Report</th>
              <th className="text-left px-4 py-2.5 font-medium text-[#57606a]">Priority</th>
              <th className="text-left px-4 py-2.5 font-medium text-[#57606a]">Score</th>
              <th className="text-left px-4 py-2.5 font-medium text-[#57606a]">Findings</th>
            </tr>
          </thead>
          <tbody>
            {reports.map((r, i) => (
              <tr
                key={i}
                onClick={() => onSelect(r)}
                className="border-b last:border-0 border-[#e5e7eb] hover:bg-[#f7f8fa] cursor-pointer"
              >
                <td className="px-4 py-3 font-medium text-[#1f2328] truncate max-w-[220px]">{r.filename}</td>
                <td className="px-4 py-3"><PriorityBadge priority={r.priority} /></td>
                <td className="px-4 py-3 text-[#57606a]">{(r.score * 100).toFixed(0)}%</td>
                <td className="px-4 py-3 text-[#57606a]">{r.finding_counts.total}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {summary.errors.length > 0 && (
        <div className="border border-red-200 bg-red-50 rounded-lg px-4 py-3 text-sm text-red-700">
          <p className="font-medium mb-1">{summary.errors.length} file(s) failed to process:</p>
          <ul className="list-disc list-inside space-y-1">
            {summary.errors.map((e, i) => (
              <li key={i}><span className="font-medium">{e.filename}</span>: {e.error}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Finding card
// ---------------------------------------------------------------------------
function FindingCard({ finding }: { finding: Finding }) {
  const [open, setOpen] = useState(false)

  return (
    <div className="border border-[#e5e7eb] rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-start gap-3 px-4 py-3 text-left hover:bg-[#f7f8fa] transition-colors"
      >
        <span className={`mt-1.5 w-2 h-2 rounded-full flex-shrink-0 ${SEVERITY_DOT[finding.severity]}`} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-medium text-[#1f2328] text-sm">{finding.title}</span>
            <PriorityBadge priority={finding.severity} />
          </div>
          {finding.section && (
            <span className="text-xs text-[#57606a]">Section: {finding.section}</span>
          )}
        </div>
        <span className="text-[#57606a] text-xs mt-0.5">{open ? "▲" : "▼"}</span>
      </button>

      {open && (
        <div className="border-t border-[#e5e7eb] px-4 py-3 space-y-3 bg-[#f7f8fa]">
          {/* Reason */}
          <div>
            <p className="text-xs font-semibold text-[#57606a] uppercase tracking-wide mb-1">Reason</p>
            <p className="text-sm text-[#1f2328]">{finding.reason}</p>
          </div>

          {/* Evidence */}
          {Object.keys(finding.evidence).length > 0 && (
            <div>
              <p className="text-xs font-semibold text-[#57606a] uppercase tracking-wide mb-1">Evidence</p>
              <div className="space-y-2">
                {Object.entries(finding.evidence).map(([k, v]) => (
                  <div key={k}>
                    <p className="text-xs text-[#57606a] mb-0.5">{k.replace(/_/g, " ")}</p>
                    {typeof v === "string" && v.length > 0 ? (
                      <pre className="text-xs bg-white border border-[#e5e7eb] rounded p-2 whitespace-pre-wrap break-words font-mono">
                        {v}
                      </pre>
                    ) : (
                      <code className="text-xs bg-white border border-[#e5e7eb] rounded px-2 py-1">
                        {JSON.stringify(v)}
                      </code>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Detail view
// ---------------------------------------------------------------------------
function DetailView({ report, onBack }: { report: Report; onBack: () => void }) {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <button onClick={onBack} className="text-sm text-[#3b82d4] hover:underline mb-2 block">
            ← Back to results
          </button>
          <h1 className="text-xl font-semibold text-[#1f2328] break-all">{report.filename}</h1>
        </div>
        <div className="text-right flex-shrink-0">
          <PriorityBadge priority={report.priority} />
          <p className="text-[#57606a] text-xs mt-1">Score: {(report.score * 100).toFixed(0)}%</p>
        </div>
      </div>

      {/* Finding counts */}
      <div className="flex gap-3">
        {(["HIGH", "MEDIUM", "LOW"] as Priority[]).map(p => (
          report.finding_counts[p] > 0 && (
            <span key={p} className={`text-xs font-medium px-2 py-1 rounded border ${PRIORITY_COLOR[p]}`}>
              {report.finding_counts[p]} {p}
            </span>
          )
        ))}
      </div>

      {/* Missing sections */}
      {report.missing_sections.length > 0 && (
        <div className="border border-amber-200 bg-amber-50 rounded-lg px-4 py-3 text-sm">
          <p className="font-medium text-amber-800 mb-1">Missing sections</p>
          <ul className="list-disc list-inside text-amber-700 space-y-0.5">
            {report.missing_sections.map(s => <li key={s}>{s}</li>)}
          </ul>
        </div>
      )}

      {/* Findings */}
      <div>
        <h2 className="font-semibold text-[#1f2328] mb-3">
          Findings <span className="text-[#57606a] font-normal text-sm">({report.findings.length})</span>
        </h2>
        {report.findings.length === 0 ? (
          <p className="text-[#57606a] text-sm">No issues detected.</p>
        ) : (
          <div className="space-y-2">
            {report.findings.map((f, i) => <FindingCard key={i} finding={f} />)}
          </div>
        )}
      </div>

      {/* Score breakdown */}
      {Object.keys(report.score_breakdown).length > 0 && (
        <div>
          <h2 className="font-semibold text-[#1f2328] mb-3">Score Breakdown</h2>
          <div className="border border-[#e5e7eb] rounded-lg overflow-hidden">
            {Object.entries(report.score_breakdown).map(([type, val], i) => (
              <div
                key={type}
                className={`flex justify-between px-4 py-2 text-sm ${i % 2 === 0 ? "bg-[#f7f8fa]" : "bg-white"}`}
              >
                <span className="text-[#57606a]">{type.replace(/_/g, " ")}</span>
                <span className="font-medium text-[#1f2328]">{(val * 100).toFixed(1)}%</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Root page — state machine
// ---------------------------------------------------------------------------
type AppState =
  | { view: "upload" }
  | { view: "dashboard"; response: AnalyzeResponse }
  | { view: "detail"; response: AnalyzeResponse; report: Report }

export default function HomePage() {
  const [state, setState] = useState<AppState>({ view: "upload" })

  if (state.view === "upload") {
    return <UploadView onResult={r => setState({ view: "dashboard", response: r })} />
  }

  if (state.view === "dashboard") {
    return (
      <DashboardView
        response={state.response}
        onSelect={r => setState({ view: "detail", response: state.response, report: r })}
        onReset={() => setState({ view: "upload" })}
      />
    )
  }

  return (
    <DetailView
      report={state.report}
      onBack={() => setState({ view: "dashboard", response: state.response })}
    />
  )
}
