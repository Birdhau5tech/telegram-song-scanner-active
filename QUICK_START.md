# ⚡ QUICK START GUIDE

**5-Minute Setup for WhatsApp Song Scanner**

---

## ✅ Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop) installed and running
- WhatsApp Business Account (Twilio) OR phone number (Evolution API)
- 5 GB free disk space
- Ports 5000, 3306, 6379 available

---

## 🚀 Installation (5 minutes)

### **Step 1: Configure Environment** (2 min)
```bash
# Copy configuration template
cp .env.example .env

# Edit with your settings
# Choose: Twilio OR Evolution API
nano .env
```

### **Step 2: Start Services** (2 min)
```bash
# Start Docker containers
docker-compose -f docker/docker-compose.yml up -d

# Wait for services to start (should see all running)
docker-compose -f docker/docker-compose.yml ps
```

### **Step 3: Access Dashboard** (1 min)
```bash
# Open in browser
http://localhost:5000
```

---

## 📡 Configure WhatsApp

### **Option A: Twilio (5 minutes)**
1. Go to https://console.twilio.com
2. Create WhatsApp Sandbox account
3. Get **Account SID** and **Auth Token**
4. Add to `.env`:
   ```
   WHATSAPP_PROVIDER=twilio
   TWILIO_ACCOUNT_SID=your_sid
   TWILIO_AUTH_TOKEN=your_token
   TWILIO_WHATSAPP_NUMBER=+1234567890
   ```
5. Set webhook: `http://your-ip:5000/api/v1/webhook/twilio`

### **Option B: Evolution API (3 minutes)**
1. Visit http://localhost:8080
2. Scan QR code with WhatsApp
3. Get instance name from dashboard
4. Already in `.env` - just update:
   ```
   WHATSAPP_PROVIDER=evolution
   EVOLUTION_INSTANCE_NAME=your_instance_name
   ```

---

## 🎯 Configure RadioDJ

### **Method 1: API (if available)**
```env
RADIODJ_API_URL=http://your-radiodj:8080/api
RADIODJ_API_KEY=your_api_key
```

### **Method 2: Direct Database**
```env
RADIODJ_DB_PATH=/path/to/RadioDJ/Database.db
RADIODJ_DEFAULT_PLAYLIST_ID=1
```

---

## 📊 Dashboard Quick Tour

### **Access Dashboard**
```
http://localhost:5000
```

### **What You See**
- **Pending Requests**: Songs awaiting your approval
- **Approve Button**: ✓ Click to queue song to RadioDJ
- **Reject Button**: ✗ Click to skip song
- **Status**: Green = System healthy

### **Workflow**
1. Someone requests a song on WhatsApp
2. System matches it to MusicBrainz
3. **You see it in Dashboard → Pending**
4. Click ✓ Approve
5. **Song automatically added to RadioDJ**

---

## ✅ Verify Everything Works

```bash
# Check system health
curl http://localhost:5000/api/v1/health

# View pending requests
curl http://localhost:5000/api/v1/requests/pending

# Test approval
curl -X POST http://localhost:5000/api/v1/requests/approve \
  -H "Content-Type: application/json" \
  -d '{"id": 1}'
```

---

## �️ Local Development (Without Docker)

### **Start Telegram Bot**
```powershell
# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Set Python path and start bot (with logging)
$env:PYTHONPATH = "."
Start-Process -FilePath ".\.venv\Scripts\python.exe" -ArgumentList "src/telegram_bot.py" -RedirectStandardOutput "bot_out.log" -RedirectStandardError "bot_err.log" -NoNewWindow

# Or run in foreground (see output directly)
$env:PYTHONPATH = "."; .\.venv\Scripts\python.exe src/telegram_bot.py
```

### **Start Flask API Server**
```powershell
$env:PYTHONPATH = "."; .\.venv\Scripts\python.exe src/main.py
```

### **Monitor Bot Logs**
```powershell
# Watch error log in real-time
Get-Content bot_err.log -Tail 20 -Wait

# View recent output
Get-Content bot_out.log -Tail 30
```

### **Check if Bot is Running**
```powershell
Get-Process python -ErrorAction SilentlyContinue | Select-Object Id, ProcessName
```

### **Stop All Python Processes**
```powershell
Stop-Process -Name python -Force -ErrorAction SilentlyContinue
```

---

## �🐛 Quick Troubleshooting

### **Dashboard won't load**
```bash
docker-compose -f docker/docker-compose.yml restart song-scanner-bot
```

### **Can't connect to WhatsApp**
```bash
# Check Evolution API running
docker ps | grep evolution

# View logs
docker logs whatsapp-song-scanner | tail -20
```

### **RadioDJ not syncing**
```bash
# Verify path/API credentials in .env
# Restart services
docker-compose -f docker/docker-compose.yml restart
```

### **Port already in use**
```bash
# Change port in .env
APP_PORT=5001

# Restart
docker-compose down && docker-compose up -d
```

---

## 📞 Next Steps

- ✅ Open dashboard: http://localhost:5000
- ✅ Test song request via WhatsApp
- ✅ Approve request in dashboard
- ✅ Verify it appears in RadioDJ
- 📖 See [DEPLOYMENT.md](DEPLOYMENT.md) for advanced config

---

## 🛑 Stop Services

```bash
docker-compose -f docker/docker-compose.yml down
```

---

**That's it! Your system is running.** 🎉

Refer to [DEPLOYMENT.md](DEPLOYMENT.md) for detailed configuration and troubleshooting.
