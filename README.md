# LabLens — AI-Powered Programming Lab Report Review Assistant

**A sharper lens for every lab report.**

LabLens is an AI-powered assistant that helps teaching assistants review programming lab reports by identifying potential inconsistencies, detecting missing or insufficient sections, and prioritizing reports that may need closer inspection.

Instead of replacing human judgment, LabLens provides structured findings and supporting evidence to make the review process more organized and efficient.

**Live Demo:** [app.aspraklablens.me](https://app.aspraklablens.me)

---

## The Problem

Reviewing programming lab reports involves more than checking whether a program runs. Teaching assistants may need to examine multiple report components and verify whether they are consistent with one another.

For example:
- A report may contain incomplete or missing sections.
- The pseudocode may describe branches that do not match the source code.
- The written analysis may overlook important programming constructs.
- Potential inconsistencies may be difficult to spot when reviewing many reports.

These checks take time and can make the review process challenging to manage.

## The Solution

LabLens combines a pretrained large language model (LLM) with deterministic, rule-based analysis to help identify potential issues in programming lab reports.

The system processes an uploaded PDF, extracts its report sections, runs multiple analyzers, and produces findings with a review-priority score.

LabLens is designed as a **decision-support tool for teaching assistants**, not an automated grading system.

## Key Features

- **PDF Processing:** Extracts text from uploaded programming lab reports.
- **Section Extraction:** Organizes report content into sections such as Introduction, Flowchart, Pseudocode, Code, Analysis, Output, and Conclusion.
- **Completeness Analysis:** Detects missing or insufficiently populated sections.
- **Pseudocode–Code Checks:** Uses predefined rules to identify selected structural inconsistencies.
- **Analysis–Code Checks:** Checks whether the written analysis mentions programming constructs found in the code.
- **LLM-Based Semantic Analysis:** Uses a pretrained LLM through an API to identify potential inconsistencies between pseudocode, source code, and written analysis.
- **Anomaly Scoring:** Combines findings using deterministic scoring rules to assign a review priority.
- **Human-in-the-Loop Review:** Presents findings to teaching assistants, who remain responsible for the final judgment.

## How It Works

```text
Programming Lab Report PDF
            |
            v
     PDF Text Extraction
            |
            v
      Section Extraction
            |
            v
      Hybrid Analysis
       /           \
      v             v
Rule-Based         LLM-Based
Analyzers          Analysis
       \           /
            v
      Findings Merge
            |
            v
    Deterministic Scoring
            |
            v
   Findings & Review Priority
            |
            v
   Teaching Assistant Review
```

### 1. PDF and Section Processing

LabLens extracts text from the uploaded PDF using PyMuPDF and organizes the content into report sections for downstream analysis.

### 2. Rule-Based Analysis

Deterministic analyzers apply predefined rules to check report completeness and selected structural relationships between pseudocode, source code, and written analysis.

These checks are based on explicit programming rules and patterns rather than a trained machine learning classifier.

### 3. LLM-Based Semantic Analysis

A pretrained large language model is accessed through an API to analyze potential inconsistencies that may require more flexible interpretation.

Structured prompts guide the model to report potential issues with supporting evidence and avoid inventing information.

The LLM performs inference using an existing model. LabLens does not claim to train or fine-tune its own foundation model.

### 4. Anomaly Scoring

The findings are passed to a deterministic scoring component that considers finding types and severity levels to calculate a review-priority score.

The score helps teaching assistants decide where to focus their attention first. It is not a student grade, a calibrated probability of error, or proof that a report is incorrect.

### 5. Human Review

Teaching assistants inspect the findings and make the final decision. LabLens supports the review process rather than replacing academic judgment.

## System Architecture

LabLens uses a separate frontend and backend.

```text
Teaching Assistant
        |
        v
Vercel
Next.js / React Frontend
        |
        | HTTPS API Request
        v
Cloudflare Network
        |
        v
Cloudflare Tunnel
        |
        v
Linux VM
  |             |
  v             v
FastAPI       cloudflared
Backend       Connector
  |
  v
External LLM API
```

The frontend is deployed on Vercel, while the Python FastAPI backend runs on a Linux virtual machine. Cloudflare Tunnel provides a connection for exposing the configured backend service without requiring a publicly exposed inbound server port.

The backend runs the analysis pipeline and communicates with the configured external LLM API when needed.

*This diagram is a conceptual overview. The exact request routing depends on the deployed Cloudflare Tunnel and application configuration.*

## Technology Stack

| Component | Technology |
|---|---|
| Frontend | Next.js, React |
| Backend | Python, FastAPI |
| PDF Processing | PyMuPDF |
| AI / Semantic Analysis | Pretrained LLM accessed through an API |
| Deterministic Analysis | Python-based rules and regular expressions |
| Scoring | Custom deterministic anomaly-scoring logic |
| Frontend Hosting | Vercel |
| Backend Connectivity | Cloudflare Tunnel |
| Backend Hosting | Linux VM |

## Getting Started

### Prerequisites

- Python and pip
- Node.js and npm
- Git
- API credentials for the LLM provider configured in the backend

### 1. Clone the Repository

```bash
git clone <YOUR_GITHUB_REPOSITORY_URL>
cd lablens
```

Replace the repository URL and directory name with the actual values for your repository.

### 2. Set Up the Backend

```bash
cd backend

python3 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
pip install -r requirements.txt
```

Create a `.env` file inside the backend directory and configure the API credentials required by your implementation.

```dotenv
GEMINI_API_KEY=your_gemini_api_key
GROQ_API_KEY=your_groq_api_key
```

Keep real API keys private. Never commit `.env` or other files containing secrets to GitHub.

Start the backend locally:

```bash
uvicorn api:app --reload
```

The API documentation is typically available at:

`http://127.0.0.1:8000/docs`

Use this address only for a local development server running on its default port.

### 3. Set Up the Frontend

Open a separate terminal:

```bash
cd frontend

npm install
npm run dev
```

Configure the frontend's backend API URL using the environment variable and format expected by the actual frontend implementation.

Do not use a production backend URL or local development URL without verifying which environment the frontend is configured to use.

## Limitations

- LLM findings may be incomplete or incorrect and require human verification.
- Rule-based checks cover explicitly implemented patterns; they do not establish full semantic equivalence between pseudocode and source code.
- Extracting PDF text does not automatically mean that diagrams or images are visually understood by the system.
- The review-priority score is a heuristic indicator, not a calibrated probability or an academic grade.
- LabLens is intended to assist teaching assistants, not to replace them.

## Future Improvements

Potential areas for further development include:
- More robust semantic comparison between pseudocode and source code.
- Improved handling of PDF layouts and diagram content.
- Evaluation of finding accuracy against manually reviewed reports.
- More detailed explanations and evidence for each finding.
- Support for additional report formats and programming languages.

These are potential improvements, not claims about existing features.

## Project Context

LabLens was developed as an AI-assisted software project for the **ML Empowerment Build Challenge 3.0**.

The project explores how pretrained language models can be combined with deterministic programmatic checks to support a real-world academic workflow.

**The goal is simple: help teaching assistants review reports more systematically while keeping humans in control.**
