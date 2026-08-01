# Sahaay-Human-in-the-loop
# 🌉 SETU – Human-in-the-Loop AI Government Service Platform

> **AI that assists. Humans that decide. Citizens that trust.**

SETU is a configurable **Human-in-the-Loop AI platform** designed to accelerate government service delivery while ensuring every final decision remains under human oversight.

Built for the **Google Agentic AI Day Hackathon**, SETU demonstrates how **Responsible AI**, deterministic validation, and explainable decision-making can streamline citizen service workflows without compromising accountability.

---

# 📌 Problem Statement

Government welfare applications often involve multiple documents, manual verification, repetitive data entry, and long processing times.

While AI can automate extraction, **fully autonomous decisions are unsuitable for high-impact public services.**

SETU solves this by combining:

- Deterministic validation
- Explainable AI
- Human review
- Complete auditability

to build a trustworthy decision-support platform.

---

# 🚀 Our Solution

SETU assists government officers by:

✅ Validating uploaded documents

✅ Checking eligibility

✅ Extracting structured information using AI

✅ Assigning confidence scores

✅ Routing uncertain cases for human review

✅ Maintaining complete audit logs

The final decision always remains with a human reviewer.

---

# 🏗️ System Architecture

<p align="center">
  <img src="docs/architecture.png" width="100%">
</p>

---

# ⚙️ Key Features

### 🛡️ Deterministic Guardrails
- Document validation
- Eligibility verification
- Missing document detection
- Rule-based validation

### 🤖 Explainable AI
- Google Gemini powered extraction
- Structured AI drafts
- Confidence scoring
- Reason generation

### 👨‍⚖️ Human-in-the-Loop
- Review dashboard
- Approve / Edit / Reject
- Trusted delegate workflow
- OTP verification

### 📊 Transparency
- Audit trail
- Timeline
- Evidence reports
- Exportable JSON logs

---

# 🛠️ Tech Stack

| Category | Technology |
|----------|------------|
| Frontend | Streamlit |
| Backend | Python |
| AI | Google Gemini API |
| Validation | Regex + Rule Engine |
| Storage | JSON |
| Testing | unittest |

---

# 📂 Repository Structure

```text
backend/
frontend/
data/
docs/
tests/
```

---

# ▶️ Installation

```bash
git clone https://github.com/<username>/SETU.git

cd SETU

pip install -r requirements.txt
```

---

# ▶️ Run

Backend

```bash
python backend/main.py
```

Frontend

```bash
streamlit run frontend/app.py
```

---

# 📊 Demo Workflow

Citizen

↓

Upload Documents

↓

Guardrails Validation

↓

AI Draft Generation

↓

Human Review

↓

Final Approval

↓

Audit Report

---

# 📁 Dataset

The project uses **synthetic government documents** created exclusively for hackathon demonstration purposes.

No real citizen information or sensitive personal data is stored or processed.

---

# 🔐 Security

- No API keys committed
- No passwords stored
- Synthetic datasets only
- Human approval required before submission

---

# 📈 Scalability

SETU follows a **configuration-driven architecture**.

The same platform can support:

- Old Age Pension
- Widow Pension
- Insurance Claims
- Scholarship Verification
- Banking Nominee Transfer
- Healthcare Benefits

by updating workflow configurations instead of rewriting business logic.

---

# 📚 Documentation

- 📄 Presentation → `docs/presentation.pdf`
- 🏗 Architecture Diagram → `docs/architecture.png`
- 🔄 Workflow Diagram → `docs/workflow.png`
- 🎬 Demo Script → `docs/demo_script.md`

---

# 🤝 Third-Party Services

- Google Gemini API
- Streamlit
- Python Standard Library

---

# 📄 License

Developed for the Google Agentic AI Day Hackathon.
# 🏗️ System Architecture

<p align="center">
<img src="docs/architecture.png" width="100%">
</p>
<img width="917" height="537" alt="image" src="https://github.com/user-attachments/assets/c16e3e03-cd85-4886-9987-21b32f250dae" />
# Third-Party & Pre-existing Components

This project uses the following external technologies and services:

•⁠  ⁠Google Gemini API for AI-assisted document understanding
•⁠  ⁠Streamlit for the frontend interface
•⁠  ⁠Python standard libraries and open-source packages listed in ⁠ requirements.txt ⁠

All workflow logic, guardrails, synthetic datasets, architecture, and application code were developed by the team specifically for this hackathon.

No proprietary datasets are included. All documents used for demonstrations are synthetic and created solely for testing purposes.
