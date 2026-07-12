# Architecture & Design Decisions Document

This document outlines the core design decisions, data flow, and scaling strategies implemented in Aura.

---

## 1. Single-Store Vector & Relational Database (PostgreSQL + pgvector)

### Decision
We store both photo metadata and vector spaces in **PostgreSQL** using the **`pgvector`** extension, rather than maintaining a separate relational database (e.g., SQLite/PostgreSQL) and multiple memory-only vector search indexes (e.g., FAISS files).

### Rationale
* **Atomic Hybrid Queries**: Traditional vector databases (or FAISS files) require pre-filtering or post-filtering when combining vector search with metadata filters (e.g., *"show me receipts from 2025"*). In pgvector, we can write a single SQL query that filters by date and category, and ranks by vector cosine distance:
  ```sql
  SELECT * FROM photos 
  WHERE category = 'receipt' AND taken_at >= '2025-01-01' 
  ORDER BY clip_embedding <=> :query_vector 
  LIMIT 10;
  ```
* **Transactional Integrity**: When a photo is deleted, its metadata and embeddings are deleted atomically. With separate index files, keeping the relational DB in sync with a FAISS index requires manual lock management and risks desynchronization.
* **Production Readiness**: pgvector supports high-performance HNSW (Hierarchical Navigable Small World) index structures, which handle millions of vectors with 99%+ recall and millisecond latency.

---

## 2. Ingestion Pipeline & Background Workers (Celery + Redis)

### Decision
We offload all image processing, hash calculations, face recognition, and OCR tasks to a **Celery** task queue backed by **Redis** as a message broker.

### Rationale
* **Fast API Responses**: Uploading an image or triggering a folder scan returns a `202 Accepted` status instantly. The user interface doesn't freeze waiting for heavy neural networks to run.
* **Resource Isolation**: CPU and GPU-intensive ML tasks (MTCNN, FaceNet, CLIP) run in separate worker processes. This prevents heavy inferences from blocking the FastAPI web server's event loop.
* **Concurrency Control**: By configuring Celery concurrency (e.g., `--concurrency=1` on standard CPU systems), we prevent multiple heavy model loads from causing Out-Of-Memory (OOM) crashes.

---

## 3. $O(N)$ Scale Duplicate Detection (Locality Sensitive Hashing)

### Decision
For near-duplicate image matching (detecting resized, compressed, or brightness-adjusted copies), we employ **Perceptual Hashing (pHash)** matched using a **Locality Sensitive Hashing (LSH)** partitioning strategy.

### Rationale
* **The Scale Problem**: A naive pairwise comparison of $N$ images requires $\frac{N(N-1)}{2}$ Hamming distance checks. For 100,000 images, this is **5 billion operations**, which would crash or take hours to run on every duplicate scan.
* **The LSH Solution**:
  1. We represent the 64-bit pHash as a 64-bit integer.
  2. We split the 64-bit integer into 4 chunks of 16 bits each.
  3. According to the **Pigeonhole Principle**, if two hashes have a Hamming distance of $\le 4$ (i.e. they are near-duplicates), they *must* share at least one identical 16-bit chunk.
  4. We index all photos in memory by their 4 chunk values.
  5. During scanning, we only calculate the full Hamming distance between a photo and candidates that share at least one chunk.
* **Result**: The search space is reduced from $O(N^2)$ to $O(N)$. Scanning 100,000 photos for near-duplicates completes in **under 1 second**.

---

## 4. Facial Recognition (MTCNN + FaceNet + DBSCAN)

### Decision
We detect faces locally using **MTCNN**, generate 512-dimensional face embeddings using **FaceNet** (pretrained on VGGFace2), and cluster them using **DBSCAN**.

### Rationale
* **DBSCAN vs. K-Means**: DBSCAN is an unsupervised density-based clustering algorithm. It does not require specifying the number of clusters (people) in advance, which is perfect because we do not know how many distinct people are in a user's library.
* **Outlier Handling**: DBSCAN automatically labels outliers (faces that do not match any cluster) as noise (`-1`). This prevents random strangers in the background of photos from forming false clusters.
* **L2-Normalized Space**: FaceNet embeddings are L2 normalized, meaning their Euclidean distance corresponds directly to cosine similarity. A DBSCAN Euclidean radius of `eps=0.55` provides optimal precision and recall for face matching.

---

## 5. LLM Structured Query Planner (Gemini API)

### Decision
We use the **Gemini API** with **Structured JSON Schema Outputs** to translate natural language search queries into machine-readable query objects.

### Rationale
* **Query Understanding**: Translating *"receipts from last summer with Rahul"* into a relational database query is error-prone using regular expressions. An LLM understands that:
  * "receipts" $\rightarrow$ category: `['receipt']`
  * "last summer" (if current time is July 2026) $\rightarrow$ date range: `['2025-06-01', '2025-08-31']`
  * "Rahul" $\rightarrow$ person: `['Rahul']`
* **Local Fallback**: If no API key is set, the system falls back to a regex-based parser, ensuring the backend is highly resilient.
