# N8N Automation Workflows for JobAgent

This document outlines all N8N automation workflows for JobAgent platform.

## Prerequisites

1. Install N8N: `npm install n8n -g`
2. Start N8N: `n8n start`
3. Access N8N UI: http://localhost:5678

## Workflow 1: Resume Analysis & Feedback

**Trigger:** Webhook from JobAgent  
**Schedule:** On-demand (when user analyzes resume)

### Nodes:
1. **Webhook** - Receives resume data from JobAgent
2. **AI Agent (Gemini)** - Analyzes resume with advanced AI
3. **Code** - Processes and structures the analysis
4. **PostgreSQL** - Saves analysis to database
5. **Email** - Sends results to user (optional)

### Configuration:
```json
{
  "webhook": {
    "path": "/webhook/resume-analysis",
    "methods": ["POST"]
  },
  "ai_prompt": "Analyze this resume and provide ATS score, strengths, weaknesses, and actionable improvements...",
  "database_table": "resume_analyses"
}
```

## Workflow 2: Job Recommendation Engine

**Trigger:** Schedule (Daily at 9 AM)  
**Action:** Send personalized job recommendations

### Nodes:
1. **Schedule Trigger** - Daily at 9 AM
2. **PostgreSQL** - Get user profiles and preferences
3. **HTTP Request** - Fetch jobs from multiple platforms
4. **AI Agent** - Match jobs to user profile
5. **Filter** - Remove irrelevant jobs
6. **Email** - Send personalized recommendations
7. **PostgreSQL** - Log recommendations sent

### Configuration:
```json
{
  "schedule": "0 9 * * *",
  "job_sources": ["linkedin", "indeed", "glassdoor", "naukri"],
  "match_threshold": 70,
  "max_recommendations": 10
}
```

## Workflow 3: Interview Question Generator

**Trigger:** Webhook from JobAgent  
**Schedule:** On-demand

### Nodes:
1. **Webhook** - Receives role and company
2. **AI Agent (Gemini)** - Generates role-specific questions
3. **Code** - Structures questions by round type
4. **PostgreSQL** - Caches questions for reuse
5. **Webhook Response** - Returns questions to JobAgent

### Configuration:
```json
{
  "webhook": "/webhook/interview-questions",
  "question_types": ["technical", "hr", "behavioral", "coding"],
  "questions_per_type": 5,
  "cache_ttl_hours": 24
}
```

## Workflow 4: Career Insights Updater

**Trigger:** Schedule (Weekly on Monday)  
**Action:** Update career insights from free APIs

### Nodes:
1. **Schedule Trigger** - Weekly Monday 2 AM
2. **HTTP Request** - Fetch from Adzuna API
3. **HTTP Request** - Fetch from JSearch API
4. **Code** - Aggregate and normalize data
5. **PostgreSQL** - Update career_insight_cache table
6. **Slack/Email** - Notify admin of updates

### Configuration:
```json
{
  "schedule": "0 2 * * 1",
  "apis": ["adzuna", "jsearch", "huggingface"],
  "roles_to_update": ["python developer", "frontend developer", "data scientist"],
  "cache_ttl_hours": 168
}
```

## Workflow 5: Feedback Processing

**Trigger:** Webhook from JobAgent  
**Schedule:** Real-time

### Nodes:
1. **Webhook** - Receives feedback submission
2. **Code** - Validates and categorizes feedback
3. **AI Agent** - Analyzes sentiment and priority
4. **PostgreSQL** - Saves to feedback table
5. **IF** - Check if rating <= 2 (negative)
6. **Slack** - Alert team for urgent issues
7. **Email** - Send acknowledgment to user

### Configuration:
```json
{
  "webhook": "/webhook/feedback",
  "sentiment_analysis": true,
  "urgent_threshold": 2,
  "auto_response": true
}
```

## Workflow 6: Notification System

**Trigger:** Schedule (Every 6 hours)  
**Action:** Send pending notifications

### Nodes:
1. **Schedule Trigger** - Every 6 hours
2. **PostgreSQL** - Get unread notifications
3. **Filter** - Check if user preferences allow
4. **Switch** - Route by notification type
5. **Email** - Send email notifications
6. **PostgreSQL** - Mark as sent

### Configuration:
```json
{
  "schedule": "0 */6 * * *",
  "notification_types": ["job_alert", "interview_reminder", "career_tip"],
  "batch_size": 100
}
```

## Workflow 7: Application Tracking

**Trigger:** Webhook from JobAgent  
**Schedule:** Real-time

### Nodes:
1. **Webhook** - Receives application status update
2. **PostgreSQL** - Update job_applications table
3. **IF** - Check if status changed to 'interview'
4. **AI Agent** - Generate interview prep materials
5. **Email** - Send interview prep to user
6. **PostgreSQL** - Create notification

### Configuration:
```json
{
  "webhook": "/webhook/application-update",
  "auto_interview_prep": true,
  "reminder_before_interview": "24h"
}
```

## Workflow 8: Weekly Digest

**Trigger:** Schedule (Weekly Sunday 10 AM)  
**Action:** Send weekly career progress digest

### Nodes:
1. **Schedule Trigger** - Sunday 10 AM
2. **PostgreSQL** - Get user activity for the week
3. **Code** - Calculate metrics and insights
4. **AI Agent** - Generate personalized insights
5. **Email** - Send formatted digest
6. **PostgreSQL** - Log digest sent

### Configuration:
```json
{
  "schedule": "0 10 * * 0",
  "metrics": ["resumes_analyzed", "jobs_saved", "applications_sent", "skills_learned"],
  "insights": ["top_skills_demanded", "salary_trends", "learning_recommendations"]
}
```

## Setup Instructions

### 1. Environment Variables
Create `.env.n8n` file:
```bash
# Database
N8N_DB_TYPE=postgresql
N8N_DB_POSTGRESDB_HOST=localhost
N8N_DB_POSTGRESDB_PORT=5432
N8N_DB_POSTGRESDB_DATABASE=jobagent
N8N_DB_POSTGRESDB_USER=jobagent_user
N8N_DB_POSTGRESDB_PASSWORD=your_password

# APIs
GEMINI_API_KEY=your_gemini_key
HUGGINGFACE_API_KEY=your_hf_key
ADZUNA_API_KEY=your_adzuna_key
ADZUNA_APP_ID=your_adzuna_app_id

# Email (SMTP)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASS=your_app_password

# Slack (optional)
SLACK_WEBHOOK_URL=your_slack_webhook
```

### 2. Install N8N
```bash
# Using npm
npm install n8n -g

# Using Docker
docker run -it --rm \
  --name n8n \
  -p 5678:5678 \
  -v ~/.n8n:/home/node/.n8n \
  n8nio/n8n
```

### 3. Import Workflows
1. Open N8N UI: http://localhost:5678
2. Go to Workflows → Import from File
3. Import each workflow JSON file
4. Configure credentials for each node
5. Activate workflows

### 4. Webhook Endpoints
Update JobAgent `config.py`:
```python
N8N_WEBHOOK_URL = os.getenv('N8N_WEBHOOK_URL', 'http://localhost:5678/webhook')
```

## API Integration Points

### JobAgent → N8N
```python
# Send resume for analysis
requests.post(f"{N8N_WEBHOOK_URL}/resume-analysis", json={
    'resume_text': resume_text,
    'user_id': user_id,
    'target_role': target_role
})

# Request interview questions
requests.post(f"{N8N_WEBHOOK_URL}/interview-questions", json={
    'role': role,
    'company': company,
    'experience_level': experience_level
})

# Submit feedback
requests.post(f"{N8N_WEBHOOK_URL}/feedback", json={
    'user_id': user_id,
    'rating': rating,
    'comment': comment,
    'category': category
})
```

### N8N → JobAgent
```python
# Receive processed data
@app.route('/webhook/n8n-callback', methods=['POST'])
def n8n_callback():
    data = request.json
    # Process and store in database
    return jsonify({'status': 'success'})
```

## Monitoring & Maintenance

### 1. Monitor Workflow Execution
- Check N8N execution logs
- Monitor error rates
- Set up alerts for failures

### 2. Database Maintenance
```sql
-- Clean old cache entries
DELETE FROM career_insight_cache WHERE expires_at < NOW();

-- Archive old analytics
INSERT INTO analytics_archive SELECT * FROM analytics 
WHERE created_at < NOW() - INTERVAL '90 days';
DELETE FROM analytics WHERE created_at < NOW() - INTERVAL '90 days';
```

### 3. Performance Optimization
- Enable workflow execution caching
- Use PostgreSQL for production (not SQLite)
- Set up Redis for N8N queue
- Monitor API rate limits

## Cost Estimate

### Free Tier APIs:
- Google Gemini: 60 requests/minute (free)
- Hugging Face: 1000 requests/month (free)
- Adzuna: 1000 requests/month (free)
- JSearch: 100 requests/month (free tier)

### N8N Hosting:
- Self-hosted: Free (just server costs)
- N8N Cloud: $20/month (starter)

### Total Monthly Cost: $0-20

## Security Considerations

1. **API Keys**: Store in N8N environment variables, never in code
2. **Webhooks**: Validate signatures, use HTTPS
3. **Database**: Use connection pooling, enable SSL
4. **Rate Limiting**: Implement on all external API calls
5. **Data Privacy**: Anonymize user data before AI processing

## Troubleshooting

### Common Issues:
1. **Webhook timeouts**: Increase timeout to 30s
2. **API rate limits**: Implement caching and retry logic
3. **Database connection**: Use connection pooling
4. **Memory issues**: Increase N8N memory limit

### Debug Mode:
```bash
N8N_LOG_LEVEL=debug n8n start
```

## Next Steps

1. Set up PostgreSQL database
2. Configure N8N with environment variables
3. Import and test each workflow
4. Set up monitoring and alerts
5. Document custom workflows for your team