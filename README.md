# RSS Feed Discovery & Processing Tool

A Python-based tool to **discover, parse, and process RSS/Atom feeds** from given websites. The project supports running locally with a virtual environment or via **Docker** for easy setup and deployment.

---

##  Features

* Discover RSS/Atom feeds from websites
* Parse and normalize feed URLs
* Store and manage feed data in a database
* Async-friendly structure for scalability
* Dockerized setup for quick start

---

##  Project Structure

```
.
├── main.py               # Entry point
├── feed_finder.py        # RSS/Atom feed discovery logic
├── hub_parser.py         # Parses feed hub / metadata
├── csv_handler.py        # CSV read/write utilities
├── utils.py              # Helper utilities (HTTP, normalization, headers)
├── config.py             # Configuration loader (reads from .env)
├── schema.sql            # Database schema
├── requirements.txt      # Python dependencies
├── docker-compose.yml    # Docker services
├── .env                  # Environment variables (not committed)
└── .gitignore
```

---

##  Docker Setup (Recommended)

### 1 Install Docker

* Install **Docker Desktop**: [https://www.docker.com/products/docker-desktop/](https://www.docker.com/products/docker-desktop/)
* Verify installation:

```bash
docker --version
docker compose version
```

---

### 2 Create `.env` file

Create a `.env` file in the project root:

```env
# App settings
ENV=development
DEBUG=true

# Database
DB_HOST=db
DB_PORT=5432
DB_NAME=rss_db
DB_USER=postgres
DB_PASSWORD=postgres

# Scraping
REQUEST_TIMEOUT=10
MAX_RETRIES=3
USER_AGENT=Mozilla/5.0 (compatible; RSSBot/1.0)
```

⚠️ **Do not commit `.env`** — it is ignored via `.gitignore`.

---

### 3 Run with Docker

```bash
docker compose up --build
```

To run in background:

```bash
docker compose up -d
```

To stop:

```bash
docker compose down
```

---

## 🧑‍💻 Local Development (Without Docker)

### 1 Create Virtual Environment

```bash
python -m venv .venv
```

Activate it:

**Windows**

```bash
.venv\Scripts\activate
```

**macOS / Linux**

```bash
source .venv/bin/activate
```

---

### 2 Install Dependencies

```bash
pip install -r requirements.txt
```

---

### 3 Create `.env`

```env
ENV=development
DEBUG=true

DB_HOST=localhost
DB_PORT=5432
DB_NAME=rss_db
DB_USER=postgres
DB_PASSWORD=postgres

REQUEST_TIMEOUT=10
MAX_RETRIES=3
USER_AGENT=Mozilla/5.0 (compatible; RSSBot/1.0)
```

---

### 4 Initialize Database

Run your schema manually (example with PostgreSQL):

```bash
psql -U postgres -d rss_db -f schema.sql
```

---

### 5 Run the Project

```bash
python main.py
```

---

##  Input Websites

If your project reads from an input file:

```text
input_websites.txt
```

Example:

```
https://techcrunch.com
https://theverge.com
https://bbc.com
```

-- Consider committing a `input_websites.example.txt` instead of the real one.

---

##  Best Practices

* Never commit `.env`
* Use Docker for consistent environments
* Keep secrets out of source code
* Log errors instead of printing in production

---

##  Future Improvements

* Full async pipeline with `asyncio`
* Feed content persistence
* API layer for querying feeds
* Scheduler / cron support

---

##  License

MIT License

---

If you have questions or want to extend this project, feel free to open an issue or contribute 
