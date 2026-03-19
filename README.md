# LitePolis-router-particiapi

ParticiAPI-compatible router module for LitePolis.

## Overview

This module implements the [ParticiAPI](https://partici.app/) specification, providing a simpler alternative API for the ParticiApp frontend. It works alongside `LitePolis-router-default` (Polis API) and can be used interchangeably.

## Installation

```bash
litepolis-cli deploy add-deps litepolis-router-particiapi
litepolis-cli deploy sync-deps
```

## Configuration

This module exports default configuration. To customize, create a config file:

```bash
litepolis-cli deploy init-config
```

Then edit `~/.litepolis/litepolis.config`:

```ini
[litepolis_router_particiapi]
session_secret = your-secure-secret-key-here
csrf_token_expire_hours = 24
```

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

## Quick Start

1. Install all ParticiAPI modules:
```bash
litepolis-cli deploy add-deps litepolis-database-particiapi
litepolis-cli deploy add-deps litepolis-router-particiapi
litepolis-cli deploy add-deps litepolis-ui-particiapp
litepolis-cli deploy sync-deps
```

2. Start LitePolis server:
```bash
litepolis-cli deploy serve
```

## Development Testing

```bash
pip install -e .
pytest tests/
```
