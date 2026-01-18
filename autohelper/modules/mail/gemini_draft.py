"""
Gemini API integration for draft generation.
Uses thread context for optimal token usage.
"""

import os
import json
import requests
from typing import List, Dict, Optional
from dataclasses import dataclass

# API Configuration
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

@dataclass
class EmailContext:
    """Compressed email context for API call"""
    subject: str
    sender: str
    project: str
    municipality: Optional[str]
    stage: Optional[str]
    key_asks: List[str]
    thread_summary: str

def compress_thread(emails: List[Dict]) -> EmailContext:
    """
    Compress a thread of emails into optimal context for Gemini.
    Target: ~2000 tokens max
    """
    if not emails:
        raise ValueError("No emails in thread")
    
    # Get the latest email
    latest = emails[-1]
    
    # Extract key asks from all emails
    key_asks = []
    for email in emails:
        body = email.get('bodyText', email.get('bodyPreview', ''))
        # Simple extraction - look for question marks and "please" patterns
        lines = body.split('\n')
        for line in lines:
            line = line.strip()
            if '?' in line or line.lower().startswith('please') or line.lower().startswith('can you'):
                if len(line) < 200:  # Keep it concise
                    key_asks.append(line)
    
    # Summarize thread (last 3 messages, compressed)
    thread_parts = []
    for email in emails[-3:]:
        sender = email.get('fromName', email.get('from', 'Unknown'))
        body = email.get('bodyText', email.get('bodyPreview', ''))
        # Truncate to first 300 chars
        body_short = body[:300] + '...' if len(body) > 300 else body
        thread_parts.append(f"[{sender}]: {body_short}")
    
    thread_summary = "\n---\n".join(thread_parts)
    
    return EmailContext(
        subject=latest.get('subject', ''),
        sender=latest.get('fromName', latest.get('from', '')),
        project=latest.get('projectName', latest.get('projectId', '')),
        municipality=latest.get('municipality'),
        stage=latest.get('stage'),
        key_asks=key_asks[:5],  # Max 5 key asks
        thread_summary=thread_summary
    )

def generate_draft(context: EmailContext, templates: Optional[List[str]] = None) -> Dict:
    """
    Generate a draft reply using Gemini API.
    
    Args:
        context: Compressed email context
        templates: Optional list of similar templates for style matching
    
    Returns:
        Dict with 'draft' text and 'reasoning'
    """
    if not GEMINI_API_KEY:
        return {
            "error": "Missing API Key",
            "details": "GEMINI_API_KEY environment variable not set."
        }
    
    # Build the prompt
    prompt_parts = [
        "You are a professional public art consultant responding to an email.",
        f"Project: {context.project}",
    ]
    
    if context.municipality:
        prompt_parts.append(f"Municipality: {context.municipality}")
    if context.stage:
        prompt_parts.append(f"Current Stage: {context.stage}")
    
    prompt_parts.append(f"\nEmail Subject: {context.subject}")
    prompt_parts.append(f"From: {context.sender}")
    
    if context.key_asks:
        prompt_parts.append("\nKey asks to address:")
        for ask in context.key_asks:
            prompt_parts.append(f"  - {ask}")
    
    prompt_parts.append(f"\nThread context:\n{context.thread_summary}")
    
    if templates:
        prompt_parts.append("\nReference these similar responses for tone/style:")
        for t in templates[:2]:  # Max 2 templates
            prompt_parts.append(f"---\n{t[:500]}\n---")
    
    prompt_parts.append("\nWrite a professional, concise reply. Be helpful and specific. Sign as 'Neal'.")
    
    prompt = "\n".join(prompt_parts)
    
    # Call Gemini API
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ]
    }
    
    headers = {
        "Content-Type": "application/json",
        "X-goog-api-key": GEMINI_API_KEY
    }
    
    response = requests.post(GEMINI_API_URL, json=payload, headers=headers)
    
    if response.status_code != 200:
        return {
            "error": f"API error: {response.status_code}",
            "details": response.text
        }
    
    result = response.json()
    
    # Extract the generated text
    try:
        draft_text = result['candidates'][0]['content']['parts'][0]['text']
    except (KeyError, IndexError):
        return {"error": "Failed to parse response", "details": result}
    
    return {
        "draft": draft_text,
        "reasoning": f"Generated based on {len(context.key_asks)} key asks, stage: {context.stage or 'unknown'}",
        "token_estimate": len(prompt.split()) * 1.3  # Rough estimate
    }


# Quick test
if __name__ == "__main__":
    test_emails = [
        {
            "subject": "Re: Qualex - Artesia - Public Art",
            "fromName": "Leyli Jalali",
            "from": "ljalali@qualex.ca",
            "projectName": "Artesia",
            "bodyText": "Hi Jan, Happy New Year! Henry and I wanted to follow up on the public art installation timeline. Can you please send the updated schedule?"
        }
    ]
    
    context = compress_thread(test_emails)
    print(f"Context: {context}")
    
    result = generate_draft(context)
    print(f"\nGenerated draft:\n{result.get('draft', result.get('error'))}")
