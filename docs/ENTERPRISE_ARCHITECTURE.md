# JobAgent Enterprise Architecture

## System Overview

JobAgent Enterprise is a production-grade AI-powered career platform built with microservices architecture, featuring n8n orchestration, PostgreSQL database, Redis caching, and comprehensive monitoring.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        Load Balancer / Nginx                     │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    JobAgent Flask Application                    │
│  ┌──────────────┬──────────────┬──────────────┬──────────────┐  │
│  │   Auth API   │  Resume API  │  Job API     │  Career API   │  │
│  └──────────────┴──────────────┴──────────────┴──────────────┘  │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    N8N Automation Layer                          │
│  ┌──────────────┬──────────────┬──────────────┬──────────────┐  │
│  │   AI/ML      │  Job Search  │  Notifications│  Analytics   │  │
│  │   Services   │  Aggregator  │  Service      │  Service     │  │
│  └──────────────┴──────────────┴──────────────┴──────────────┘  │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Data Layer                                    │
│  ┌──────────────┬──────────────┬──────────────┬──────────────┐  │
│  │  PostgreSQL  │    Redis     │   Elastic    │   S3/MinIO   │  │
│  │  (Primary)   │   (Cache)    │  (Search)    │  (Storage)   │  │
│  └──────────────┴──────────────┴──────────────┴──────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. Frontend Layer
- **Technology:** HTML5, CSS3, JavaScript (Vanilla)
- **Hosting:** Nginx (static files)
- **CDN:** Optional CloudFlare integration
- **Features:**
  - Responsive design (mobile-first)
  - Progressive Web App (PWA) ready
  - Offline capability for cached data
  - Real-time updates via WebSocket

### 2. Application Layer (Flask)
- **Framework:** Flask 3.0.0
- **WSGI Server:** Gunicorn (4 workers, 2 threads each)
- **Authentication:** Flask-Login + JWT
- **API Gateway:** Flask routes with rate limiting
- **Features:**
  - RESTful API design
  - Request validation
  - Error handling middleware
  - Request/response logging

### 3. Automation Layer (N8N)
- **Purpose:** Central orchestration platform
- **Workflows:** 5 core workflows
  1. Resume Analysis (AI-powered)
  2. Job Recommendations (Daily)
  3. Interview Preparation (On-demand)
  4. Career Insights (Cached)
  5. Feedback Processing (Real-time)
- **Benefits:**
  - API keys never exposed to frontend
  - Centralized AI/ML services
  - Scalable workflow execution
  - Visual workflow management

### 4. Data Layer

#### PostgreSQL (Primary Database)
- **Version:** PostgreSQL 15+
- **Connection Pooling:** Built-in (pool_size: 10, max_overflow: 20)
- **Indexes:** Optimized for common queries
- **Tables:** 13 models
  - users, user_profiles, saved_jobs, job_applications
  - interview_history, user_preferences, user_sessions
  - audit_logs, password_reset_tokens, feedback
  - career_insight_cache, notifications, analytics

#### Redis (Cache Layer)
- **Version:** Redis 7+
- **Purpose:** Session storage, API caching, rate limiting
- **TTL:** Configurable per data type
- **Features:** Persistence enabled, password protected

#### Elasticsearch (Optional - Full-text Search)
- **Purpose:** Advanced job search, resume parsing
- **Features:** Fuzzy matching, relevance scoring

#### S3/MinIO (File Storage)
- **Purpose:** Resume uploads, generated documents
- **Features:** Versioning, lifecycle policies

### 5. AI/ML Services

#### Google Gemini (Primary)
- **Model:** gemini-pro
- **Rate Limit:** 60 requests/minute (free tier)
- **Use Cases:**
  - Resume analysis
  - Interview question generation
  - Career insights
  - Job recommendations

#### Hugging Face (Fallback)
- **Models:** Various (bart-large-mnli, etc.)
- **Rate Limit:** 1000 requests/month (free tier)
- **Use Cases:** Text classification, sentiment analysis

#### OpenAI (Optional Enhancement)
- **Model:** GPT-4
- **Use Cases:** Advanced reasoning, complex analysis

### 6. External Integrations

#### Job Search APIs
- **Adzuna:** 1000 requests/month (free)
- **JSearch (RapidAPI):** 100 requests/month (free)
- **Fallback:** Direct platform URLs (30+ platforms)

#### Email Service
- **SMTP:** Gmail, SendGrid, or AWS SES
- **Features:** Transactional emails, bulk notifications

#### Currency API (Optional)
- **Purpose:** Multi-currency salary display
- **Fallback:** Static conversion rates

## Security Architecture

### Authentication Flow
```
1. User Login → Flask-Login (session-based)
2. API Request → JWT Token (Bearer auth)
3. Token Refresh → Automatic refresh mechanism
4. Logout → Token invalidation
```

### Security Measures
- **Passwords:** Werkzeug hashing (PBKDF2)
- **JWT:** RS256 asymmetric encryption
- **Rate Limiting:** 100 requests/hour per user
- **CORS:** Whitelist origins only
- **CSRF:** Token-based protection
- **XSS:** Input sanitization, CSP headers
- **SQL Injection:** SQLAlchemy ORM (parameterized queries)
- **Secrets:** Environment variables only (never in code)

### Audit Logging
- All authentication events
- API request/response logging
- Database changes
- Admin actions
- Security incidents

## Performance Optimization

### Caching Strategy
```
L1 Cache: In-memory (Python dict) - 1 hour TTL
L2 Cache: Redis - 24 hour TTL
L3 Cache: Database (career_insight_cache table)
```

### Database Optimization
- **Indexes:** All foreign keys, frequently queried columns
- **Query Optimization:** Eager loading, pagination
- **Connection Pooling:** 10 connections, 20 overflow
- **Read Replicas:** Optional for scaling reads

### API Performance
- **Response Time Target:** <200ms (p95)
- **Caching:** 1-hour TTL for API responses
- **Compression:** Gzip enabled
- **Pagination:** 20 items per page (configurable)

## Monitoring & Observability

### Metrics (Prometheus + Grafana)
- API response times
- Database query performance
- Cache hit/miss rates
- Error rates by endpoint
- User activity metrics
- AI API usage

### Logging
- **Format:** Structured JSON
- **Levels:** DEBUG, INFO, WARNING, ERROR, CRITICAL
- **Retention:** 30 days
- **Aggregation:** ELK Stack (optional)

### Health Checks
- `/health` - Application health
- `/health/db` - Database connectivity
- `/health/redis` - Redis connectivity
- `/health/n8n` - N8N webhook status

## Deployment Architecture

### Development
```bash
docker-compose up -d
# Services: PostgreSQL, Redis, N8N, App
```

### Production
```bash
docker-compose -f docker-compose.prod.yml up -d
# Additional: Nginx, Prometheus, Grafana, SSL
```

### Scaling Strategy
```
Horizontal Scaling:
- App: 4+ workers (Gunicorn)
- Database: Read replicas
- Cache: Redis Cluster
- N8N: Multiple workers

Vertical Scaling:
- Database: Larger instance (CPU/RAM)
- Cache: More memory
- App: More CPU/RAM per worker
```

## Data Flow Examples

### Resume Analysis Flow
```
1. User uploads resume → Flask API
2. Flask validates & stores temporarily
3. Flask calls N8N webhook
4. N8N calls Gemini AI
5. AI analyzes resume
6. N8N saves to PostgreSQL
7. N8N returns results to Flask
8. Flask displays to user
```

### Job Recommendation Flow
```
1. Schedule trigger (9 AM daily)
2. N8N queries active users
3. For each user:
   - Get profile from PostgreSQL
   - Call Gemini AI for recommendations
   - Save recommendations to DB
   - Send email notification
```

## Backup & Recovery

### Database Backups
- **Frequency:** Daily automated backups
- **Retention:** 30 days
- **Method:** pg_dump with compression
- **Storage:** S3/MinIO + local

### Disaster Recovery
- **RPO:** 1 hour (maximum data loss)
- **RTO:** 4 hours (maximum downtime)
- **Strategy:** Active-passive setup
- **Testing:** Monthly recovery drills

## Cost Optimization

### Infrastructure Costs (Monthly)
- **VPS (4GB RAM, 2 CPU):** $20-40
- **PostgreSQL (Managed):** $15-30
- **Redis (Managed):** $10-20
- **N8N (Self-hosted):** $0
- **AI APIs (Free tier):** $0
- **Total:** $45-90/month

### Cost Saving Strategies
- Use free-tier APIs (Gemini, HuggingFace)
- Self-host N8N vs N8N Cloud ($20/month savings)
- SQLite for development (PostgreSQL for production)
- Compress logs and old data
- Use CDN for static assets

## Future Enhancements

### Phase 2 (3 months)
- [ ] Mobile app (React Native)
- [ ] Browser extension
- [ ] Advanced analytics dashboard
- [ ] ML-based job matching
- [ ] Resume parsing with NLP

### Phase 3 (6 months)
- [ ] Multi-language support (i18n)
- [ ] Video interview practice
- [ ] Salary negotiation AI
- [ ] Company research automation
- [ ] Professional networking features

## Technology Stack Summary

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Frontend | HTML/CSS/JS | User interface |
| Backend | Flask 3.0 | API server |
| WSGI | Gunicorn | Production server |
| Database | PostgreSQL 15 | Primary data store |
| Cache | Redis 7 | Session & API cache |
| Automation | N8N | Workflow orchestration |
| AI/ML | Google Gemini | Resume analysis, recommendations |
| Email | SMTP/SendGrid | Notifications |
| Monitoring | Prometheus + Grafana | Metrics & dashboards |
| Logging | ELK Stack | Log aggregation |
| Container | Docker | Deployment |
| Orchestration | Docker Compose | Service management |
| Proxy | Nginx | Load balancer & SSL |

## Conclusion

This enterprise architecture provides:
- ✅ Scalability (horizontal & vertical)
- ✅ Reliability (redundancy, backups)
- ✅ Security (defense in depth)
- ✅ Performance (caching, optimization)
- ✅ Maintainability (microservices, documentation)
- ✅ Cost-effectiveness (free tiers, self-hosting)
- ✅ Production-readiness (monitoring, logging)

The system is designed to handle thousands of concurrent users while maintaining sub-200ms response times and 99.9% uptime.