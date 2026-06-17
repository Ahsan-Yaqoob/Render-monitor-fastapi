# 🚀 Render Monitor FastAPI - Setup & Troubleshooting Guide

## ✅ Installation Complete!

Your FastAPI Render Monitor is fully installed and ready to run.

## 🔧 Quick Start

### 1. Activate Virtual Environment

**Windows:**
```bash
cd render-monitor-fastapi
venv\Scripts\activate
```

**macOS/Linux:**
```bash
cd render-monitor-fastapi
source venv/bin/activate
```

### 2. Configure Environment Variables

Edit `.env` file and add your credentials:
```env
RENDER_API_KEY=your_actual_render_api_key
RENDER_SERVICE_ID=your_actual_service_id
EMAIL_SENDER=your_email@gmail.com
EMAIL_PASSWORD=your_gmail_app_password
EMAIL_RECEIVER=recipient@example.com
FASTAPI_PORT=8000
FASTAPI_HOST=0.0.0.0
DEBUG=False
```

### 3. Run the Application

```bash
python -m uvicorn backend.main:app --reload
```

Or without reload (for production):
```bash
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

### 4. Access the Dashboard

- **Dashboard**: http://localhost:8000
- **API Docs (Swagger)**: http://localhost:8000/docs
- **Alternative Docs (ReDoc)**: http://localhost:8000/redoc

## 📦 Installed Packages

All dependencies are pre-built wheels (no compilation needed):

```
FastAPI              0.104.1
Uvicorn (with extras) 0.24.0
Python-dotenv        1.0.0
APScheduler          3.10.4
Requests             2.31.0
Pydantic             2.4.2
Pydantic-settings    2.0.3
```

## 🔐 Getting Your Credentials

### Render API Key
1. Visit https://dashboard.render.com
2. Go to Account Settings
3. Find API Keys section
4. Create a new API key
5. Copy and paste in `.env`

### Render Service ID
1. Go to your service in Render Dashboard
2. Copy the service ID from the URL: `https://dashboard.render.com/services/{SERVICE_ID}`
3. Paste in `.env`

### Gmail App Password
1. Enable 2-Step Verification on your Google Account
2. Go to myaccount.google.com → Security
3. Find "App passwords" section
4. Generate password for Mail + Windows Computer
5. Use this password in `.env` (NOT your Gmail password)

## 🌐 Deployment to Render

### 1. Push to GitHub
```bash
git add .
git commit -m "Render Monitor FastAPI"
git push origin main
```

### 2. Create Web Service on Render
- Go to https://dashboard.render.com
- Click "New" → "Web Service"
- Connect your GitHub repo
- Set:
  - **Build Command**: `pip install -r requirements.txt`
  - **Start Command**: `uvicorn backend.main:app --host 0.0.0.0 --port 8000`

### 3. Add Environment Variables
Add all `.env` variables in Render dashboard

### 4. Deploy
Click Deploy and wait for completion

## 🐛 Troubleshooting

### "Module not found" Error
```bash
# Make sure venv is activated
venv\Scripts\activate  # Windows
source venv/bin/activate  # macOS/Linux

# Then verify installations
pip list
```

### Port Already in Use
```bash
# Change port in .env or command line
python -m uvicorn backend.main:app --port 9000
```

### Emails Not Sending
- [ ] Use Gmail App Password (not regular password)
- [ ] Enable 2-Step Verification on Gmail
- [ ] Check EMAIL_SENDER format (must be full Gmail address)
- [ ] Verify less secure apps is disabled (if using 2FA)

### API Not Responding
- [ ] Check uvicorn is running: `python -m uvicorn backend.main:app --reload`
- [ ] Check port 8000 is not blocked by firewall
- [ ] Verify FASTAPI_PORT in `.env`

### Dashboard Shows "No Data"
- [ ] Make sure scheduler is running (check console logs)
- [ ] Render API credentials must be correct
- [ ] Service must be reachable from Render's servers

## 📊 API Endpoints

All endpoints return JSON:

```
GET  /                          - Dashboard HTML
GET  /api/status                - Current service status
GET  /api/history?limit=100     - Event history
GET  /api/stats?days=30         - Statistics
GET  /api/stats/daily-failures  - Daily failure counts
GET  /api/stats/issue-frequency - Issue frequency
GET  /api/stats/downtime-by-issue - Downtime by issue
GET  /api/stats/recovery-time-avg - Average recovery time
GET  /api/health                - Health check
POST /api/monitor/check         - Manual status check
GET  /docs                       - Interactive API docs
GET  /redoc                      - Alternative API docs
```

## 📝 File Structure

```
render-monitor-fastapi/
├── backend/
│   ├── main.py                   # FastAPI app
│   ├── config/settings.py        # Configuration
│   ├── routes/dashboard_routes.py # API routes
│   ├── services/
│   │   ├── render_checker.py     # Render API calls
│   │   ├── monitor_service.py    # Core logic
│   │   ├── email_service.py      # Email alerts
│   │   ├── stats_service.py      # Statistics
│   │   └── scheduler.py          # Background tasks
│   ├── database/
│   │   ├── models.py            # Data models
│   │   └── csv_handler.py       # CSV storage
│   ├── utils/
│   │   ├── logger.py            # Logging
│   │   └── helpers.py           # Utilities
│   └── data/
│       └── logs.csv             # Event logs
├── frontend/
│   ├── index.html               # Dashboard UI
│   ├── css/style.css            # Styling
│   └── js/
│       ├── api.js               # API client
│       ├── charts.js            # Charts
│       └── dashboard.js         # Dashboard logic
├── venv/                         # Virtual environment
├── .env                          # Credentials
├── requirements.txt              # Dependencies
├── render.yaml                   # Deployment config
└── README.md                     # Documentation
```

## 💡 Pro Tips

1. **Local Development**: Use `--reload` flag for auto-restart on file changes
2. **Debugging**: Set `DEBUG=True` in `.env` for detailed error messages
3. **Logging**: Check `logs/` folder for daily log files
4. **Testing API**: Use Swagger UI at `/docs` to test endpoints
5. **Production**: Don't use `--reload` on production servers

## ✨ Features Verified

✅ FastAPI server starts successfully  
✅ All imports working  
✅ Configuration loaded  
✅ CSV handler ready  
✅ Email service ready  
✅ Render checker ready  
✅ Scheduler ready  
✅ Virtual environment complete  
✅ All dependencies installed  

## 🚀 You're Ready!

Your Render Monitor is fully set up and ready to go. Just configure your `.env` file with actual credentials and start monitoring!

```bash
# Activate venv
venv\Scripts\activate

# Run the app
python -m uvicorn backend.main:app --reload

# Open in browser
# http://localhost:8000
```

## 📞 Need Help?

1. Check logs in `logs/` directory
2. Verify credentials in `.env`
3. Test with `/docs` endpoint
4. Review README.md for details
5. Check Render API status: https://status.render.com

---

**Render Monitor v1.0.0 (FastAPI)** - Happy Monitoring! 🎉
