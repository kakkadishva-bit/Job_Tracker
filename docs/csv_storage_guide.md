# CSV Storage Guide

## Overview
The Job Agent uses pandas DataFrame to store job data in CSV format with clickable URLs for easy access to job postings.

## How CSV Storage Works

### 1. Data Collection
- All scrapers (Naukri, RemoteOK, Wellfound) return job data as dictionaries
- Each job dictionary contains: job_title, company_name, location, job_url, salary, description, posted_date, source
- Jobs are collected in a list and passed to the CSV storage handler

### 2. CSV Storage Process
```python
from storage.csv_storage import CSVStorage

# Initialize storage
storage = CSVStorage()

# Save jobs to CSV
storage.save_to_csv(jobs_list, 'jobs.csv')
```

### 3. Clickable URLs
The CSV storage automatically converts job URLs into clickable hyperlinks using Excel's HYPERLINK formula:
```python
df['job_url'] = df['job_url'].apply(lambda x: f'=HYPERLINK("{x}", "Click Here")' if x and str(x).startswith('http') else x)
```

When you open the CSV file in Excel or Google Sheets, the job URLs will appear as "Click Here" links that open the job posting when clicked.

### 4. File Handling
- If the CSV file exists, new jobs are appended to existing data
- If the file doesn't exist, a new file is created
- Duplicate jobs are filtered based on job URLs

### 5. CSV Output Format
The CSV file contains the following columns:

| Column | Description |
|--------|-------------|
| job_title | Title of the job position |
| company_name | Name of the hiring company |
| location | Job location |
| job_url | Clickable link to job posting |
| salary | Salary/compensation information |
| description | Job description |
| posted_date | When the job was posted |
| source | Platform (Naukri/RemoteOK/Wellfound) |

## Usage Examples

### Basic Usage
```bash
python main.py --job-role "Software Engineer" --location "Bangalore" --output jobs.csv
```

### Custom Output File
```bash
python main.py --job-role "Data Scientist" --output my_jobs.csv --limit 20
```

### With HTML Caching
```bash
python main.py --job-role "Product Manager" --cache-html --save-html
```

## Viewing the CSV File

### In Excel
1. Double-click the CSV file to open in Excel
2. The job_url column will show "Click Here" text
3. Click on "Click Here" to open the job posting in your browser

### In Google Sheets
1. Upload the CSV file to Google Drive
2. Open with Google Sheets
3. The job_url column will show "Click Here" text
4. Click on "Click Here" to open the job posting

### As Plain Text
If you prefer to see the actual URLs instead of clickable links, you can:
1. Open the CSV file in a text editor
2. The job_url column will contain the actual URLs
3. Copy and paste URLs into your browser

## Troubleshooting

### Permission Error
If you get a "Permission denied" error when saving to CSV:
- Close the CSV file if it's currently open in Excel or another application
- Use a different filename: `--output new_jobs.csv`
- Ensure you have write permissions in the directory

### URLs Not Clickable
If URLs are not clickable in Excel:
- Make sure you're opening the file directly in Excel (not importing)
- The HYPERLINK formula only works in Excel and Google Sheets
- In other applications, you'll see the raw formula text

### Empty CSV File
If the CSV file is empty:
- Check if any scrapers found jobs (look at console output)
- Verify your internet connection
- Some platforms may have anti-scraping measures
- Try with a different job title or location

## Data Validation

The CSV storage includes automatic validation:
- Required fields: job_title, company_name, job_url
- Invalid jobs are filtered out before saving
- Missing fields are logged as warnings
- Duplicate jobs are removed based on job URLs

## Performance Considerations

- Large CSV files (>10,000 jobs) may take longer to load
- Consider splitting into multiple files for large datasets
- Use the `--limit` parameter to control the number of jobs per platform
- HTML caching can speed up repeated scrapes

## Backup and Maintenance

### Regular Backups
- Copy CSV files to a backup location regularly
- Use version control if tracking changes
- Keep historical data for trend analysis

### Data Cleaning
- Remove duplicate entries manually if needed
- Update job statuses (applied, rejected, etc.)
- Add custom columns for personal tracking

## Integration with Other Tools

### Import to Excel
```python
import pandas as pd
df = pd.read_csv('jobs.csv')
```

### Import to Database
```python
import pandas as pd
from sqlalchemy import create_engine

df = pd.read_csv('jobs.csv')
engine = create_engine('sqlite:///jobs.db')
df.to_sql('jobs', engine, if_exists='replace')
```

### Data Analysis
```python
import pandas as pd

df = pd.read_csv('jobs.csv')
print(df.groupby('source').size())
print(df['salary'].describe())
```
