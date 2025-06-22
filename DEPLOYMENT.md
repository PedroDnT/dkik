# DEPLOYMENT.md  
*Deploying the DKIK WhatsApp Bot (TJSP) on Render.com*

---

## 1. Prerequisites
| Item | Purpose |
|------|---------|
| **Render account** | PaaS where we will host the API and background worker |
| **GitHub repository** (public/private) | Source code (`https://github.com/PedroDnT/dkik`) |
| **MongoDB Atlas cluster** | Primary data store |
| **Twilio WhatsApp Business account** | Messaging channel |
| **OpenAI account** | LLM API key for LangChain agent |
| **DataJud credentials** | Judiciary data source |

> Keep all credentials handy; we will add them to Render as environment variables.

---

## 2. Repository Structure Recap
```
dkik/
 ├─ app/            # FastAPI application
 ├─ worker/         # Background scheduler
 ├─ Dockerfile      # Multi-stage image
 ├─ docker-entrypoint.sh
 ├─ requirements.txt
 └─ …
```
The same container image is used for **Web Service** and **Background Worker**; the command changes (`web` vs `worker`).

---

## 3. Create Render Services

### 3.1. Web Service (`dkik-api`)
1. **Dashboard → New → Web Service**
2. **Connect repository** → choose `dkik`.
3. **Environment**  
   - Runtime: **Docker**  
   - Dockerfile path: `Dockerfile`  
4. **Build & Start Command**  
   - *Leave empty*: Render will use `CMD` from `Dockerfile`, which our entrypoint interprets as `web`.
5. **Instance Type**  
   - Start with **Starter – 512 MB / 0.5 CPU**. Upgrade if latency > 5 s.
6. **Environment Variables**  
   Add the following (all `Type` = *Secret*):  
   ```
   TWILIO_ACCOUNT_SID=<value>
   TWILIO_AUTH_TOKEN=<value>
   TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886

   OPENAI_API_KEY=<value>
   OPENAI_MODEL=gpt-4-turbo-preview

   DATAJUD_API_KEY=<value>
   DATAJUD_API_BASE_URL=https://api.datajud.cnj.jus.br/v1

   MONGODB_URI=mongodb+srv://<user>:<pass>@cluster.mongodb.net/dkik
   MONGODB_DB_NAME=dkik

   JWT_SECRET=<random-long-string>
   DEBUG=false            # set true for staging
   LOG_LEVEL=INFO
   ALLOWED_PHONE_NUMBERS= # optional whitelist, comma-separated
   ```
   Render automatically exposes `PORT`.

7. **Health Check**  
   - Path: `/api/health`  
   - Success codes: `200-299`

> After the first deploy, Render provides a URL like `https://dkik-api.onrender.com`.

### 3.2. Background Worker (`dkik-worker`)
1. **Dashboard → New → Background Worker**
2. **Connect repository**: same repo.
3. **Environment → Docker** (same image).
4. **Start Command**  
   ```
   worker
   ```
5. **Environment Variables**  
   Duplicate the **exact same** variables from the Web Service (Render’s *Sync from* helper does this).
6. **Instance Type**  
   - **Starter** is fine; bump CPU if polling lag appears.

> The worker’s entrypoint runs `python worker/main.py`, starting APScheduler jobs: process polling, hearing reminders, etc.

---

## 4. MongoDB Atlas Setup
1. Create an **M0/M2 cluster** (free tier OK for dev).  
2. Whitelist Render’s egress IPs *(Settings → Network Access)*.  
3. Add database user and generate connection string:  
   ```
   mongodb+srv://dkik:<password>@cluster.mongodb.net/dkik
   ```  
4. Replace `<password>` above and store in `MONGODB_URI`.

---

## 5. Twilio WhatsApp Webhook Configuration
1. In **Twilio Console → Messaging → Senders → WhatsApp Sandbox** (or Business number):  
   - **WHEN A MESSAGE COMES IN** → `https://dkik-api.onrender.com/webhook`  
2. Save. Twilio will POST every incoming message to the endpoint; we verify the signature in FastAPI.

---

## 6. Deploy Steps Summary
```bash
# 1. Push code to GitHub
git add .
git commit -m "feat: initial DKIK bot"
git push origin main

# 2. Render automatically builds & deploys web and worker

# 3. Verify health
curl https://dkik-api.onrender.com/api/health
# => {"success":true, ...}

# 4. Send WhatsApp message to sandbox number:
#    "Qual o status do processo 1234567-89.2023.8.26.0000?"
#    Bot should reply within 5 seconds.
```

---

## 7. Scaling & Tuning
| Concern | Recommendation |
|---------|----------------|
| **Cold starts** | Keep “Instance auto-sleep” disabled for the API service. |
| **High throughput** | Upgrade to “Pro – 2 GB / 1 CPU” when daily messages > 2 000. |
| **Long-running jobs** | Worker already uses APScheduler; adjust `WORKER_POLLING_INTERVAL_MINUTES` env var. |
| **Secrets rotation** | Use Render *Environment Groups*; redeploy services after editing. |
| **Observability** | Render logs tab + MongoDB Atlas Metrics + Twilio Messaging logs. |

---

## 8. Domain & SSL (optional)
1. Add a **Custom Domain** in Render → point DNS CNAME to `dkik-api.onrender.com`.
2. Render issues Auto-SSL certificates.

---

## 9. Backup & Disaster Recovery
| Resource | Strategy |
|----------|----------|
| MongoDB Atlas | Enable daily snapshots (M2+) |
| Render services | Continuous deploy via GitHub; re-provisionable |
| Twilio numbers | Sticky to account; export message logs |

---

## 10. Rollback
1. Render keeps previous images; click **Deploys → Rollback**.  
2. Ensure DB migrations are backward compatible before rolling back.

---

## 11. Troubleshooting Checklist
| Symptom | Possible Cause | Fix |
|---------|----------------|-----|
| 502 on Render | Health check failing | Check env vars & logs |
| Bot silent | Worker down or polling interval too high | Restart worker / lower interval |
| Twilio 403 webhook | Signature mismatch | URL incorrect or env `TWILIO_AUTH_TOKEN` wrong |
| Slow replies (>5 s) | Model latency | Enable GPU model or cache responses |

---

**🚀 DKIK is now live!**  
Test end-to-end, monitor logs, gather lawyer feedback, then iterate on new features (jurisprudence search, dashboard, etc.).
