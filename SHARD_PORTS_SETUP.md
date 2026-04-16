# 🔧 Sharding Setup - Shard Ports Configuration

## ⚠️ IMPORTANT: Shard Port Update (Confirmed with TA)

**Date:** April 17, 2026  
**Confirmed by:** TA  
**Status:** OFFICIAL ✅

---

## 📍 Shard Port Configuration

The sharding system runs on the following ports:

| Shard | Port | Service | Status |
|-------|------|---------|--------|
| **Shard 0** | **8081** | API + Database | ✅ Active |
| **Shard 1** | **8082** | API + Database | ✅ Active |
| **Shard 2** | **8083** | API + Database | ✅ Active |

---

## ❌ What Does NOT Work

- **Port 8080** - ❌ NOT WORKING (confirmed with TA)
  - Do NOT use this port for shard connections
  - All shard operations must use 8081, 8082, 8083

---

## 🚀 How to Test Shard Connectivity

### Check Shard 0 (Port 8081)
```bash
curl http://localhost:8081/admin/sharding/status
```

### Check Shard 1 (Port 8082)
```bash
curl http://localhost:8082/admin/sharding/status
```

### Check Shard 2 (Port 8083)
```bash
curl http://localhost:8083/admin/sharding/status
```

---

## 📝 Connection String Examples

### Environment Variables
```bash
export SHARD_0_URL="http://localhost:8081"
export SHARD_1_URL="http://localhost:8082"
export SHARD_2_URL="http://localhost:8083"
```

### Python Connection
```python
SHARD_URLS = {
    0: "http://localhost:8081",
    1: "http://localhost:8082",
    2: "http://localhost:8083",
}

def get_shard_url(shard_id):
    return SHARD_URLS[shard_id]
```

### FastAPI Configuration
```python
SHARD_PORTS = {
    "shard_0": 8081,
    "shard_1": 8082,
    "shard_2": 8083,
}
```

---

## 📊 Hash-Based Routing Formula

```
shard_id = user_id % 3

Examples:
- user_id = 5  → 5 % 3 = 2  → Connect to port 8083
- user_id = 10 → 10 % 3 = 1 → Connect to port 8082
- user_id = 15 → 15 % 3 = 0 → Connect to port 8081
```

---

## 🧪 Example Routing Demo

### Get user_id = 5 (Goes to Shard 2)
```bash
# Calculate: 5 % 3 = 2 (Shard 2 = Port 8083)
curl http://localhost:8083/portfolio/230005
```

### Get user_id = 10 (Goes to Shard 1)
```bash
# Calculate: 10 % 3 = 1 (Shard 1 = Port 8082)
curl http://localhost:8082/portfolio/230010
```

### Get user_id = 15 (Goes to Shard 0)
```bash
# Calculate: 15 % 3 = 0 (Shard 0 = Port 8081)
curl http://localhost:8081/portfolio/230015
```

---

## 🔗 Multi-Shard Queries (Range Queries)

When fetching all users/data across shards:

```bash
# Query all shards in sequence
curl http://localhost:8081/members  # Shard 0 results
curl http://localhost:8082/members  # Shard 1 results
curl http://localhost:8083/members  # Shard 2 results

# Application merges results from all 3 shards
```

---

## ✅ Deployment Checklist

- [ ] Shard 0 running on port **8081**
- [ ] Shard 1 running on port **8082**
- [ ] Shard 2 running on port **8083**
- [ ] All 3 shards accessible via HTTP
- [ ] Connection tests passing for all ports
- [ ] Environment variables configured correctly
- [ ] API endpoints responding on correct ports

---

## 📞 Troubleshooting

### Port Already in Use
```bash
# Find what's using the port
netstat -ano | findstr :8081

# Kill the process
taskkill /PID <PID> /F
```

### Connection Refused
```bash
# Check if shards are running
curl -v http://localhost:8081

# Check firewall rules
# Windows Firewall: Allow ports 8081, 8082, 8083
```

### Shard Not Responding
- Verify the service is started
- Check logs in shard container/process
- Restart the shard service

---

## 📚 Related Documentation

- [SHARDING_DESIGN.md](SHARDING_DESIGN.md) – Design rationale
- [SHARDING_REPORT.md](SHARDING_REPORT.md) – Full implementation report
- [SHARDING_QUICKSTART.md](SHARDING_QUICKSTART.md) – Quick start guide

---

**Last Updated:** April 17, 2026  
**Confirmed by TA:** ✅ Official  
**Status:** ACTIVE ✅
