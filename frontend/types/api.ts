// Types that mirror the FastAPI response schema exactly.

export interface Finding {
  type: string
  severity: "LOW" | "MEDIUM" | "HIGH"
  title: string
  evidence: Record<string, unknown>
  reason: string
  section: string | null
}

export interface Report {
  filename: string
  priority: "LOW" | "MEDIUM" | "HIGH"
  score: number
  sections: Record<string, string>
  missing_sections: string[]
  findings: Finding[]
  score_breakdown: Record<string, number>
  finding_counts: {
    HIGH: number
    MEDIUM: number
    LOW: number
    total: number
  }
}

export interface AnalyzeResponse {
  reports: Report[]
  summary: {
    total: number
    HIGH: number
    MEDIUM: number
    LOW: number
    errors: Array<{ filename: string; error: string }>
  }
}
