# Architecture Guide — TypeScript + Python Server

---

## Big Picture — What We Are Building

```
Client (Frontend)
      ↓
TypeScript Server  ←─── Smart Layer
      │                  - Accepts all requests
      │                  - Manages queue
      │                  - Caches final results
      │                  - Tracks job status
      │                  - Rate limits users
      ↓
Python Server      ←─── Dumb Compute Layer
                         - Receives ONE job at a time
                         - Processes it fully
                         - Returns JSON result
                         - Forgets everything
                         - No state, no cache
```

The core idea is simple:
- TypeScript server is the **brain** — it decides when and what to send to Python
- Python server is the **muscle** — it only does computation, nothing else

---

## Why This Split Matters

Right now Python server does everything:
- Accepts requests
- Manages its own cache
- Processes everything in parallel
- Holds state between requests

This causes memory overload because:
- Multiple heavy jobs run simultaneously
- Cache stores huge numpy arrays (150+ MB each)
- No control over how many requests Python handles at once

After this split:
- Python never holds more than ONE job in memory at a time
- Cache stores only final JSON (kilobytes, not megabytes)
- TypeScript controls the entire flow

---

## TypeScript Server — Full Responsibility Breakdown

### 1. Request Queue

```
What it is:
  A waiting list of jobs that need to go to Python

How it works:
  - User sends request → TS adds it to queue
  - Queue checks if Python is free
  - If free  → send job to Python immediately
  - If busy  → job waits in queue
  - When Python finishes → pick next job from queue

What it stores per job:
  - jobId         → unique identifier (UUID)
  - userId        → who requested it
  - requestBody   → the polygon / params sent by user
  - status        → pending / processing / done / failed
  - createdAt     → when it was added
  - startedAt     → when Python started processing
  - finishedAt    → when result came back

Why this fixes the problem:
  - Python NEVER gets 2 jobs simultaneously
  - Memory spike is always max ONE request worth
  - No more OOM from concurrent users
```

### 2. Job Status Store

```
What it is:
  A place to track every job's current state

Why it is needed:
  - When queue is busy, user needs to know their job is waiting
  - User can poll "is my job done yet?"
  - If Python crashes mid-job, TS knows to retry

Flow from user's perspective:
  User sends request
        ↓
  TS returns immediately with:
    { jobId: "abc-123", status: "pending", position: 2 }
        ↓
  User polls  GET /job/abc-123
        ↓
  TS checks status store
        ↓
  Returns current status:
    pending   → "still in queue, position 2"
    processing → "Python is working on it"
    done      → returns full result
    failed    → returns error message

Storage options:
  - Simple: in-memory Map/object (lost on restart, fine for MVP)
  - Better: Redis (survives restarts, shareable across instances)
```

### 3. Response Cache

```
What it is:
  Stores FINAL JSON results so same polygon is never sent to Python twice

What it stores:
  - Key   → hash of polygon coordinates + request params
  - Value → final JSON response (GeoJSON features + metadata)
  - TTL   → 15-30 minutes (configurable)

What it does NOT store:
  - numpy arrays       ← Python's old mistake
  - raw raster data    ← never needed outside Python
  - intermediate state ← not needed

Why this is safe:
  - Final JSON for a 300 km² polygon analysis = ~500 KB to 2 MB
  - Compare to Python's old cache = 150+ MB numpy arrays
  - 100x smaller, same usefulness

Flow:
  Request comes in
        ↓
  TS checks cache with polygon hash as key
        ↓
  Hit?  → return cached JSON immediately
          Python never called
          Response time: milliseconds
        ↓
  Miss? → add to queue → Python processes → store result → return to user
```

### 4. Rate Limiter

```
What it is:
  Controls how many requests a single user can send in a time window

Why it is needed:
  - One user hammering the API fills the queue for everyone
  - Prevents accidental infinite loops from frontend bugs
  - Protects Python from a single bad actor

Simple rules to implement:
  - Max 5 requests per user per minute
  - Max 2 large polygon requests (>100 km²) per user per 5 minutes
  - If exceeded → return 429 Too Many Requests immediately

How to identify users:
  - By API key (best)
  - By IP address (simpler)
  - By session token
```

### 5. Python Health Monitor

```
What it is:
  TS periodically checks if Python server is alive and responsive

Why it is needed:
  - If Python crashes, queue keeps growing silently
  - Users get stuck waiting with no feedback
  - TS needs to know when to stop sending jobs

How it works:
  Every 30 seconds:
        ↓
  TS calls Python GET /health
        ↓
  Python responds with:
    { status: "ok", memory_mb: 245, current_job: "processing" / "idle" }
        ↓
  If no response in 5 seconds:
    → mark Python as unavailable
    → pause queue
    → return 503 to new requests
    → retry health check every 10 seconds
        ↓
  When Python recovers:
    → resume queue
```

---

## Python Server — Full Responsibility Breakdown

### 1. Stateless Processing

```
What stateless means:
  - Every request is treated as if it is the first request ever
  - No memory of previous requests
  - No cache
  - No stored state between calls
  - When request finishes, ALL memory related to it is freed

Why this is important:
  - Python memory stays low and predictable
  - No memory accumulates over time
  - Restart anytime without losing anything important
    (TS holds all state now)

What Python does per request:
  Receive job from TS
        ↓
  Validate inputs
        ↓
  Call GEE / SoilGrids / ML model
        ↓
  Process arrays → build GeoJSON
        ↓
  Free all intermediate arrays from memory
        ↓
  Return final JSON to TS
        ↓
  Forget everything
```

### 2. Memory Cleanup Per Request

```
Why explicit cleanup is needed:
  Python GC (garbage collector) does not free memory immediately
  when a function returns. It runs on its own schedule.
  
  Without explicit cleanup:
    Request 1 finishes → 150 MB still in RAM
    Request 2 starts   → another 150 MB allocated
    Overlap            → 300 MB briefly, may OOM

  With explicit cleanup:
    After building GeoJSON → delete numpy arrays manually
    Call gc.collect()      → force GC to run now
    Request 2 starts       → only ~20 MB leftover from request 1

What needs cleanup after each request:
  - label array (raster labels)
  - probs dict (9 probability band arrays)
  - indices dict (5 spectral index arrays)
  - masks dict (9 boolean arrays derived from label)
  - All intermediate shapely geometry objects
```

### 3. Sequential Processing Guarantee

```
What this means:
  Python should only ever be doing ONE heavy job at a time

How Python enforces this:
  - A simple flag or semaphore with limit=1
  - If somehow two requests arrive simultaneously
    (TS bug or direct API call):
    → second request waits
    → or returns 503 "server busy, use TS queue"

Why TS handles this but Python also guards:
  - Defense in depth
  - Protects against direct API calls bypassing TS
  - Protects against TS bugs that send two jobs at once
```

### 4. Health Endpoint

```
What it exposes:
  GET /health

What it returns:
  {
    status: "ok" or "busy",
    current_memory_mb: 245,
    job_status: "idle" or "processing",
    uptime_seconds: 3600
  }

Why it is needed:
  - TS uses this to decide whether to send next job
  - Render / deployment platform uses it for health checks
  - Easy debugging — see memory usage without SSH
```

### 5. Change Detection — Sequential Fetch

```
Current problem:
  Period A arrays fetched → held in memory
  Period B arrays fetched → held in memory
  Both alive simultaneously → 2x memory

Fix:
  Fetch Period A
        ↓
  Extract only what is needed (label array, NDVI values)
        ↓
  Delete Period A raw arrays immediately
        ↓
  Force GC
        ↓
  Fetch Period B
        ↓
  Do comparison with Period A extracted values
        ↓
  Delete Period B raw arrays
        ↓
  Return result

Memory impact:
  Before: ~34 MB × 2 = 68 MB simultaneously
  After:  ~34 MB + ~5 MB (extracted values) = 39 MB peak
```

---

## Communication Between TS and Python

### Current (Synchronous — Problem)

```
TS sends request to Python
        ↓
TS waits..................... (30-120 seconds for large polygon)
        ↓
Python responds
        ↓
TS returns to user

Problem:
  TS connection held open for 2 minutes
  HTTP timeout risk
  User has no feedback during wait
  TS cannot accept queue logic while waiting
```

### Proposed (Async — Solution)

```
Option A — Polling (Simpler to implement)

  TS sends job to Python with jobId
        ↓
  Python acknowledges: { jobId: "abc", status: "accepted" }
        ↓
  Python processes in background
        ↓
  TS polls Python every 5 seconds: GET /job/abc/status
        ↓
  Python returns "processing" until done
        ↓
  Python returns full result when done
        ↓
  TS caches result, marks job done, notifies user

---

Option B — Callback (Cleaner)

  TS sends job to Python with a callback URL
        ↓
  Python acknowledges immediately
        ↓
  Python processes in background
        ↓
  When done, Python calls back TS: POST /internal/job-complete
        ↓
  TS receives result, caches it, marks job done

---

Which to choose:
  Option A (Polling) → easier to implement, good for MVP
  Option B (Callback) → cleaner, better for production
```

---

## Full Request Flow After Changes

```
User sends POST /soil/polygon with large polygon
        ↓
TypeScript Server receives request
        ↓
Step 1: Rate limit check
  → User exceeded limit? Return 429 immediately
        ↓
Step 2: Cache check
  → Same polygon requested before? Return cached JSON immediately
  → Cache hit = Python never involved
        ↓
Step 3: Add to queue
  → Generate jobId
  → Store in job status store as "pending"
  → Return to user: { jobId: "abc-123", status: "pending", position: 1 }
        ↓
Step 4: Queue processor checks Python health
  → Python busy? Job waits in queue
  → Python free? Send job to Python
        ↓
Step 5: Update job status to "processing"
        ↓
Step 6: Python receives job
  → Validates polygon
  → Calls GEE (label + probs + indices arrays)
  → Builds GeoJSON
  → Deletes arrays, runs GC
  → Returns final JSON
        ↓
Step 7: TypeScript receives result
  → Stores in response cache (keyed by polygon hash)
  → Updates job status to "done" with result
  → Picks next job from queue
        ↓
Step 8: User polls GET /job/abc-123
  → TS returns full result from job status store
        ↓
Done. Python memory fully freed. Cache holds only JSON.
```

---

## Summary — Who Does What

```
TYPESCRIPT SERVER
├── Accept all incoming requests
├── Rate limit per user
├── Check response cache before involving Python
├── Manage job queue (max 1 job to Python at a time)
├── Track job status (pending / processing / done / failed)
├── Store final JSON results in cache
├── Monitor Python health
└── Handle retries if Python fails

PYTHON SERVER
├── Receive one job at a time from TS
├── Validate inputs
├── Call GEE for satellite data
├── Call SoilGrids for soil data
├── Run ML models for crop recommendation
├── Build GeoJSON from raster arrays
├── Clean up memory after each job (del + gc)
├── Return final JSON to TS
└── Expose health endpoint
```

---

## What This Achieves

| Problem Before | After This Architecture |
|---|---|
| Python memory spikes from concurrent users | Max 1 job at a time — memory spike is predictable |
| Cache storing 150 MB numpy arrays | Cache stores 500 KB JSON only |
| No user feedback during 2 min processing | User gets jobId, can poll status anytime |
| Python OOM kills whole server | Python crash only affects current job, TS retries |
| No rate limiting | Per-user rate limit at TS layer |
| Cache entries not freed after TTL | TS cache stores JSON — trivial memory footprint |
| No visibility into what is processing | Job status store shows full queue state |