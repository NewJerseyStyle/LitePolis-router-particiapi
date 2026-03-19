# LitePolis-router-particiapi

ParticiAPI-compatible router module for LitePolis.

## Overview

This module implements the [ParticiAPI](https://partici.app/) specification, providing a simpler alternative API for the ParticiApp frontend. It works alongside `LitePolis-router-default` (Polis API) and can be used interchangeably.

## ParticiAPI Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/session` | POST | Create/refresh session |
| `/api/conversations/{id}` | GET | Get conversation |
| `/api/conversations/{id}/results/` | GET | Get results (consensus/repness) |
| `/api/conversations/{id}/statements/` | GET | Get all statements |
| `/api/conversations/{id}/statements/` | POST | Submit new statement |
| `/api/conversations/{id}/participant` | GET | Get participant info |
| `/api/conversations/{id}/participant/notifications` | GET | Get notification settings |
| `/api/conversations/{id}/participant/notifications` | PUT | Set notification settings |
| `/api/conversations/{id}/votes/{tid}` | PUT | Submit vote |

## Key Differences from Polis API

1. **Endpoint Structure**: `/api/` prefix vs `/api/v3/`
2. **Session Auth**: Cookie-based sessions with CSRF tokens
3. **Error Format**: RFC 7807 Problem+JSON responses
4. **Vote Values**: AGREE=-1, NEUTRAL=0, DISAGREE=1 (inverted from Polis)
5. **Response Format**: Direct JSON objects vs PolisResponse wrapper

## Installation

```bash
pip install -e .
```

## Usage

```python
from fastapi import FastAPI
from litepolis_router_particiapi import router

app = FastAPI()
app.include_router(router, prefix="/api")
```

## Testing

```bash
pytest tests/
```
