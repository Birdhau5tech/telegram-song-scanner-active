# 🎵 WhatsApp Song Scanner Bot → MariaDB → RadioDJ

A production-ready system that scans Telegram chats for song requests, matches them to music databases using MusicBrainz and fuzzy matching, stores verified results in MariaDB, and integrates with RadioDJ for automated playlist management.

## ✨ Features

- **Telegram Song Matching Bot**: Send song requests in your Telegram group and get instant matches from MusicBrainz
- **Intelligent Song Matching**: Uses MusicBrainz with fuzzy matching and confidence scoring
- **Database Storage**: Complete MariaDB schema for tracking chats, messages, songs, and requests
- **RadioDJ Integration**: Automated playlist addition via API or direct database access
- **Modular Architecture**: Clean separation of concerns for easy maintenance
- **Production Ready**: Docker deployment, monitoring, logging, and health checks
- **Scalable Design**: Supports multiple chats and concurrent processing

## 🤖 Telegram Song Matching (Quick Start)

The easiest way to use this project is via the Telegram bot. Send song requests in your group and get instant matches!

### Setup

1. **Create a Telegram bot** via [@BotFather](https://t.me/BotFather)
2. **Add your bot** to a Telegram group
3. **Configure `.env`**:
   ```ini
   TELEGRAM_BOT_TOKEN=your_bot_token_here
   TELEGRAM_CHAT_ID=your_group_chat_id_here
   ```

4. **Start the bot**:
   ```powershell
   cd whatsapp-song-scanner
   .\.venv\Scripts\Activate.ps1
   python src/telegram_bot.py
   ```

### Usage

Send messages in your Telegram group like:

```
Play Bohemian Rhapsody by Queen
```
```
I want to hear Blinding Lights by The Weeknd
```
```
Can you play Hoe Cakes by MF Doom
```

The bot will reply with:

```
🎵 Song Match Found!

Bohemian Rhapsody
👤 Artist: Queen
✅ Confidence: 100%
🔗 MusicBrainz
```

### How It Works

```
┌─────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│   Telegram      │───▶│  Message Parser  │───▶│  MusicBrainz     │
│   Group Chat    │    │  (extract song)  │    │  Search          │
└─────────────────┘    └──────────────────┘    └──────────────────┘
                                                        │
┌─────────────────┐    ┌──────────────────┐    ┌───────▼──────────┐
│   Bot Reply     │◀───│  Format Response │◀───│  Fuzzy Matcher   │
│   with Match    │    │                  │    │  (best match)    │
└─────────────────┘    └──────────────────┘    └──────────────────┘
```

## 🚀 Quick Start

### Prerequisites

- Docker and Docker Compose
- WhatsApp Business Account (Twilio) OR phone number (Evolution API)
- Python 3.11+ (for local development)

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/KiloMusician/whatsapp-song-scanner.git
cd whatsapp-song-scanner

# 2. Configure environment
cp .env.example .env
# Edit .env with your configuration
nano .env

# 3. Start all services with Docker
docker-compose -f docker/docker-compose.yml up -d

# 4. Initialize database
docker-compose -f docker/docker-compose.yml exec song-scanner-bot \
  python -c "from src.database.models import init_database; init_database()"

# 5. Verify installation
curl http://localhost:5000/api/v1/health
```

## 📋 System Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│   WhatsApp      │───▶│  Chat Scanner    │───▶│  Text Processor  │
│     Chats       │    │                  │    │                  │
└─────────────────┘    └──────────────────┘    └──────────────────┘
                                                            │
┌─────────────────┐    ┌──────────────────┐          ┌─────▼─────┐
│   RadioDJ       │◀───│  RadioDJ         │◀─────────│  Music    │
│   Playlists     │    │  Integrator      │          │  Matcher  │
└─────────────────┘    └──────────────────┘          └─────┬─────┘
        ▲                                                   │
        │                                            ┌─────▼─────┐
        └────────────────────────────────────────────│  MariaDB  │
                                                     │  Storage  │
                                                     └───────────┘
```

## ⚙️ Configuration

### Environment Variables

Edit `.env` file with your configuration:

```bash
# WhatsApp Provider
WHATSAPP_PROVIDER=evolution  # or 'twilio'

# For Twilio
TWILIO_ACCOUNT_SID=your_account_sid
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_WHATSAPP_NUMBER=+14155238886

# For Evolution API
EVOLUTION_API_URL=http://localhost:8080
EVOLUTION_API_KEY=your_api_key

# Database
MARIADB_HOST=mariadb
MARIADB_PORT=3306
MARIADB_DATABASE=song_scanner
MARIADB_USERNAME=scanner_bot
MARIADB_PASSWORD=changeme

# Music Matching
MUSICBRAINZ_USER_AGENT=WhatsAppSongScanner/1.0.0

# RadioDJ (optional)
RADIODJ_API_URL=http://localhost:8080/radiodj
RADIODJ_DB_PATH=/path/to/radiodj/database.sqlite

### Telegram Integration (optional)

This project can send live match notifications to a Telegram chat using a bot. To enable:

1. Create a bot with BotFather in Telegram and copy the `BOT_TOKEN`.
2. Obtain the chat id:
  - Easiest: message your bot and ask `@userinfobot` for your chat id, or
  - Send a message to the bot and call `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` and inspect `message.chat.id`.
3. Add the following to your local `.env` (do NOT commit secrets):

```dotenv
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
```

4. Test the bot (from repo root, with venv active):

```powershell
# PowerShell
python .\scripts\telegram\send_test.py "Test message from WhatsApp Song Scanner"
```

Or using PowerShell direct API call:

```powershell
$token = "<YOUR_TOKEN>"
$chat  = "<YOUR_CHAT_ID>"
Invoke-RestMethod -Uri "https://api.telegram.org/bot$token/sendMessage" -Method Post -Body @{ chat_id = $chat; text = "Test message from WhatsApp Song Scanner" }
```

5. Restart the application so it picks up environment changes. When a match/request is created the bot will forward a notification to the configured chat.

Security note: never commit bot tokens or chat ids to source control. If a token is exposed, revoke it in BotFather and generate a new one.

#### Webhook: secure `setWebhook` and handler

To make Telegram deliver updates to your app via webhook and secure them with a secret token, run:

```bash
# Set webhook with a secret token that Telegram will include as a header
curl -F "url=https://your-public-host/api/v1/webhook/telegram" \
   -F "secret_token=MY_RANDOM_SECRET" \
   https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook
```

Telegram will include the secret in the header `X-Telegram-Bot-Api-Secret-Token` for each request. Example Flask handler snippet to validate it before processing:

```python
from flask import request, abort
import os

TELEGRAM_WEBHOOK_SECRET = os.getenv('TELEGRAM_WEBHOOK_SECRET')

@app.route('/api/v1/webhook/telegram', methods=['POST'])
def telegram_webhook():
  # Validate secret header
  secret = request.headers.get('X-Telegram-Bot-Api-Secret-Token')
  if TELEGRAM_WEBHOOK_SECRET and secret != TELEGRAM_WEBHOOK_SECRET:
    abort(403)

  update = request.get_json()
  # forward to existing handler
  db = SessionLocal()
  try:
    success = message_handler.handle_telegram_update(db, update)
    return ("OK", 200) if success else ("IGNORED", 200)
  finally:
    db.close()
```

Add `TELEGRAM_WEBHOOK_SECRET` to your local `.env` (do not commit).
```

### WhatsApp Setup

#### Using Evolution API (Recommended)

1. Install and run Evolution API: `docker run -d evolution-api`
2. Configure webhook in `.env` pointing to your server
3. Link phone number via Evolution dashboard

#### Using Twilio

1. Create Twilio Business Account at twilio.com
2. Get WhatsApp Business Account credentials
3. Configure webhook URL for incoming messages
4. Update `.env` with credentials

## 🛠️ CLI Commands

The CLI provides manual operations for testing and management:

```bash
# Show status and statistics
python -m src.cli status

# Scan WhatsApp chats
python -m src.cli scan                    # Scan all active chats
python -m src.cli scan --chat-id=123      # Scan specific chat

# Sync to RadioDJ
python -m src.cli sync                    # Sync up to 50 requests
python -m src.cli sync --limit=10         # Sync custom limit

# Manage song requests
python -m src.cli list-requests           # Show pending requests
python -m src.cli approve 5               # Approve request #5
python -m src.cli reject 5 --notes="N/A"  # Reject request #5

# List chats
python -m src.cli list-chats             # Show all active chats
```

## 📡 API Endpoints

### Health & Status

- `GET /api/v1/health` - Health check
- `GET /api/v1/metrics` - Application metrics
- `GET /api/v1/status` - Current status

### Webhooks

- `POST /api/v1/webhook/twilio` - Twilio WhatsApp messages
- `POST /api/v1/webhook/evolution` - Evolution API messages

### Song Requests (if exposed)

- `GET /api/v1/requests` - List pending requests
- `PUT /api/v1/requests/:id/approve` - Approve request
- `PUT /api/v1/requests/:id/reject` - Reject request

## 🧪 Testing

```bash
# Run all tests with coverage
pytest -v --cov=src --cov-report=html

# Run specific test file
pytest tests/unit/test_text_processing.py -v

# Run with coverage report
pytest --cov=src --cov-report=term-missing
```

**Current Coverage**: 50% (32/32 tests passing)

## 🔍 Code Quality

All code passes quality checks:

```bash
# Type checking
mypy src/

# Linting
flake8 src/

# Code formatting
black src/

# Import sorting
isort src/
```

## 🐳 Docker Deployment

### Start Services

```bash
docker-compose -f docker/docker-compose.yml up -d
```

### Services

- **song-scanner-bot**: Flask application (port 5000)
- **mariadb**: Database (port 3306)
- **redis**: Cache layer (port 6379)
- **evolution-api**: WhatsApp integration (port 8080)
- **adminer**: Database management UI (port 8081)

### View Logs

```bash
docker-compose -f docker/docker-compose.yml logs -f song-scanner-bot
```

### Stop Services

```bash
docker-compose -f docker/docker-compose.yml down
```

## 📁 Project Structure

```
whatsapp-song-scanner/
├── src/
│   ├── main.py                 # Flask application entry point
│   ├── cli.py                  # CLI commands
│   ├── core/                   # Core functionality
│   │   ├── scheduler.py        # Background job scheduling
│   │   ├── health_check.py     # Health monitoring
│   │   └── state_manager.py    # Application state
│   ├── database/               # Database models and operations
│   │   ├── models.py           # SQLAlchemy ORM models
│   │   └── operations.py       # CRUD operations
│   ├── whatsapp/               # WhatsApp integration
│   │   ├── client.py           # WhatsApp client
│   │   ├── message_handler.py  # Message processing
│   │   └── chat_scanner.py     # Chat scanning logic
│   ├── text_processing/        # Text analysis
│   │   ├── text_cleaner.py     # Text normalization
│   │   ├── message_parser.py   # Pattern extraction
│   │   └── keyword_extractor.py
│   ├── music_matching/         # Music database matching
│   │   ├── musicbrainz_client.py
│   │   ├── fuzzy_matcher.py    # Fuzzy matching logic
│   │   ├── song_validator.py   # Match validation
│   │   └── matching_orchestrator.py
│   ├── radiodj_integration/    # RadioDJ sync
│   │   ├── radiodj_client.py
│   │   ├── playlist_manager.py
│   │   └── sync_service.py
│   └── utils/                  # Utilities
│       ├── logger.py
│       ├── cache.py
│       └── rate_limiter.py
├── config/                     # Configuration
│   ├── settings.py
│   ├── database.py
│   └── logging_config.py
├── docker/                     # Docker configuration
│   ├── Dockerfile
│   └── docker-compose.yml
├── tests/                      # Test suite
│   ├── unit/
│   ├── integration/
│   └── conftest.py
├── .github/workflows/          # CI/CD pipelines
│   └── ci.yml
└── requirements.txt            # Production dependencies
```

## 📊 Database Schema

### Core Tables

- **whatsapp_chats**: Tracks WhatsApp chats being scanned
- **chat_messages**: Individual messages with text and metadata
- **extracted_songs**: Song titles/artists extracted from messages
- **matched_songs**: Verified matches from MusicBrainz with confidence scores
- **song_requests**: Final song requests pending RadioDJ approval

## 🔧 Troubleshooting

### Issue: "ModuleNotFoundError: No module named 'src'"

**Solution**: Install the package in development mode:
```bash
pip install -e .
```

### Issue: Database connection fails

**Solution**: Check MariaDB is running:
```bash
docker-compose -f docker/docker-compose.yml logs mariadb
```

### Issue: WhatsApp webhooks not receiving messages

**Solution**: 
1. Verify webhook URL is publicly accessible
2. Check firewall/NAT settings
3. Verify API credentials in `.env`
4. Check application logs: `docker-compose logs song-scanner-bot`

## 📈 Performance & Monitoring

- **APScheduler**: Background job scheduling (5-min scan, 2-min sync intervals)
- **Logging**: Structured logging with rotating file handlers
- **Caching**: Redis integration for rate limit and results caching
- **Health Checks**: Endpoint monitoring and status reporting

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Make changes and ensure tests pass
4. Commit with clear message (`git commit -m 'Add amazing feature'`)
5. Push to branch (`git push origin feature/amazing-feature`)
6. Open Pull Request

## 📝 License

This project is licensed under the MIT License - see LICENSE file for details.

## 🙏 Acknowledgments

- [MusicBrainz](https://musicbrainz.org/) for music database API
- [Twilio](https://www.twilio.com/) for WhatsApp integration
- [Evolution API](https://github.com/EvolutionAPI/evolution-api) for alternative WhatsApp integration
- [RadioDJ](http://www.radiodj.ro/) for radio automation software
- [Flask](https://flask.palletsprojects.com/) for web framework
- [SQLAlchemy](https://www.sqlalchemy.org/) for ORM

#### Option 1: Evolution API (Recommended for Testing)

1. Access Evolution API dashboard: `http://localhost:8080`
2. Create a new instance
3. Scan QR code with your WhatsApp
4. Configure instance name in `.env`

#### Option 2: Twilio API (Production)

1. Create Twilio account and enable WhatsApp Sandbox
2. Configure webhook: `http://your-server:5000/api/v1/webhook/twilio`
3. Set credentials in `.env`

## 🏗️ Project Structure

```
whatsapp-song-scanner/
├── config/                 # Configuration files
├── src/
│   ├── whatsapp/          # WhatsApp integration
│   ├── text_processing/   # Message parsing and cleaning
│   ├── music_matching/    # MusicBrainz and fuzzy matching
│   ├── database/          # MariaDB models and operations
│   ├── radiodj_integration/ # RadioDJ integration
│   ├── core/              # Scheduler, health checks, state
│   └── utils/             # Logging, cache, rate limiter
├── tests/                 # Unit and integration tests
├── docker/                # Docker configuration
├── scripts/               # Setup and maintenance scripts
└── data/                  # Logs, cache, exports
```

## 🔧 API Endpoints

### Health & Monitoring
- `GET /api/v1/health` - System health check
- `GET /api/v1/metrics` - Application metrics
- `GET /api/v1/scan/status` - Scanning status

### Webhooks
- `POST /api/v1/webhook/twilio` - Twilio webhook
- `POST /api/v1/webhook/evolution` - Evolution API webhook

### Song Requests
- `GET /api/v1/requests/pending` - Get pending requests
- `POST /api/v1/requests/approve` - Approve request
- `POST /api/v1/requests/reject` - Reject request

## 🐳 Docker Deployment

```bash
# Build and start
make up

# View logs
make logs

# Stop services
make down

# Run tests
make test

# Database backup
make backup
```

## 🧪 Testing

```bash
# Run all tests
pytest -v

# Run specific test suite
pytest tests/unit/test_text_processing.py -v
pytest tests/integration/test_whatsapp_integration.py -v

# Run with coverage
pytest --cov=src --cov-report=html
```

## 📊 Database Schema

The system uses 5 main tables:

1. **whatsapp_chats** - Tracks monitored WhatsApp conversations
2. **chat_messages** - Stores individual messages
3. **extracted_songs** - Song phrases extracted from messages
4. **matched_songs** - Verified song information from MusicBrainz
5. **song_requests** - Final requests ready for RadioDJ

See `src/database/schema.sql` for detailed schema.

## 🔄 Maintenance

### Automated Tasks

- **Chat Scanning**: Every 5 minutes (configurable)
- **RadioDJ Sync**: Every 2 minutes
- **Database Cleanup**: Daily at 2 AM
- **Log Rotation**: When logs reach 100MB

### Manual Maintenance

```bash
# Backup database
./scripts/maintenance/backup_database.sh

# Clean cache
./scripts/maintenance/cleanup_cache.sh

# Rotate logs
./scripts/maintenance/rotate_logs.sh
```

## 🚨 Troubleshooting

### WhatsApp Connection Issues

```bash
# For Evolution API
docker-compose logs evolution-api

# For Twilio
# Check webhook logs in Twilio console
docker-compose logs song-scanner-bot | grep webhook
```

### Database Connection Failed

```bash
# Check MariaDB status
docker-compose ps mariadb

# View MariaDB logs
docker-compose logs mariadb

# Test connection
mysql -h localhost -P 3306 -u scanner_bot -p
```

### MusicBrainz Rate Limiting

```bash
# Reduce scan frequency in .env
SCAN_INTERVAL=10  # Scan every 10 minutes
```

## 📈 Monitoring

- **Application Health**: `http://localhost:5000/api/v1/health`
- **Prometheus** (optional): `http://localhost:9090`
- **Grafana** (optional): `http://localhost:3000`
- **Evolution API**: `http://localhost:8080`

## 🔒 Security Considerations

- Store sensitive credentials in `.env` (never commit)
- Use environment-specific `.env` files
- Enable RadioDJ database backups before direct access
- Validate WhatsApp webhook signatures
- Rate limit API endpoints
- Regular security updates via `pip` and Docker images

## 📝 Development

### Local Development

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt -r requirements-dev.txt

# Run locally
python src/main.py
```

### Code Quality

```bash
# Format code
make format

# Lint code
make lint

# Type checking
mypy src
```

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Credits

- **MusicBrainz** - Open music encyclopedia
- **Twilio** - WhatsApp Business API
- **Evolution API** - Open-source WhatsApp integration
- **RadioDJ** - Radio automation software

## 📞 Support

For issues and questions:
- Open an issue on GitHub
- Check logs in `data/logs/`

---

**Note**: This is a WhatsApp-specific bot, NOT a Discord bot. All chat scanning functionality is built around WhatsApp's APIs and protocols.
