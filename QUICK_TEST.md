# Quick Testing - Disable Auth Temporarily

## To test the new admin pages without Keycloak setup:

### 1. Edit backend/app/routers/admin/salts.py

**Line 100-104, change:**
```python
# FROM:
router = APIRouter(
    prefix="/admin/salts",
    tags=["admin-salts"],
    dependencies=[Depends(require_admin)]  # ← Comment this line
)

# TO:
router = APIRouter(
    prefix="/admin/salts",
    tags=["admin-salts"],
    # dependencies=[Depends(require_admin)]  # ← TEMPORARILY DISABLED
)
```

### 2. Edit backend/app/routers/admin/manufacturers.py

**Line 69-73, change:**
```python
# FROM:
router = APIRouter(
    prefix="/admin/manufacturers",
    tags=["admin-manufacturers"],
    dependencies=[Depends(require_admin)]  # ← Comment this line
)

# TO:
router = APIRouter(
    prefix="/admin/manufacturers",
    tags=["admin-manufacturers"],
    # dependencies=[Depends(require_admin)]  # ← TEMPORARILY DISABLED
)
```

### 3. Restart Backend

```bash
docker-compose restart backend
```

### 4. Test Pages

Now you can access without login:
- http://localhost:3000/admin/manufacturers
- http://localhost:3000/admin/salts

### ⚠️ IMPORTANT: Re-enable Auth Before Deployment!

Revert the changes above before pushing to production.
