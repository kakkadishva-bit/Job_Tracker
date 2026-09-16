# JobAgent Enterprise - Deployment Guide

## Prerequisites

- Docker 20.10+
- Docker Compose 2.0+
- 4GB RAM minimum (8GB recommended)
- 20GB disk space
- Git

## Quick Start (Development)

### 1. Clone Repository
```bash
git clone <repository-url>
cd job-agent
```

### 2. Environment Setup
```bash
# Copy environment template
cp .env.example .env

# Edit .env with your configuration
nano .env
```

### 3. Start Services
```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Check service status
docker-compose ps
```

### 4. Initialize Database
```bash
# Run migrations
docker-compose exec app flask db upgrade

# Create admin user (optional)
docker-compose exec app flask shell
>>> from utils.auth import create_user_account
>>> create_user_account('admin@jobagent.com', 'admin', 'secure_password')
```

### 5. Access Application
- **Main App:** http://localhost:5000
- **N8N:** http://localhost:5678 (admin / n8n_admin_password)
- **Grafana:** http://localhost:3000 (admin / admin)
- **Prometheus:** http://localhost:9090

## Production Deployment

### 1. Server Setup
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

### 2. SSL Certificate (Let's Encrypt)
```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx -y

# Generate certificate
sudo certbot certonly --standalone -d yourdomain.com

# Certificates will be at:
# /etc/letsencrypt/live/yourdomain.com/fullchain.pem
# /etc/letsencrypt/live/yourdomain.com/privkey.pem
```

### 3. Production Environment
```bash
# Create production .env
cp .env.example .env.prod

# Edit with production values
nano .env.prod
```

Required production settings:
```env
FLASK_ENV=production
FLASK_DEBUG=False
DATABASE_URL=postgresql://user:pass@host:5432/jobagent
SECRET_KEY=<generate-secure-key-64-chars>
JWT_SECRET_KEY=<generate-secure-key-64-chars>
SMTP_USER=your-email@domain.com
SMTP_PASS=your-app-password
```

### 4. Deploy with Production Config
```bash
# Start services
docker-compose -f docker-compose.prod.yml up -d

# Monitor logs
docker-compose -f docker-compose.prod.yml logs -f app
```

### 5. Setup Backups
```bash
# Create backup script
cat > /opt/jobagent/backup.sh << 'EOF'
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
docker-compose exec -T postgres pg_dump -U jobagent jobagent | gzip > /backups/jobagent_$DATE.sql.gz
# Keep only last 30 days
find /backups -name "jobagent_*.sql.gz" -mtime +30 -delete
EOF

chmod +x /opt/jobagent/backup.sh

# Add to crontab (daily at 2 AM)
(crontab -l 2>/dev/null; "0 2 * * * /opt/jobagent/backup.sh") | crontab -
```

## N8N Workflow Setup

### 1. Access N8N
```bash
# Open browser
http://localhost:5678

# Login with:
# Username: admin
# Password: (from .env N8N_PASSWORD)
```

### 2. Import Workflows
1. Go to Workflows → Import from File
2. Import each JSON file from `n8n/workflows/`:
   - resume_analysis_workflow.json
   - job_recommendations_workflow.json
   - interview_prep_workflow.json
   - career_insights_workflow.json
   - feedback_processing_workflow.json

### 3. Configure Credentials
For each workflow, configure:

#### Google Gemini
- Go to Settings → Credentials
- Add Google AI API Key
- Paste your GEMINI_API_KEY

#### PostgreSQL
- Add PostgreSQL credentials
- Host: postgres
- Database: jobagent
- User: jobagent
- Password: (from .env)

#### Email (SMTP)
- Add Email credentials
- Host: smtp.gmail.com
- Port: 587
- User: your-email@gmail.com
- Password: your-app-password

### 4. Activate Workflows
- Open each workflow
- Click "Active" toggle
- Test with sample data

## Health Checks

### Application Health
```bash
# Check app health
curl http://localhost:5000/health

# Expected response:
# {"status": "healthy", "timestamp": "2024-01-01T00:00:00Z"}
```

### Database Health
```bash
# Check PostgreSQL
docker-compose exec postgres pg_isready -U jobagent

# Check Redis
docker-compose exec redis redis-cli ping
```

### N8N Health
```bash
# Check N8N
curl http://localhost:5678/healthz
```

## Monitoring

### Prometheus Metrics
Access http://localhost:9090 to view:
- API request rates
- Response times
- Error rates
- Database metrics

### Grafana Dashboards
Access http://localhost:3000 to view:
- Application performance
- Database performance
- Cache hit rates
- User activity

### Logs
```bash
# View application logs
docker-compose logs -f app

# View database logs
docker-compose logs -f postgres

# View N8N logs
docker-compose logs -f n8n
```

## Scaling

### Horizontal Scaling
```bash
# Scale app to 4 workers
docker-compose up -d --scale app=4

# Scale N8N workers
docker-compose up -d --scale n8n=2
```

### Database Scaling
```sql
-- Create read replica
-- (Requires PostgreSQL configuration)

-- Add indexes for common queries
CREATE INDEX CONCURRENTLY idx_users_email ON users(email);
CREATE INDEX CONCURRENTLY idx_saved_jobs_user_id ON saved_jobs(user_id);
```

## Troubleshooting

### Common Issues

#### 1. Port Already in Use
```bash
# Check what's using port 5000
sudo lsof -i :5000

# Kill process
sudo kill -9 <PID>
```

#### 2. Database Connection Issues
```bash
# Check PostgreSQL is running
docker-compose ps postgres

# Check credentials
docker-compose exec postgres psql -U jobagent -c "SELECT 1"
```

#### 3. N8N Workflow Failures
```bash
# Check N8N logs
docker-compose logs -f n8n

# Test webhook manually
curl -X POST http://localhost:5678/webhook/resume-analysis \
  -H "Content-Type: application/json" \
  -d '{"test": "data"}'
```

#### 4. Out of Memory
```bash
# Check memory usage
docker stats

# Increase Docker memory limit
# Docker Desktop → Settings → Resources → Memory
```

## Security Checklist

- [ ] Change all default passwords
- [ ] Use strong SECRET_KEY (64+ characters)
- [ ] Enable HTTPS (SSL certificates)
- [ ] Configure firewall (UFW/iptables)
- [ ] Regular security updates
- [ ] Database backups encrypted
- [ ] API rate limiting enabled
- [ ] CORS properly configured
- [ ] Audit logging enabled
- [ ] Secrets in environment variables only

## Performance Tuning

### Database
```sql
-- Optimize PostgreSQL
ALTER SYSTEM SET shared_buffers = '256MB';
ALTER SYSTEM SET effective_cache_size = '1GB';
ALTER SYSTEM SET maintenance_work_mem = '64MB';
ALTER SYSTEM SET checkpoint_completion_target = 0.9;
ALTER SYSTEM SET wal_buffers = '16MB';
ALTER SYSTEM SET default_statistics_target = 100;
ALTER SYSTEM SET random_page_cost = 1.1;
ALTER SYSTEM SET effective_io_concurrency = 200;
ALTER SYSTEM SET work_mem = '4MB';
ALTER SYSTEM SET min_wal_size = '1GB';
ALTER SYSTEM SET max_wal_size = '4GB';
```

### Redis
```conf
# redis.conf
maxmemory 512mb
maxmemory-policy allkeys-lru
save 900 1
save 300 10
save 60 10000
```

### Gunicorn
```bash
# Optimize workers
# Formula: (2 x CPU cores) + 1
gunicorn --workers 9 --threads 2 --timeout 120 app:app
```

## Maintenance

### Daily
- Monitor error logs
- Check disk space
- Review failed jobs

### Weekly
- Review performance metrics
- Check database size
- Update dependencies (if needed)

### Monthly
- Security updates
- Database optimization (VACUUM)
- Backup testing
- Performance review

## Support

For issues or questions:
1. Check documentation: `/docs`
2. Review logs: `docker-compose logs`
3. Check health endpoints
4. Contact: support@jobagent.com

## License

Proprietary - All rights reserved