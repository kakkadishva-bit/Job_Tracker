"""CSV storage for job data"""

import pandas as pd
import os
from datetime import datetime


class CSVStorage:
    """Handle CSV storage for job data"""
    
    def __init__(self):
        self.columns = [
            'job_title',
            'company_name',
            'location',
            'job_url',
            'salary',
            'description',
            'posted_date',
            'source'
        ]
    
    def save_to_csv(self, jobs: list, filename: str):
        """
        Save jobs to CSV file with clickable URLs and duplicate removal
        
        Args:
            jobs: List of job dictionaries
            filename: Output CSV filename
        """
        if not jobs:
            print("No jobs to save")
            return
        
        # Create DataFrame
        df = pd.DataFrame(jobs, columns=self.columns)
        
        # Remove duplicate jobs based on job_url
        df = df.drop_duplicates(subset=['job_url'], keep='first')
        
        # Remove rows with missing required fields
        df = df.dropna(subset=['job_title', 'company_name', 'job_url'])
        
        # Remove rows with empty strings in required fields
        df = df[(df['job_title'].str.strip() != '') & 
                (df['company_name'].str.strip() != '') & 
                (df['job_url'].str.strip() != '')]
        
        # Make job URLs clickable by creating a hyperlink column
        # This will work when opened in Excel or Google Sheets
        df['job_url'] = df['job_url'].apply(lambda x: f'=HYPERLINK("{x}", "Click Here")' if x and str(x).startswith('http') else x)
        
        # Check if file exists to append or create new
        if os.path.exists(filename):
            # Append to existing file
            existing_df = pd.read_csv(filename)
            df = pd.concat([existing_df, df], ignore_index=True)
            # Remove duplicates again after concatenation
            df = df.drop_duplicates(subset=['job_url'], keep='first')
        
        # Save to CSV
        df.to_csv(filename, index=False)
        print(f"Successfully saved {len(jobs)} jobs to {filename}")
    
    def load_from_csv(self, filename: str) -> pd.DataFrame:
        """
        Load jobs from CSV file
        
        Args:
            filename: CSV filename to load
            
        Returns:
            DataFrame with job data
        """
        if not os.path.exists(filename):
            print(f"File {filename} does not exist")
            return pd.DataFrame()
        
        return pd.read_csv(filename)
    
    def get_unique_jobs(self, jobs: list) -> list:
        """
        Remove duplicate jobs based on job URL
        
        Args:
            jobs: List of job dictionaries
            
        Returns:
            List of unique job dictionaries
        """
        seen_urls = set()
        unique_jobs = []
        
        for job in jobs:
            job_url = job.get('job_url', '')
            if job_url and job_url not in seen_urls:
                seen_urls.add(job_url)
                unique_jobs.append(job)
            elif not job_url:
                # If no URL, still include it
                unique_jobs.append(job)
        
        return unique_jobs
