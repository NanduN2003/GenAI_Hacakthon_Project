# Travel Assistant AI

This guide explains how to set up and run the Travel Assistant AI project. For a detailed look at the architecture and agent-based workflow, see the "Overview" section below.

## Quick Start: How to Run

Follow these steps to get the application running on your local machine.

### 1. Prerequisites

- Python 3.10+ and `pip`
- An active Amadeus Developer account (for API keys)
- A Google Cloud Platform account (for Google GenAI and Vision API keys)

### 2. Setup & Configuration

**a. Clone & Enter the Repository**
```bash
git clone <your-repository-url>
cd Hacakthon_Project
```

**b. Create & Activate a Virtual Environment**
- **Windows:**
  ```bash
  python -m venv .venv
  .\.venv\Scripts\activate
  ```
- **macOS / Linux:**
  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  ```

**c. Install Dependencies**
```bash
pip install -r requirements.txt
```

**d. Configure Environment Variables**
Create a `.env` file in the project root and add your API keys.
```env
# --- Google Cloud & GenAI ---
GCP_PROJECT_ID="your-gcp-project-id"
GCP_REGION="your-gcp-region"
GOOGLE_API_KEY="your-google-api-key"

# --- Amadeus API ---
AMADEUS_CLIENT_ID="your-amadeus-client-id"
AMADEUS_CLIENT_SECRET="your-amadeus-client-secret"

# --- Application Settings ---
UPLOADS_DIR="uploads"
```

### 3. Run the Application
Start the FastAPI server with Uvicorn.
```bash
uvicorn main:app --reload
```
The application will be available at `http://127.0.0.1:8000`.

### 4. Use the App
1.  Navigate to `http://127.0.0.1:8000`.
2.  Upload an image of a travel request.
3.  Enter a company name from `scripts/dummy_crm_data.json` (e.g., "Innovate Inc").
4.  Press "Send" to see the live analysis and flight results.

---

##  Overview

This project uses a multi-agent architecture driven by a central orchestrator to process travel requests. It is designed for simplicity and clarity, prioritizing a direct, observable workflow over complex, dynamic agent protocols.

### Core Technology
- **Backend**: **FastAPI** provides the web server and API endpoints.
- **AI & Language Models**: **LangChain** and **Google GenAI** are used to construct the core logic for understanding user intent.
- **External APIs**: **Google Vision API** for OCR and **Amadeus API** for flight and hotel data.
- **Frontend**: A lightweight interface built with **HTML, CSS, and JavaScript**, communicating with the backend via Server-Sent Events (SSE) for real-time updates.

### Architecture & Agent Workflow
The system's architecture is centered around the `TravelOrchestrator`, which manages a sequence of specialized agents. This is a practical, linear multi-agent system, not a formal A2A or MCP-based one.

**Workflow Sequence:**
1.  **Image Upload**: The user uploads an image to the FastAPI backend.
2.  **Vision Agent**: The orchestrator calls this agent to perform OCR on the image, extracting raw text.
3.  **CRM Agent**: The orchestrator takes the user-provided company name and calls this agent to fetch relevant customer data (preferences, history) from the CRM.
4.  **Intent Agent**: The orchestrator passes the cleaned text and CRM data to this agent. It uses a LangChain-powered LLM to analyze the information and extract a structured `TravelRequest` (e.g., flight details, dates, destination).
5.  **Enrichment Agent**: The orchestrator passes the structured request to this agent, which applies any final business logic or data enrichment.
6.  **Streaming Response**: Throughout this process, the orchestrator sends real-time status updates to the frontend. The final, structured data is sent as the last event.

**Agent Communication Model:**
- **Central Control**: The `TravelOrchestrator` is the single point of control.
- **No Direct Agent-to-Agent Communication**: Agents are isolated and do not call each other. They receive data from the orchestrator, process it, and return the result. This makes the system predictable and easy to debug.
- **Asynchronous Flow**: The orchestrator uses `async` calls to manage the workflow efficiently, ensuring the server remains responsive.


