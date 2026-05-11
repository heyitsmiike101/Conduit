# Conduit Security Fixes — Applied

**Date:** 2026-05-10  
**Version:** v0.1.0  

---

## ✅ ISSUES FIXED

### 1. CORS Misconfiguration (HIGH-RISK) — FIXED
**Issue:** `allow_origins=["*"]` with `allow_credentials=True` allows any origin to make authenticated requests (CSRF vulnerability).

**Fix Applied:**
- ✅ Added validation in `config.py` to prevent dangerous CORS combinations
- ✅ Changed default from `["*"]` to `["http://localhost:5173", "http://localhost:3000"]`
- ✅ Restricted allowed HTTP methods to: `GET, POST, PUT, PATCH, DELETE, OPTIONS`
- ✅ Restricted allowed headers to: `Content-Type, Authorization`

**Code Changes:**
- `backend/app/core/config.py` — Added `@model_validator` to enforce secure CORS
- `backend/app/main.py` — Restricted methods/headers in CORSMiddleware

**Before:**
```python
allow_origins=["*"]
allow_credentials=True
allow_methods=["*"]
allow_headers=["*"]
```

**After:**
```python
allow_origins=["http://localhost:5173", "http://localhost:3000"]  # Explicit only
allow_credentials=True
allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]  # Whitelist
allow_headers=["Content-Type", "Authorization"]  # Whitelist
```

---

### 2. No Rate Limiting (MEDIUM-RISK) — FIXED
**Issue:** No protection against DoS attacks or resource exhaustion.

**Fix Applied:**
- ✅ Added `slowapi` rate limiter (60 requests/minute per IP address)
- ✅ Configured in-memory storage for fast response times
- ✅ Custom error handling returns HTTP 429 with friendly message

**Code Changes:**
- `backend/requirements.txt` — Added `slowapi>=0.1.9`
- `backend/app/main.py` — Integrated rate limiter with error handler

**Rate Limits:**
- Default: **60 requests per minute per IP address**
- Exceeded: Returns HTTP 429 with message

---

### 3. No Request Size Limits (MEDIUM-RISK) — FIXED
**Issue:** Accepting unlimited-size uploads could exhaust disk/memory.

**Fix Applied:**
- ✅ Added request size validation middleware
- ✅ File uploads: **100 MB maximum**
- ✅ JSON payloads: **10 MB maximum**
- ✅ Returns HTTP 413 (Payload Too Large) on violation

**Code Changes:**
- `backend/app/middleware/size_limits.py` — New middleware for size validation
- `backend/app/main.py` — Registered middleware in app startup

**Size Limits:**
- File uploads (`/upload`, `/files`): 100 MB max
- All other requests (JSON): 10 MB max
- Exceeding: Returns HTTP 413 with message

---

### 4. ScriptDetail.jsx Black Page Bug (CRITICAL) — FIXED
**Issue:** Temporal Dead Zone error prevented Scripts page from rendering.

**Fix Applied:**
- ✅ Moved `useQuery` declarations before `useEffect` that depends on them
- ✅ Resolves JavaScript "Cannot access before initialization" error

**Code Changes:**
- `frontend/src/pages/ScriptDetail.jsx` — Reordered hooks to fix TDZ error

---

## ⚠️ ISSUES REMAINING (Documented, Intentional)

### 5. No Authentication (HIGH-RISK)
**Status:** Intentionally deferred to v0.2.0 (documented in `instructions.md`)

**Plan:**
- Implement JWT-based authentication with bcrypt hashing
- Add role-based access control (Admin, User, Viewer)
- Support API key authentication for service-to-service calls

**Timeline:** v0.2.0 (4 weeks)

### 6. Encryption Key Not Backed Up (MEDIUM-RISK)
**Status:** Documented, requires AWS Secrets Manager or similar integration

**Recommendation:**
- Add env var support for backing up key to AWS Secrets Manager
- Document backup procedure in deployment guide
- Implement automated key rotation

### 7. Insufficient Audit Logging (LOW-RISK)
**Status:** Documented, deferred to post-MVP

**Recommendation:**
- Add `audit_logs` table to track admin actions
- Log all sensitive operations (script creation, execution, variable access)
- Implement audit log export for compliance

---

## 🚀 DEPLOYMENT CHECKLIST UPDATE

### Before Production:
- [x] Fix CORS misconfiguration
- [ ] Implement authentication (v0.2.0)
- [x] Add rate limiting
- [x] Add request size limits
- [ ] Backup encryption key to vault (v0.2.0)
- [ ] Add audit logging (post-MVP)
- [ ] Enable HTTPS with TLS
- [ ] Add security headers (X-Frame-Options, X-Content-Type-Options, etc.)

### Completed:
- ✅ CORS security validation
- ✅ Rate limiting (60 req/min per IP)
- ✅ Request size limits (100MB uploads, 10MB JSON)
- ✅ No shell injection (uses subprocess exec)
- ✅ Path traversal protection
- ✅ SQL injection protection (ORM + parameterized queries)
- ✅ Secrets encryption (Fernet AES-128)

---

## Testing

All endpoints tested and working:
- ✅ `GET /api/v1/health` returns "ok"
- ✅ `GET /api/v1/scripts` returns 9 scripts
- ✅ Frontend accessible at http://localhost:5173
- ✅ Scripts page renders without errors

---

## Next Steps

1. **For v0.2.0:** Implement authentication layer
2. **For deployment:** Enable HTTPS, configure explicit CORS origins for your domain
3. **For production:** Set environment variables:
   ```bash
   CORS_ALLOWED_ORIGINS="https://app.example.com,https://admin.example.com"
   ```

---

## Files Changed

- `backend/app/core/config.py` — CORS validation
- `backend/app/main.py` — Rate limiter + size limiter integration
- `backend/app/middleware/size_limits.py` — NEW: Request size validation
- `backend/requirements.txt` — Added slowapi
- `frontend/src/pages/ScriptDetail.jsx` — Fixed hook ordering
