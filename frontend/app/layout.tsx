import type { Metadata } from "next"
import "./globals.css"

export const metadata: Metadata = {
  title: "LabLens",
  description: "AI-assisted practical report analyzer",
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-white">
        <header className="border-b border-[#e5e7eb] px-6 py-3 flex items-center gap-3">
          <span className="font-semibold text-[15px] tracking-tight text-[#1f2328]">LabLens</span>
          <span className="text-[#57606a] text-xs">Practical Report Analyzer</span>
        </header>
        <main className="max-w-4xl mx-auto px-6 py-8">{children}</main>
      </body>
    </html>
  )
}
