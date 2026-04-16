# 📢 Group Announcement: Shard Port Configuration (OFFICIAL)

## ✅ CONFIRMED WITH TA

**Shards are running on ports: 8081, 8082, 8083**

❌ Port 8080 does NOT work (confirmed with TA)

---

## 🔗 Quick Connection Guide

| Shard | Port |
|-------|------|
| Shard 0 | 8081 |
| Shard 1 | 8082 |
| Shard 2 | 8083 |

---

## 📝 Hash-Based Routing

```
shard_id = user_id % 3

Examples:
- user_id = 5  → port 8083 (Shard 2)
- user_id = 10 → port 8082 (Shard 1)  
- user_id = 15 → port 8081 (Shard 0)
```

---

## 🧪 Test Connection

```bash
curl http://localhost:8081/admin/sharding/status
curl http://localhost:8082/admin/sharding/status
curl http://localhost:8083/admin/sharding/status
```

All should return `200 OK` with shard information.

---

## 📚 Full Setup Guide

See `SHARD_PORTS_SETUP.md` in the repository for:
- Detailed configuration examples
- Python/FastAPI connection strings
- Troubleshooting guide
- Multi-shard query patterns

---

**GitHub Repo:** https://github.com/KeerthanVarma/Databases_Assignment4

**Status:** ✅ Official (Confirmed with TA - April 17, 2026)
