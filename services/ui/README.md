# Financial Document Intelligence - UI Service

The **UI Service** provides an interactive web interface built with **Gradio** for users to query the Financial Intelligence Agent and view grounded responses with reasoning details.

---

## 🚀 Features

- **Interactive Web Interface**: Clean UI for asking financial questions and viewing results.
- **Agent API Integration**: Sends user queries directly to the Agent Service REST endpoints.
- **Structured Response View**: Displays final answers alongside calculated data and evidence types.

---

## 🛠 Project Structure

```text
services/ui/
├── app.py           # Gradio application and frontend logic
├── requirements.txt # UI-specific Python dependencies
└── Dockerfile       # Container setup for UI deployment