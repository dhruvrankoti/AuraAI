# Aura: AI-Powered Photo Management System

Aura is a high-fidelity, senior-level photo organizer built around specialized vector spaces and metadata databases. It integrates local storage and Google Photos, automatically detects faces and groups people, categorizes documents, receipts, and landscapes, performs OCR text search, filters exact and near-duplicates, and utilizes an LLM query planner to translate natural language into structured database search plans.

---

## 🏗️ Architecture & Technology Stack

Aura utilizes a monorepo architecture coordinated via Docker Compose:

```
                [ React Web Dashboard (Port 3000) ]
                               │
                               ▼
                 [ FastAPI Backend (Port 8000) ]
                               │
            ┌──────────────────┼──────────────────┐
            ▼                  ▼                  ▼
   [ Postgres + pgvector ]  [ Redis ]     [ Gemini API ]
                               ▲          (Search Planner)
                               │
                        [ Celery Worker ]
                               │
            ┌──────────────────┼──────────────────┐
            ▼                  ▼                  ▼
     [ Local Disk ]    [ Google Photos ]     [ local ML ]
    (/photos_data)          (OAuth2)      (CLIP, FaceNet, pHash)
```

### Specialized Core Vector Spaces

Rather than forcing a single vector space to handle all image semantics, Aura separates concerns into three distinct databases/indexes:

1. **Semantic Image Space (CLIP ViT-B-32 - 768 dimensions)**: Stores whole-image embeddings for conceptual similarity (e.g., searching "dog playing" matches dogs playing on a beach).
2. **Face Vector Space (MTCNN + FaceNet - 512 dimensions)**: Stores cropped face embeddings. Groups people automatically using **DBSCAN Clustering** without labels.
3. **Document Text Space (all-MiniLM-L6-v2 - 384 dimensions)**: Generates sentence embeddings of extracted OCR text (via PyTesseract) for medical prescriptions, bills, and documents.

### Deduplication Engine

* **Exact duplicates**: Handled via binary `SHA256` hashing stored with unique indexes in PostgreSQL.
* **Near duplicates** (compressed, resized, or brightened images): Handled via **Perceptual Hashing (pHash)**.
* **Scaling to 100,000+ images**: Pairwise Hamming distance comparison is computationally expensive ($O(N^2)$). Aura implements a **Locality Sensitive Hashing (LSH)** algorithm by splitting the 64-bit pHash into four 16-bit chunks, enabling fast, sub-second near-duplicate searches in $O(N)$ time.

---

## ⚡ Setup & Deployment

### Prerequisites
* [Docker](https://www.docker.com/) and Docker Compose installed.
* [Google Gemini API Key](https://aistudio.google.com/) (optional, falls back to local models if not provided).
* Google OAuth credentials (optional, for Google Photos integration).

### 1. Environment Configuration

Create a `.env` file in the root directory:

```env
# Gemini LLM Integration
GEMINI_API_KEY=your_gemini_api_key_here

# Google Photos API Integration (Optional)
GOOGLE_CLIENT_ID=your_client_id_here
GOOGLE_CLIENT_SECRET=your_client_secret_here
GOOGLE_REDIRECT_URI=http://localhost:8000/api/v1/auth/google/callback
```

### 2. How to Launch & Run

#### Option A: Run Without Docker (Fast, Lightweight Mode)
This mode runs the application using a local SQLite database (`backend/aura_photos.db`) and FastAPI's native background thread pool for processing (no Redis, Celery, or Postgres installation needed).

On **Windows**:
```powershell
./run_local.ps1
```

On **macOS/Linux**:
```bash
chmod +x run_local.sh
./run_local.sh
```

#### Option B: Run With Docker Compose (Production Stack Mode)
This mode starts the full containerized stack: PostgreSQL with pgvector, Redis, a Celery worker, and the React frontend served by Nginx.

```bash
docker-compose up --build
```
* **Web Dashboard**: [http://localhost:3000](http://localhost:3000)
* **API Documentation (Swagger)**: [http://localhost:8000/docs](http://localhost:8000/docs)

### 3. Ingesting Photos
Place your photos inside the `./photos_data` directory in the project root. In the Web Dashboard, navigate to **Settings & Sync** and click **Start Scanning Local Folder** to begin ingestion.

---

## 🧪 Automated Tests

Aura includes automated unit tests covering near-duplicate detection, search planner query generation, and DBSCAN facial clustering.

To run tests:
1. Initialize a virtual environment in the `backend` folder:
   ```bash
   cd backend
   pip install -r requirements.txt
   ```
2. Execute pytest:
   ```bash
   pytest tests/
   ```

---

## 📡 API Endpoints

### Photos
* `GET /api/v1/photos/` - List photos (supports category and storage filters, paginated).
* `POST /api/v1/photos/upload` - Direct photo upload.
* `GET /api/v1/photos/{id}` - Retrieve metadata, captions, OCR text, and detected faces.
* `GET /api/v1/photos/{id}/file` - Securely stream the image file.
* `DELETE /api/v1/photos/{id}` - Delete photo from DB and filesystem.
* `POST /api/v1/photos/sync/local` - Scan local folders for new photos.
* `POST /api/v1/photos/sync/google` - Trigger Google Photos sync page.

### Search
* `POST /api/v1/search/` - Parse natural-language queries (using LLM structured planning) and run semantic search.

### People
* `GET /api/v1/people/` - List grouped face clusters with cover image and face counts.
* `GET /api/v1/people/{id}` - List all photos containing a specific person.
* `PUT /api/v1/people/{id}` - Label/rename a person cluster.
* `POST /api/v1/people/recluster` - Manually trigger DBSCAN face clustering.

### Duplicates
* `GET /api/v1/duplicates/exact` - Get exact duplicate groups (SHA256).
* `GET /api/v1/duplicates/near` - Get near duplicate pairs within Hamming threshold (LSH-optimized pHash).
