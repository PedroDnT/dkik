# DKIK – WhatsApp Bot for São Paulo State Lawyers (TJSP)

DKIK is an AI-powered WhatsApp bot that helps lawyers practicing in the São Paulo Court of Justice (TJSP) keep track of their cases, receive real-time procedural updates, and get reminders about upcoming hearings – all from WhatsApp.

## ✨ Why DKIK?

Monitoring dozens of case dockets through the TJSP portal is time-consuming and error-prone. DKIK automates this routine by combining:

* Twilio WhatsApp API for secure, reliable messaging  
* DataJud (CNJ) API for authoritative case information  
* An AI Agent (OpenAI + LangChain) to interpret natural-language questions in Portuguese  
* MongoDB for persistent subscription and movement logs  

The result: lawyers stay informed within seconds, without switching apps or hiring extra staff.

---

## 📋 Core Features

| Priority | Feature | Status |
|----------|---------|--------|
| **Must** | 🔍 Query case status via CNJ number (e.g. `1234567-89.2023.8.26.0000`) | ⬜ |
| **Must** | 🔔 Automatic push notifications when a new movement is published | ⬜ |
| **Must** | 🗓️ Daily reminders for scheduled hearings | ⬜ |
| **Should** | 🗣️ Natural-language support in PT-BR (“Qual o status …?”) | ⬜ |
| **Should** | ✅ Basic user verification (whitelist / subscription) | ⬜ |
| **Could** | 🏛️ Integration with other SP courts & legislative updates | ⬜ |

---

## 🏗️ High-Level Architecture

```
Lawyer ⇄ WhatsApp ⇄ Twilio Webhook (FastAPI)
                          │
                          ▼
                  AI Agent (LangChain)
                          │
        ┌───────────┬─────┴─────┬───────────┐
        │           │           │           │
   DataJud API  MongoDB   Scheduler  Future Tools
```

* A single webhook endpoint receives WhatsApp messages from Twilio.  
* The LangChain Agent classifies intent and decides whether to call:
  * **DataJudTool** – fetches case data.
  * **SubscriptionTool** – read/write user subscriptions.
* Background **scheduler/worker** polls DataJud and triggers proactive updates.

> The full PlantUML diagram is available in [`docs/architecture.puml`](docs/architecture.puml).

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | **FastAPI** (Python 3.11) |
| AI / NLP | **OpenAI** Chat Completions + **LangChain** Agents |
| Messaging | **Twilio** WhatsApp Business API |
| Data Source | **DataJud** (Conselho Nacional de Justiça) |
| Database | **MongoDB Atlas** |
| Deployment | **Render.com** (Web Service + Background Worker) |
| Testing | **pytest**, **httpx** |

---

## 📂 Repository Structure

```
dkik/
 ├── app/                # FastAPI application
 │   ├── main.py         # Entry point / webhook
 │   ├── agents/         # LangChain agent & prompt templates
 │   ├── tools/          # DataJud, Subscription, etc.
 │   └── models/         # Pydantic and MongoEngine schemas
 ├── worker/             # Background notification scheduler
 ├── tests/              # Unit & integration tests
 ├── requirements.txt
 └── README.md
```

*(Directory skeleton will be generated in upcoming commits.)*

---

## 🚀 Quick Start (Local Development)

1. **Clone repo**

```bash
git clone https://github.com/PedroDnT/dkik.git
cd dkik
```

2. **Create virtual environment**

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

3. **Environment variables**

Create `.env` in the project root:

```
OPENAI_API_KEY=sk-...
DATAJUD_API_KEY=...
MONGODB_URI=mongodb+srv://user:pass@cluster.mongodb.net/dkik
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886
```

4. **Run FastAPI server**

```bash
uvicorn app.main:app --reload --port 8000
```

5. **Expose webhook (development)**  
Use ngrok or Render preview URL and configure it in the Twilio Console → Sandbox.

---

## 🖥️ Deployment on Render

1. Create two Render services:
   * **Web Service** – build & run `uvicorn app.main:app`.
   * **Background Worker** – run `python worker/main.py`.
2. Add the same environment variables in Render Dashboard.
3. Point Twilio “Webhook URL” to `https://<render-web-url>/webhook`.

More details in [`docs/deployment.md`](docs/deployment.md).

---

## 🧑‍💻 Running the Scheduler Locally

```bash
python worker/main.py
```

The worker loads all subscribed CNJ numbers, polls DataJud every *N* minutes (configurable), and sends WhatsApp updates when new movements are detected.

---

## ✅ Testing

```bash
pytest -q
```

Tests mock Twilio and DataJud responses to enable offline runs.

---

## 🗺️ Roadmap / Milestones

1. **Project Setup & Config** – Twilio Sandbox, Render, MongoDB, DataJud  
2. **AI Agent & Tool Integration** – LangChain tools, prompt templates  
3. **WhatsApp User Flow** – Webhook handling & conversational logic  
4. **Notification Scheduler** – Background worker + push messages  
5. **Testing & LGPD Compliance**  
6. **Production Launch** – Twilio prod number, approved templates  
7. **Post-Launch Monitoring** – Logs, metrics, user feedback  

---

## 🤝 Contributing

Pull requests are welcome! Please open an issue first to discuss major changes.

1. Fork the repo & create your branch: `git checkout -b feature/foo`.
2. Commit your changes: `git commit -m 'Add foo'`.
3. Push to the branch: `git push origin feature/foo`.
4. Open a PR.

---

## 📝 License

Distributed under the MIT License. See `LICENSE` for more information.
