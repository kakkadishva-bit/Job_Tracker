#!/usr/bin/env python3
"""
Convert JobAgent Technical Documentation from Markdown to PDF
Uses Playwright (already in requirements) for PDF generation
"""

import markdown
import os
from datetime import datetime
from playwright.sync_api import sync_playwright

def markdown_to_pdf(md_file_path, pdf_file_path):
    """
    Convert Markdown file to PDF using Playwright
    
    Args:
        md_file_path: Path to input Markdown file
        pdf_file_path: Path to output PDF file
    """
    
    # Read Markdown content
    with open(md_file_path, 'r', encoding='utf-8') as f:
        md_content = f.read()
    
    # Convert Markdown to HTML
    html_body = markdown.markdown(
        md_content,
        extensions=[
            'tables',
            'fenced_code',
            'codehilite',
            'toc',
            'nl2br',
            'sane_lists'
        ]
    )
    
    # Professional CSS styling for PDF
    css_styles = """
    @page {
        size: A4;
        margin: 2cm;
    }
    
    body {
        font-family: "Segoe UI", Tahoma, Geneva, Verdana, sans-serif;
        font-size: 11pt;
        line-height: 1.6;
        color: #333;
        max-width: 100%;
    }
    
    h1 {
        font-size: 24pt;
        color: #2c3e50;
        border-bottom: 3px solid #3498db;
        padding-bottom: 10px;
        margin-top: 40px;
        page-break-after: avoid;
    }
    
    h2 {
        font-size: 18pt;
        color: #34495e;
        border-bottom: 2px solid #3498db;
        padding-bottom: 8px;
        margin-top: 30px;
        page-break-after: avoid;
    }
    
    h3 {
        font-size: 14pt;
        color: #2980b9;
        margin-top: 25px;
        page-break-after: avoid;
    }
    
    h4 {
        font-size: 12pt;
        color: #27ae60;
        margin-top: 20px;
        page-break-after: avoid;
    }
    
    h5, h6 {
        font-size: 11pt;
        color: #555;
        margin-top: 15px;
        page-break-after: avoid;
    }
    
    p {
        margin: 10px 0;
        text-align: justify;
    }
    
    a {
        color: #3498db;
        text-decoration: none;
    }
    
    strong {
        color: #2c3e50;
        font-weight: 600;
    }
    
    code {
        font-family: "Consolas", "Monaco", "Courier New", monospace;
        background-color: #f4f4f4;
        padding: 2px 6px;
        border-radius: 3px;
        font-size: 10pt;
        color: #e74c3c;
    }
    
    pre {
        background-color: #f8f8f8;
        border: 1px solid #ddd;
        border-left: 4px solid #3498db;
        padding: 12px;
        margin: 15px 0;
        overflow-x: auto;
        page-break-inside: avoid;
        border-radius: 4px;
        white-space: pre-wrap;
        word-wrap: break-word;
    }
    
    pre code {
        background-color: transparent;
        padding: 0;
        color: #333;
        font-size: 9pt;
        line-height: 1.4;
    }
    
    blockquote {
        border-left: 4px solid #3498db;
        margin: 15px 0;
        padding: 10px 20px;
        background-color: #f9f9f9;
        color: #555;
        font-style: italic;
    }
    
    ul, ol {
        margin: 10px 0;
        padding-left: 30px;
    }
    
    li {
        margin: 5px 0;
    }
    
    table {
        width: 100%;
        border-collapse: collapse;
        margin: 20px 0;
        font-size: 10pt;
        page-break-inside: avoid;
    }
    
    thead {
        background-color: #3498db;
        color: white;
    }
    
    th {
        padding: 10px;
        text-align: left;
        font-weight: 600;
        border: 1px solid #2980b9;
    }
    
    td {
        padding: 8px 10px;
        border: 1px solid #ddd;
    }
    
    tbody tr:nth-child(even) {
        background-color: #f9f9f9;
    }
    
    hr {
        border: none;
        border-top: 1px solid #ddd;
        margin: 30px 0;
    }
    
    .page-break {
        page-break-before: always;
    }
    
    /* Header and footer */
    .header {
        text-align: center;
        padding: 20px;
        border-bottom: 2px solid #3498db;
        margin-bottom: 30px;
    }
    
    .footer {
        text-align: center;
        padding: 10px;
        font-size: 9pt;
        color: #666;
        border-top: 1px solid #ddd;
        margin-top: 30px;
    }
    """
    
    # Complete HTML document with header/footer
    html_document = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>JobAgent Enterprise - Technical Documentation</title>
        <style>
            {css_styles}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>JobAgent Enterprise</h1>
            <h2>Technical Documentation</h2>
            <p>Version 1.0.0 | Generated: {datetime.now().strftime('%B %d, %Y')}</p>
        </div>
        
        {html_body}
        
        <div class="footer">
            <p>JobAgent Enterprise | Page <span class="pageNumber"></span></p>
        </div>
    </body>
    </html>
    """
    
    # Convert HTML to PDF using Playwright
    print(f"Converting {md_file_path} to PDF...")
    print("This may take a few minutes...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        # Set content
        page.set_content(html_document)
        
        # Generate PDF
        page.pdf(
            path=pdf_file_path,
            format='A4',
            margin={
                'top': '2cm',
                'right': '2cm',
                'bottom': '2cm',
                'left': '2cm'
            },
            print_background=True
        )
        
        browser.close()
    
    print(f"✓ PDF successfully generated: {pdf_file_path}")
    
    # Get file size
    pdf_size = os.path.getsize(pdf_file_path)
    print(f"  File size: {pdf_size / 1024 / 1024:.2f} MB")

def main():
    """Main conversion function"""
    
    # File paths
    md_file = "docs/TECHNICAL_DOCUMENTATION.md"
    pdf_file = "docs/JobAgent_Technical_Documentation.pdf"
    
    # Check if Markdown file exists
    if not os.path.exists(md_file):
        print(f"Error: Markdown file not found: {md_file}")
        return 1
    
    try:
        # Convert to PDF
        markdown_to_pdf(md_file, pdf_file)
        
        print("\n" + "="*60)
        print("Conversion completed successfully!")
        print("="*60)
        print(f"\nOutput PDF: {pdf_file}")
        print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("\nYou can now open the PDF in any PDF reader.")
        
        return 0
        
    except Exception as e:
        print(f"\nError during conversion: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit(main())