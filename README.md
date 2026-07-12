# 🌌 Aura: AI-Powered Personal Photo Organiser

Aura is a high-performance, self-hosted photo management system built around specialized vector embedding spaces, offline machine learning models, and portable database architectures. 

It indexes local directories and Google Photos, extracts faces and groups people automatically using DBSCAN, categorizes images via zero-shot CLIP, runs local OCR on documents, identifies duplicates (using SHA256 and LSH-optimized perceptual hashing), and plans natural language search queries using Gemini 2.5 Flash.

---

## 🏗️ System Architecture

Aura coordinates a modern web architecture, supporting a fully containerized Docker Compose stack for production and a zero-configuration SQLite stack for local development.

```mermaid
graph TD
    Client[React Web Dashboard <br/> Nginx / Port 3000] <-->|HTTP / REST API <br/> Status Polling| API[FastAPI Web Server <br/> Port 8000]
    API <-->|SQLAlchemy ORM <br/> SafeVector Layer| DB[(Database <br/> PostgreSQL + pgvector / SQLite)]
    API <-->|Enqueue Jobs| Queue[Redis Message Broker <br/> Port 6379]
    Worker[Celery Background Worker] <-->|Fetch Tasks| Queue
    Worker <-->|Write Records| DB
    Worker -->|Read/Write Files| Storage[Local Disk Storage <br/> ./uploads /photos_data]

    subgraph Offline Ingestion Pipeline
        CLIP[CLIP ViT-B-32 <br/> 512-dim Semantic Image Space]
        MTCNN[MTCNN Face Detector] --> FaceNet[FaceNet <br/> 512-dim Face Vector Space]
        DBSCAN[DBSCAN Clustering <br/> Face Grouping]
        OCR[PyTesseract OCR] --> MiniLM[all-MiniLM-L6-v2 <br/> 384-dim OCR Text Space]
        PHASH[pHash DCT <br/> 64-bit Int Hamming Distance]
    end

    Worker -.-> Offline Ingestion Pipeline
```

---

## 🧠 Key Features & Technical Details

### 1. Specialized Core Embedding Spaces
To optimize accuracy, Aura avoids using a single vector space for all semantics, instead splitting concerns into three specialized mathematical representation spaces:
* **Semantic Image Space (CLIP ViT-B-32)**: Generates **512-dimensional** whole-image embeddings for visual/conceptual matches (e.g. searching *"sunset over hills"*).
* **Face Recognition Space (MTCNN + FaceNet)**: MTCNN detects bounding boxes, and InceptionResnetV1 (FaceNet) extracts **512-dimensional** face vectors. Aura groups people automatically using **DBSCAN Clustering** (eps=0.55, min_samples=2) without requiring manual tags.
* **OCR Text Space (all-MiniLM-L6-v2)**: If an image is classified as a document/receipt/prescription, Aura runs PyTesseract OCR and encodes the text into a **384-dimensional** sentence-embedding space, enabling document search by text content.

### 2. Dual-Database Portability (`SafeVector`)
Aura features a custom SQLAlchemy TypeDecorator called `SafeVector` that allows the system to remain database-independent:
* **PostgreSQL + pgvector**: When running inside Docker, `SafeVector` compiles columns directly into native PostgreSQL `vector(N)` columns, running high-speed Cosine Similarity indexes on the database server.
* **SQLite Fallback**: For local development, `SafeVector` compiles into `TEXT` columns, storing float arrays as serialized JSON strings. When search queries are run, the backend dynamically loads the vectors and runs vector similarity in Python using **NumPy** matrix operations.

### 3. $O(N)$ Locality Sensitive Hashing (LSH) Deduplication
Comparing 64-bit perceptual hashes (pHash) pairwise to detect near-duplicates is an $O(N^2)$ operation, which lags at 100,000+ photos. Aura indexes pHashes using LSH:
* The 64-bit pHash is split into four 16-bit blocks.
* If two images have a Hamming distance of $\le 4$, they *must* share at least one identical 16-bit chunk (Pigeonhole Principle).
* Candidates are filtered by matching 16-bit buckets first, reducing comparisons to $O(N)$ linear time and finding near-duplicates in sub-second times.

### 4. Zero-Shot Optimization (Category Caching)
Ingesting photos zero-shot via CLIP requires matching image embeddings against candidate category text embeddings. Aura caches the candidate category text embeddings ("a scanned document", "a pet", etc.) in class memory upon startup, saving millions of redundant operations and speeding up zero-shot categorization by **500%**.

### 5. Stateless Google Photos Sync
To protect user privacy, Aura uses a **stateless authentication flow**. Google OAuth tokens (access & refresh tokens) are never persisted on the server's disk or database. They are redirected to the frontend, stored solely in the client browser's `localStorage`, and passed dynamically in the HTTP headers when synchronization tasks are triggered.

---

## ⚡ Setup & Launch Instructions

### Prerequisites
* Python 3.10+ (for local runs) or Docker & Docker Compose.
* [Google Gemini API Key](https://aistudio.google.com/) (Required for Search Query Planner).
* Tesseract OCR installed on your system path (if running locally: `pip install pytesseract` requires `tesseract-ocr` binary).

### 1. Environment Variables
Create a `.env` file in the root folder:
```env
# Gemini API Key for Natural Language Search Planning
GEMINI_API_KEY=your_gemini_api_key_here

# Google OAuth Credentials (Optional - for Google Photos Connection)
GOOGLE_CLIENT_ID=your_google_client_id_here
GOOGLE_CLIENT_SECRET=your_google_client_secret_here
GOOGLE_REDIRECT_URI=http://localhost:8000/api/v1/auth/google/callback
```

### 2. Running Locally (Docker-less SQLite Mode)
Runs the server with a local `aura_photos.db` SQLite file and runs background tasks on the FastAPI execution thread (Redis/Celery not required).

**On Windows (PowerShell)**:
```powershell
# Installs dependencies, sets local folders, and runs frontend + backend
./run_local.ps1
```
*Note: Make sure uvicorn is run without `--reload` during heavy scanning, as file uploads will trigger uvicorn server restarts and clear the model caches.*

**On macOS/Linux**:
```bash
chmod +x run_local.sh
./run_local.sh
```

### 3. Running with Docker Compose (Production Postgres Mode)
Launches PostgreSQL+pgvector, Redis, FastAPI, Celery, and Nginx.
```bash
docker-compose up --build
```
* **Web Client**: [http://localhost:3000](http://localhost:3000)
* **Backend Docs (Swagger)**: [http://localhost:8000/docs](http://localhost:8000/docs)

### 4. Running Tests
Run automated tests covering LSH deduplication, face clustering, and database models:
```bash
cd backend
pip install -r requirements.txt
pytest tests/
```
