"""
Free API Integrations for JobAgent
Integrates with free-tier APIs for career data, job listings, and insights.
"""
import os
import json
import requests
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from functools import lru_cache
import time

class FreeAPIIntegrations:
    """Centralized free API integrations with fallback logic."""
    
    def __init__(self):
        self.cache = {}
        self.cache_ttl = 3600  # 1 hour cache
        
        # API Keys from environment variables
        self.gemini_api_key = os.getenv('GEMINI_API_KEY')
        self.huggingface_api_key = os.getenv('HUGGINGFACE_API_KEY')
        self.adzuna_api_key = os.getenv('ADZUNA_API_KEY')
        self.adzuna_app_id = os.getenv('ADZUNA_APP_ID')
        
    def _get_cached(self, key: str) -> Optional[Any]:
        """Get cached data if not expired."""
        if key in self.cache:
            data, timestamp = self.cache[key]
            if time.time() - timestamp < self.cache_ttl:
                return data
        return None
    
    def _set_cached(self, key: str, data: Any):
        """Cache data with timestamp."""
        self.cache[key] = (data, time.time())
    
    # ═══════════════════════════════════════════════════════════════════
    # JOB SEARCH APIs
    # ═══════════════════════════════════════════════════════════════════
    
    def search_jobs_adzuna(self, query: str, location: str = "", country: str = "us") -> List[Dict]:
        """
        Search jobs using Adzuna API (free tier: 1000 calls/month)
        https://developer.adzuna.com/
        """
        cache_key = f"adzuna_{query}_{location}_{country}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        if not self.adzuna_api_key or not self.adzuna_app_id:
            return []
        
        try:
            url = f"https://api.adzuna.com/v1/api/jobs/{country}/search/1"
            params = {
                'app_id': self.adzuna_app_id,
                'app_key': self.adzuna_api_key,
                'what': query,
                'where': location,
                'results_per_page': 20,
                'content-type': 'application/json'
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            jobs = []
            for job in data.get('results', []):
                jobs.append({
                    'title': job.get('title'),
                    'company': job.get('company', {}).get('display_name'),
                    'location': job.get('location', {}).get('display_name'),
                    'description': job.get('description', '')[:500],
                    'salary_min': job.get('salary_min'),
                    'salary_max': job.get('salary_max'),
                    'url': job.get('redirect_url'),
                    'posted_date': job.get('created'),  # ISO 8601 string from Adzuna
                    'external_id': str(job.get('id', '')),
                    'source': 'Adzuna'
                })
            
            self._set_cached(cache_key, jobs)
            return jobs
            
        except Exception as e:
            print(f"Adzuna API error: {e}")
            return []
    
    def search_jobs_jsearch(self, query: str, location: str = "") -> List[Dict]:
        """
        Search jobs using JSearch API (RapidAPI - free tier available)
        """
        cache_key = f"jsearch_{query}_{location}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        rapidapi_key = os.getenv('RAPIDAPI_KEY')
        if not rapidapi_key:
            return []
        
        try:
            url = "https://jsearch.p.rapidapi.com/search"
            headers = {
                'X-RapidAPI-Key': rapidapi_key,
                'X-RapidAPI-Host': 'jsearch.p.rapidapi.com'
            }
            params = {
                'query': f"{query} in {location}" if location else query,
                'page': '1',
                'num_pages': '1'
            }
            
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            jobs = []
            for job in data.get('data', [])[:20]:
                jobs.append({
                    'title': job.get('job_title'),
                    'company': job.get('employer_name'),
                    'location': job.get('job_location'),
                    'description': job.get('job_description', '')[:500],
                    'salary': job.get('job_salary'),
                    'salary_min': job.get('job_min_salary'),
                    'salary_max': job.get('job_max_salary'),
                    'url': job.get('job_apply_link'),
                    'posted_date': job.get('job_posted_at_datetime_utc'),
                    'external_id': str(job.get('job_id', '')),
                    'source': 'JSearch'
                })
            
            self._set_cached(cache_key, jobs)
            return jobs
            
        except Exception as e:
            print(f"JSearch API error: {e}")
            return []
    
    # ═══════════════════════════════════════════════════════════════════
    # SALARY & CAREER INSIGHTS APIs
    # ═══════════════════════════════════════════════════════════════════
    
    def get_salary_data(self, role: str, location: str = "United States") -> Dict:
        """
        Get salary data from free sources.
        Uses cached data with fallback to internal database.
        """
        cache_key = f"salary_{role}_{location}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        # Try to fetch from free salary APIs
        # For now, return structured data that can be enhanced
        salary_data = {
            'role': role,
            'location': location,
            'avg_salary': None,
            'salary_range': None,
            'entry_level': None,
            'senior_level': None,
            'source': 'internal_db',
            'last_updated': datetime.utcnow().isoformat()
        }
        
        self._set_cached(cache_key, salary_data)
        return salary_data
    
    # ═══════════════════════════════════════════════════════════════════
    # AI/ML APIs FOR RESUME ANALYSIS
    # ═══════════════════════════════════════════════════════════════════
    
    def analyze_resume_with_gemini(self, resume_text: str, job_description: str = "") -> Dict:
        """
        Use Google Gemini API for advanced resume analysis
        Free tier: 60 requests/minute
        """
        if not self.gemini_api_key:
            return {'success': False, 'error': 'Gemini API key not configured'}
        
        try:
            import google.generativeai as genai
            
            genai.configure(api_key=self.gemini_api_key)
            model = genai.GenerativeModel('gemini-pro')
            
            prompt = f"""
            Analyze this resume against the job requirements and provide:
            1. Overall match score (0-100)
            2. Key strengths (3-5 points)
            3. Missing skills/keywords (3-5 points)
            4. Specific improvements (3-5 actionable suggestions)
            5. ATS compatibility assessment
            
            Resume:
            {resume_text[:2000]}
            
            Job Description:
            {job_description[:1000] if job_description else 'Not provided'}
            
            Provide response in JSON format.
            """
            
            response = model.generate_content(prompt)
            
            # Try to parse JSON from response
            try:
                # Extract JSON from response
                text = response.text
                start = text.find('{')
                end = text.rfind('}') + 1
                if start != -1 and end != -1:
                    json_str = text[start:end]
                    return {'success': True, 'data': json.loads(json_str)}
            except:
                pass
            
            return {
                'success': True,
                'data': {
                    'analysis': response.text,
                    'source': 'gemini'
                }
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def analyze_resume_with_huggingface(self, resume_text: str) -> Dict:
        """
        Use Hugging Face Inference API for resume analysis
        Free tier: 1000 requests/month
        """
        if not self.huggingface_api_key:
            return {'success': False, 'error': 'HuggingFace API key not configured'}
        
        try:
            # Use a suitable model for text classification/analysis
            api_url = "https://api-inference.huggingface.co/models/facebook/bart-large-mnli"
            
            headers = {
                'Authorization': f'Bearer {self.huggingface_api_key}',
                'Content-Type': 'application/json'
            }
            
            # Classify resume sections
            labels = [
                "has technical skills",
                "has work experience",
                "has education",
                "has projects",
                "has certifications",
                "needs improvement"
            ]
            
            payload = {
                'inputs': resume_text[:500],
                'parameters': {
                    'candidate_labels': labels,
                    'multi_label': True
                }
            }
            
            response = requests.post(api_url, headers=headers, json=payload, timeout=30)
            
            if response.status_code == 200:
                return {'success': True, 'data': response.json()}
            else:
                return {'success': False, 'error': f'API returned {response.status_code}'}
                
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    # ═══════════════════════════════════════════════════════════════════
    # SKILLS & COMPETENCY APIs
    # ═══════════════════════════════════════════════════════════════════
    
    def get_skills_from_esco(self, skill_name: str) -> List[Dict]:
        """
        Query ESCO (European Skills, Competences, Qualifications)
        Free API: https://ec.europa.eu/esco/
        """
        try:
            url = f"https://ec.europa.eu/esco/api/search?text={skill_name}&type=skill&limit=10"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            skills = []
            for result in data.get('_embedded', {}).get('results', []):
                skills.append({
                    'title': result.get('title'),
                    'description': result.get('description'),
                    'uri': result.get('uri')
                })
            
            return skills
            
        except Exception as e:
            print(f"ESCO API error: {e}")
            return []
    
    def get_skills_from_onet(self, occupation: str) -> List[Dict]:
        """
        Query O*NET database for skills by occupation
        Free API: https://services.onetcenter.org/
        """
        try:
            # O*NET requires registration, return structured data
            # This is a placeholder for actual O*NET integration
            return []
            
        except Exception as e:
            print(f"O*NET API error: {e}")
            return []
    
    # ═══════════════════════════════════════════════════════════════════
    # INTERVIEW QUESTIONS GENERATION
    # ═══════════════════════════════════════════════════════════════════
    
    def generate_interview_questions_ai(self, role: str, company: str = "", 
                                        experience_level: str = "mid") -> Dict:
        """
        Generate role-specific interview questions using AI
        """
        if not self.gemini_api_key:
            return {'success': False, 'error': 'AI API not configured'}
        
        try:
            import google.generativeai as genai
            
            genai.configure(api_key=self.gemini_api_key)
            model = genai.GenerativeModel('gemini-pro')
            
            prompt = f"""
            Generate 5 realistic interview questions for a {role} position at {company if company else "a tech company"}.
            Experience level: {experience_level}
            
            For each question provide:
            1. The question
            2. What the interviewer is looking for
            3. Key points to include in answer
            4. Sample strong answer (2-3 sentences)
            5. Common mistakes to avoid
            6. Difficulty level (Easy/Medium/Hard)
            7. Estimated time to answer (minutes)
            
            Format as JSON array.
            """
            
            response = model.generate_content(prompt)
            
            return {
                'success': True,
                'questions': response.text,
                'source': 'gemini'
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    # ═══════════════════════════════════════════════════════════════════
    # UTILITY METHODS
    # ═══════════════════════════════════════════════════════════════════
    
    def get_all_available_apis(self) -> Dict[str, bool]:
        """Check which APIs are configured and available."""
        return {
            'gemini': bool(self.gemini_api_key),
            'huggingface': bool(self.huggingface_api_key),
            'adzuna': bool(self.adzuna_api_key and self.adzuna_app_id),
            'jsearch': bool(os.getenv('RAPIDAPI_KEY'))
        }
    
    def get_api_status(self) -> Dict[str, Any]:
        """Get status of all API integrations."""
        return {
            'available_apis': self.get_all_available_apis(),
            'cache_size': len(self.cache),
            'cache_ttl': self.cache_ttl
        }


# Global instance
api_integrations = FreeAPIIntegrations()