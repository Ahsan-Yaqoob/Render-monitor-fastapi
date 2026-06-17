# 🚀 Render Monitor - Service Status Dashboard (FastAPI)

A production-ready monitoring system for tracking Render service status with real-time alerts, comprehensive analytics, and an interactive dashboard. Built with FastAPI for high performance.

## 📋 Features

- **Real-time Service Monitoring**: Checks Render service status every 5 minutes
- **Smart Alerting**: Email notifications when service goes down and recovers
- **Interactive Dashboard**: Beautiful web interface with real-time status updates
- **Analytics & Charts**: Issue frequency and failure timeline visualization
- **Event Timeline**: Complete history of all service status changes
- **Uptime Tracking**: Detailed statistics on service reliability
- **Auto-refresh**: Dashboard updates every 30 seconds
- **Zero Dependencies Frontend**: Pure HTML, CSS, and JavaScript (no frameworks)
- **FastAPI**: Modern, fast ASGI web framework with automatic API documentation

## 🛠️ Tech Stack

- **Backend**: Python, FastAPI, Uvicorn
- **Scheduler**: APScheduler (5-minute intervals)
- **Email**: Gmail SMTP with Python smtplib
- **Data Storage**: CSV file (logs.csv)
- **Frontend**: HTML, CSS, JavaScript (Vanilla)
- **Charts**: Chart.js (CDN)
- **Deployment**: Render.com

## 📁 Project Structure

```
render-monitor/
├── backend/
│   ├── main.py                 # FastAPI application entry point
│   ├── config/
│   │   └── settings.py         # Configuration and environment variables
│   ├── routes/
│   │   └── dashboard_routes.py # API endpoints
│   ├── services/
│   │   ├── render_checker.py   # Render API integration
│   │   ├── monitor_service.py  # Core monitoring logic
│   │   ├── email_service.py    # Email notifications
│   │   ├── stats_service.py    # Statistics calculation
│   │   └── scheduler.py        # Background scheduler
│   ├── database/
│   │   ├── models.py           # Data models
│   │   └── csv_handler.py      # CSV file operations
│   ├── utils/
│   │   ├── logger.py           # Logging utility
│   │   └── helpers.py          # Helper functions
│   └── data/
│       └── logs.csv            # CSV data storage
├── frontend/
│   ├── index.html              # Main dashboard page
│   ├── css/
│   │   └── style.css           # Styling
│   ├── js/
│   │   ├── api.js              # API client
│   │   ├── charts.js           # Chart management
│   │   └── dashboard.js        # Dashboard logic
│   └── assets/                 # Static assets
├── requirements.txt            # Python dependencies
├── render.yaml                 # Render deployment config
├── .env                        # Environment variables
└── README.md                   # This file
```

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- pip
- Gmail account with App Password
- Render API key
- Git (optional)

### Local Setup

1. **Clone the repository** (or extract the files)
```bash
git clone <repository-url>
cd render-monitor
```

2. **Create virtual environment**
```bash
python -m venv venv

# On Windows
venv\Scripts\activate

# On macOS/Linux
source venv/bin/activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Configure environment variables**

Create a `.env` file in the root directory with:
```env
RENDER_API_KEY=your_render_api_key
RENDER_SERVICE_ID=your_service_id
EMAIL_SENDER=your_gmail@gmail.com
EMAIL_PASSWORD=your_gmail_app_password
EMAIL_RECEIVER=notification_email@example.com
FASTAPI_PORT=8000
FASTAPI_HOST=0.0.0.0
DEBUG=False
```

5. **Run the application**
```bash
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

6. **Access the dashboard**
Open your browser and navigate to: `http://localhost:8000`

## 🔧 Configuration Guide

### Render API Key

1. Go to [Render Dashboard](https://dashboard.render.com)
2. Click your account icon → **Account Settings**
3. Scroll to **API Keys** section
4. Click **Create API Key**
5. Copy the key and paste in `.env`

### Render Service ID

1. In Render Dashboard, click on your service
2. The service ID is in the URL: `https://dashboard.render.com/services/{SERVICE_ID}`
3. Copy and paste in `.env`

### Gmail App Password

1. Go to [Google Account](https://myaccount.google.com)
2. Click **Security** in the left menu
3. Enable **2-Step Verification** if not already enabled
4. Go back to Security
5. Find **App passwords** (appears after 2FA is enabled)
6. Select **Mail** and **Windows Computer** (or your device)
7. Generate the password
8. Use this password in `.env` (not your Gmail password)

### Email Configuration

- **EMAIL_SENDER**: Your Gmail address
- **EMAIL_PASSWORD**: App password from Gmail (not your actual password)
- **EMAIL_RECEIVER**: Email where you want to receive alerts

## 📊 API Endpoints

### Status
```
GET /api/status
```
Returns current service status, downtime, and recent activity.

### History
```
GET /api/history?limit=100
```
Returns all event records from CSV.

### Statistics
```
GET /api/stats?days=30
```
Returns comprehensive statistics including uptime, failures, and issue frequency.

### Daily Failures
```
GET /api/stats/daily-failures?days=30
```
Returns failure count per day for charting.

### Issue Frequency
```
GET /api/stats/issue-frequency
```
Returns count of each issue type.

### Downtime by Issue
```
GET /api/stats/downtime-by-issue
```
Returns total downtime grouped by issue type.

### Manual Check
```
POST /api/monitor/check
```
Triggers an immediate service status check.

### API Documentation
```
GET /docs
```
Interactive API documentation (Swagger UI)

```
GET /redoc
```
Alternative API documentation (ReDoc)

## 📧 Email Alerts

### Down Alert
- **Subject**: 🔴 ALERT: Your Render Service is DOWN
- **Contains**: Service name, failure time, issue type

### Recovery Alert
- **Subject**: 🟢 RECOVERED: Your Render Service is Back
- **Contains**: Service name, recovery time, total downtime duration

## 🌐 Deploying on Render

### Step 1: Push to GitHub

```bash
git add .
git commit -m "Initial commit"
git push origin main
```

### Step 2: Create Service on Render

1. Go to [Render Dashboard](https://dashboard.render.com)
2. Click **+ New** → **Web Service**
3. Connect your GitHub repository
4. Configure:
   - **Name**: `render-monitor`
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn backend.main:app --host 0.0.0.0 --port 8000`

### Step 3: Set Environment Variables

In Render dashboard, go to **Environment**:
```
RENDER_API_KEY=your_key
RENDER_SERVICE_ID=your_service_id
EMAIL_SENDER=your_email@gmail.com
EMAIL_PASSWORD=your_app_password
EMAIL_RECEIVER=recipient@example.com
FASTAPI_PORT=8000
DEBUG=False
```

### Step 4: Deploy

Click **Deploy** and wait for the deployment to complete.

Your application will be available at: `https://your-render-service.onrender.com`

## 📊 CSV Data Format

The `backend/data/logs.csv` file stores all monitoring events with the following columns:

```
id,timestamp,service_name,status,issue_type,duration,resolved_at
```

- **id**: Unique identifier for the record
- **timestamp**: ISO format timestamp when event occurred
- **service_name**: Name of the service being monitored
- **status**: FAILED, RECOVERED, or RUNNING
- **issue_type**: Type of issue (CONNECTION_ERROR, TIMEOUT, HTTP_ERROR, UNKNOWN)
- **duration**: How long the failure lasted (in minutes)
- **resolved_at**: When the issue was resolved (ISO format or empty)

## 🔄 Monitoring Logic

The system works as follows:

1. **Every 5 minutes**: Checks Render service status via API
2. **Status Change Detected**:
   - DOWN → UP: Records recovery event and sends recovery email
   - UP → DOWN: Records failure event and sends alert email
3. **No Change**: Updates last check timestamp
4. **Data Storage**: All events logged to CSV for historical analysis
5. **Dashboard**: Updates every 30 seconds with latest data

## 🛡️ Security Considerations

- Store `.env` file securely (never commit to Git)
- Use Gmail App Password, not your actual password
- Regenerate Render API key periodically
- Use HTTPS on production (automatic on Render)
- Rotate secrets regularly

## 🐛 Troubleshooting

### "Invalid API Key" Error
- Verify your RENDER_API_KEY in `.env`
- Check that API key has not been revoked
- Generate a new API key from Render dashboard

### "Service Not Found" Error
- Verify your RENDER_SERVICE_ID is correct
- Check the service ID from Render dashboard URL

### Emails Not Sending
- Verify Gmail App Password (not your Gmail password)
- Ensure 2-Step Verification is enabled on Gmail
- Check that SMTP settings are correct
- Verify EMAIL_SENDER and EMAIL_PASSWORD

### Dashboard Not Loading
- Ensure FastAPI server is running
- Check browser console for errors
- Verify port 8000 is not blocked

### Can't Connect to API
- Check if uvicorn server is running: `uvicorn backend.main:app --reload`
- Verify firewall settings
- Check that FASTAPI_PORT is correct in `.env`

## 📈 Performance

FastAPI Advantages:
- **High Performance**: Built on Starlette with async support
- **Automatic Documentation**: Interactive API docs with Swagger UI
- **Type Validation**: Built-in request/response validation
- **Async Support**: Non-blocking operations
- **Production Ready**: Runs with Uvicorn ASGI server

Monitoring Dashboard Features:
- **Status Section**: Current service status (✓ RUNNING or ✗ FAILED)
- **Current downtime duration** (if failed)
- **Last check time** and **last recovery time**

### Statistics
- Total checks performed
- Total failures recorded
- Total recovery events
- Total downtime duration
- Uptime percentage
- Most common issue type

### Charts
- **Issue Frequency**: Bar chart of issue types
- **Failure Timeline**: Line chart showing failures over 30 days

### Event Timeline
- Complete history of all events
- Sorted by most recent
- Color-coded by status
- Shows duration for resolved events

## 📝 Logging

Logs are stored in `logs/` directory with daily files:
- Format: `monitor_YYYYMMDD.log`
- Console output: INFO level and above
- File output: DEBUG level and above

## 📄 License

MIT License - feel free to use and modify for your needs.

## 🤝 Support

For issues or questions:
1. Check the Troubleshooting section
2. Review environment variables configuration
3. Check application logs in `logs/` directory
4. Verify API credentials are correct
5. Access API documentation at `/docs` or `/redoc`

## 🎉 Features Roadmap

- [ ] SMS alerts
- [ ] Slack integration
- [ ] Multiple service monitoring
- [ ] Custom check intervals
- [ ] Alert scheduling
- [ ] Historical data export
- [ ] Performance graphs
- [ ] WebSocket real-time updates

## 📞 Contact

For support or feedback, please open an issue or contact the development team.

---

**Render Monitor v1.0.0 (FastAPI Edition)** - Keep your services monitored, stay informed, never miss an outage.
