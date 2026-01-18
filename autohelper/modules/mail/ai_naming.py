"""
AI-powered filename cleaning utility.
Uses Gemini API to generate legible, human-readable filenames.
"""

import requests
import re
from pathlib import Path

# Reuse Gemini config from gemini_draft
GEMINI_API_KEY = "AIzaSyAJ3_P5WKeamnv94gJUvhIyJTo72kcF2fc"
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"


def generate_legible_filename(original_name: str, context: str = "") -> str:
    """
    Use Gemini to clean up a messy filename into a legible version.
    
    Examples:
    - "IMG_20260108_143522_HDR.jpg" -> "photo.jpg"
    - "Document (3) final FINAL v2.pdf" -> "document_final.pdf"
    - "1765493434_attachment.csv" -> "attachment.csv"
    
    Args:
        original_name: The original filename including extension
        context: Optional context (e.g., project name, email subject) for better naming
    
    Returns:
        Cleaned filename (lowercase, underscores, no random IDs)
    """
    # Extract extension
    path = Path(original_name)
    extension = path.suffix.lower()
    basename = path.stem
    
    # Skip if already clean (simple alphanumeric with underscores/hyphens)
    if re.match(r'^[a-z][a-z0-9_-]*$', basename.lower()) and len(basename) < 30:
        return original_name.lower().replace(" ", "_")
    
    # Build prompt
    prompt = f"""Clean up this filename to be human-readable. 
Rules:
- Use lowercase with underscores
- Remove random IDs, timestamps, version numbers like "(3)" or "v2"
- Keep meaningful words
- Max 30 characters before extension
- Return ONLY the new filename, nothing else

Original: {original_name}
"""
    if context:
        prompt += f"Context: {context}\n"
    
    prompt += "Cleaned filename:"
    
    try:
        payload = {
            "contents": [{"parts": [{"text": prompt}]}]
        }
        headers = {
            "Content-Type": "application/json",
            "X-goog-api-key": GEMINI_API_KEY
        }
        
        response = requests.post(GEMINI_API_URL, json=payload, headers=headers, timeout=10)
        
        if response.status_code != 200:
            # Fallback to simple cleanup
            return _simple_cleanup(original_name)
        
        result = response.json()
        cleaned = result['candidates'][0]['content']['parts'][0]['text'].strip()
        
        # Ensure it has the right extension
        cleaned_path = Path(cleaned)
        if cleaned_path.suffix.lower() != extension:
            cleaned = cleaned_path.stem + extension
        
        # Final sanitization
        cleaned = re.sub(r'[^\w\-.]', '_', cleaned.lower())
        cleaned = re.sub(r'_+', '_', cleaned)
        cleaned = cleaned.strip('_')
        
        return cleaned if cleaned else _simple_cleanup(original_name)
        
    except Exception:
        return _simple_cleanup(original_name)


def _simple_cleanup(filename: str) -> str:
    """Fallback simple cleanup without AI"""
    path = Path(filename)
    extension = path.suffix.lower()
    basename = path.stem.lower()
    
    # Remove common patterns
    basename = re.sub(r'\(\d+\)', '', basename)  # (1), (2), etc.
    basename = re.sub(r'_v\d+', '', basename)  # _v1, _v2
    basename = re.sub(r'\s*final\s*', '', basename, flags=re.IGNORECASE)
    basename = re.sub(r'^\d{10,}_', '', basename)  # Long numeric prefixes
    basename = re.sub(r'_\d{8,}', '', basename)  # Embedded timestamps
    
    # Clean up
    basename = re.sub(r'[^\w\-]', '_', basename)
    basename = re.sub(r'_+', '_', basename)
    basename = basename.strip('_')
    
    if not basename:
        basename = "attachment"
    
    return basename + extension


# Test
if __name__ == "__main__":
    test_files = [
        "IMG_20260108_143522_HDR.jpg",
        "Document (3) final FINAL v2.pdf",
        "1765493434_Avisina_Broadview.csv",
        "clean_name.pdf",
    ]
    
    print("Testing AI filename cleanup:")
    for f in test_files:
        cleaned = generate_legible_filename(f)
        print(f"  {f} -> {cleaned}")
