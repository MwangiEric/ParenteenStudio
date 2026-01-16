from fastapi import FastAPI, Request, Form, Response, HTTPException
from fastapi.templating import Jinja2Templates
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.proxies import GenericProxyConfig
from fastapi.responses import HTMLResponse
from groq import Groq
import tempfile
import re
import textwrap
from pathlib import Path
import os
import requests
import json
from PIL import Image, ImageDraw, ImageFont
import io
from datetime import datetime
from typing import List, Dict, Any
import uuid

app = FastAPI()

# Fix template path for Vercel
current_dir = Path(__file__).parent
templates = Jinja2Templates(directory=str(current_dir / "templates"))

# Configuration
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
LOGO_URL = "https://ik.imagekit.io/ericmwangi/cropped-Parenteen-Kenya-Logo-rec.png"

# Proxy Configuration
PROXY_CONFIG = {
    'http_url': 'http://udizufzc:2ile7xfmbivj@142.111.48.253:7030/',
    'https_url': 'http://udizufzc:2ile7xfmbivj@142.111.48.253:7030/'
}

# --- CLIENT MANAGEMENT SYSTEM (Images Focus) ---
class ClientManager:
    def __init__(self):
        self.clients = []
        self.meetings = []
        self.visual_reminders = []  # Store image-based reminders
        self.load_sample_data()
    
    def load_sample_data(self):
        """Load sample client data"""
        self.clients = [
            {
                "id": "client_001",
                "name": "Sarah Mwangi",
                "teen_name": "Brian Mwangi (15)",
                "session_type": "Individual Counseling",
                "status": "Active",
                "next_session": "2024-01-15",
                "visual_notes": "anxiety_issues_communication_improving"  # Keywords for image generation
            },
            {
                "id": "client_002",
                "name": "John Kamau",
                "teen_name": "Alice Kamau (13)",
                "session_type": "Family Therapy",
                "status": "Active",
                "next_session": "2024-01-20",
                "visual_notes": "family_communication_behavioral_challenges"
            }
        ]
        
        self.visual_reminders = [
            {
                "id": "reminder_001",
                "client_id": "client_001",
                "type": "session_prep",
                "title": "Session Prep - Communication Strategies",
                "visual_content": "communication_tips_teens_parents",
                "deadline": "2024-01-15",
                "status": "pending"
            }
        ]

client_manager = ClientManager()

# --- YOUTUBE TRANSCRIPT FEATURE ---
def extract_video_id(url: str) -> str:
    """Extract video ID from any YouTube URL format"""
    patterns = [
        r'youtube\.com/shorts/([^?&]+)',
        r'youtube\.com/watch\?v=([^?&]+)',
        r'youtu\.be/([^?&]+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return url

def get_insightful_quotes(video_id: str) -> list:
    """Extract insightful quotes from YouTube video using proxy"""
    try:
        proxy_config = GenericProxyConfig(
            http_url=PROXY_CONFIG['http_url'],
            https_url=PROXY_CONFIG['https_url']
        )
        
        transcript = YouTubeTranscriptApi().fetch(video_id, languages=['en'], proxy_config=proxy_config)
        
        quotes = []
        insight_keywords = [
            'important', 'key', 'crucial', 'essential', 'remember', 'understand',
            'realize', 'discover', 'breakthrough', 'insight', 'lesson', 'wisdom',
            'experience', 'advice', 'perspective', 'meaning', 'purpose'
        ]
        
        for segment in transcript:
            text = segment.text.strip()
            score = 0
            
            text_lower = text.lower()
            for keyword in insight_keywords:
                score += text_lower.count(keyword) * 10
            
            if 20 < len(text) < 120 and score > 0:
                quotes.append({
                    'text': text,
                    'timestamp': segment.start,
                    'youtube_url': f"https://www.youtube.com/watch?v={video_id}&t={int(segment.start)}s",
                    'score': score
                })
        
        quotes.sort(key=lambda x: x['score'], reverse=True)
        return quotes[:8]
        
    except Exception as e:
        return [{'text': f'Error: {str(e)}', 'timestamp': 0, 'youtube_url': '', 'score': 0}]

# --- VISUAL CONTENT CREATION ---
def create_meeting_reminder_image(client_name: str, meeting_info: dict) -> bytes:
    """Create visual meeting reminder"""
    width, height = 1080, 1920
    
    # Create base image
    img = Image.new('RGB', (width, height), color=(30, 27, 75))
    draw = ImageDraw.Draw(img)
    
    # Add gradient
    for y in range(height):
        factor = y / height
        r = int(30 + (60 - 30) * factor)
        g = int(27 + (55 - 27) * factor)
        b = int(75 + (130 - 75) * factor)
        draw.line([(0, y), (width, y)], fill=(r, g, b))
    
    # Title
    draw.text((width//2, 200), "Meeting Reminder", 
             fill=(255, 255, 255), anchor="mm", size=60)
    
    # Client name
    draw.text((width//2, 350), f"Dear {client_name}", 
             fill=(236, 72, 153), anchor="mm", size=40)
    
    # Meeting details
    details = [
        f"📅 Date: {meeting_info.get('date', 'TBD')}",
        f"⏰ Time: {meeting_info.get('time', 'TBD')}",
        f"📍 Type: {meeting_info.get('type', 'Online')}",
        f"⏱️ Duration: {meeting_info.get('duration', 60)} minutes"
    ]
    
    y_pos = 500
    for detail in details:
        draw.text((width//2, y_pos), detail, 
                 fill=(255, 255, 255), anchor="mm", size=35)
        y_pos += 80
    
    # Key points
    if meeting_info.get('key_points'):
        draw.text((width//2, y_pos + 50), "Key Discussion Points:", 
                 fill=(236, 72, 153), anchor="mm", size=35)
        y_pos += 120
        
        for i, point in enumerate(meeting_info['key_points'][:3]):
            draw.text((width//2, y_pos), f"• {point}", 
                     fill=(255, 255, 255), anchor="mm", size=30)
            y_pos += 60
    
    # Brand
    draw.text((width//2, height - 100), "@ParenTeenKenya", 
             fill=(200, 200, 200), anchor="mm", size=25)
    
    img_buffer = io.BytesIO()
    img.save(img_buffer, format='PNG')
    img_buffer.seek(0)
    return img_buffer.getvalue()

def create_educational_infographic(topic: str, key_points: List[str]) -> bytes:
    """Create educational infographic"""
    width, height = 1080, 1920
    
    # Create base image
    img = Image.new('RGB', (width, height), color=(30, 27, 75))
    draw = ImageDraw.Draw(img)
    
    # Title
    draw.text((width//2, 150), f"Parenting Guide: {topic}", 
             fill=(255, 255, 255), anchor="mm", size=50)
    
    # Key points with visual elements
    y_pos = 300
    for i, point in enumerate(key_points[:5]):
        # Number circle
        draw.ellipse([(width//2 - 200, y_pos - 25), (width//2 - 150, y_pos + 25)], 
                    fill=(236, 72, 153))
        draw.text((width//2 - 175, y_pos), str(i + 1), 
                 fill=(255, 255, 255), anchor="mm", size=25)
        
        # Point text
        wrapped_text = textwrap.wrap(point, width=40)
        for j, line in enumerate(wrapped_text):
            draw.text((width//2 + 50, y_pos + (j - len(wrapped_text)/2) * 40), 
                     line, fill=(255, 255, 255), anchor="mm", size=28)
        
        y_pos += 120 + (len(wrapped_text) - 1) * 40
    
    # Call to action
    draw.text((width//2, height - 150), "Save & Share for Daily Reminders", 
             fill=(236, 72, 153), anchor="mm", size=30)
    
    draw.text((width//2, height - 100), "@ParenTeenKenya", 
             fill=(200, 200, 200), anchor="mm", size=25)
    
    img_buffer = io.BytesIO()
    img.save(img_buffer, format='PNG')
    img_buffer.seek(0)
    return img_buffer.getvalue()

def create_session_summary_image(client_name: str, session_data: dict) -> bytes:
    """Create visual session summary"""
    width, height = 1080, 1920
    
    # Create base image
    img = Image.new('RGB', (width, height), color=(30, 27, 75))
    draw = ImageDraw.Draw(img)
    
    # Header
    draw.text((width//2, 150), "Session Summary", 
             fill=(255, 255, 255), anchor="mm", size=50)
    
    draw.text((width//2, 220), f"Client: {client_name}", 
             fill=(236, 72, 153), anchor="mm", size=35)
    
    # Session info
    info_items = [
        f"📅 Date: {session_data.get('date', datetime.now().strftime('%Y-%m-%d'))}",
        f"⏱️ Duration: {session_data.get('duration', 60)} minutes",
        f"📊 Progress: {session_data.get('progress', 'Good')}",
    ]
    
    y_pos = 350
    for item in info_items:
        draw.text((width//2, y_pos), item, 
                 fill=(255, 255, 255), anchor="mm", size=30)
        y_pos += 70
    
    # Key insights
    if session_data.get('key_insights'):
        draw.text((width//2, y_pos + 50), "Key Insights:", 
                 fill=(236, 72, 153), anchor="mm", size=35)
        y_pos += 100
        
        for insight in session_data['key_insights'][:3]:
            wrapped = textwrap.wrap(insight, width=50)
            for line in wrapped:
                draw.text((width//2, y_pos), f"• {line}", 
                         fill=(255, 255, 255), anchor="mm", size=25)
                y_pos += 40
            y_pos += 20
    
    # Next steps
    if session_data.get('next_steps'):
        draw.text((width//2, y_pos + 30), "Next Steps:", 
                 fill=(236, 72, 153), anchor="mm", size=30)
        y_pos += 70
        
        for step in session_data['next_steps'][:3]:
            draw.text((width//2, y_pos), f"→ {step}", 
                     fill=(255, 255, 255), anchor="mm", size=25)
            y_pos += 50
    
    # Brand
    draw.text((width//2, height - 100), "@ParenTeenKenya", 
             fill=(200, 200, 200), anchor="mm", size=25)
    
    img_buffer = io.BytesIO()
    img.save(img_buffer, format='PNG')
    img_buffer.seek(0)
    return img_buffer.getvalue()

# --- GROG QUOTE GENERATION ---
def generate_groq_quotes():
    """Generate quotes using Groq AI"""
    if not GROQ_API_KEY:
        return [
            "Listening is the first step to connection.",
            "Your teen needs your presence more than your advice.",
            "Connection before correction always works.",
            "Their silence speaks volumes - listen with your heart.",
            "Parenting teens is a marathon of patience and love."
        ]
    
    try:
        client = Groq(api_key=GROQ_API_KEY)
        prompt = "Generate 5 short, impactful parenting quotes for teenagers. Keep them under 15 words each."
        
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}]
        )
        
        quotes = completion.choices[0].message.content.split('\n')
        cleaned_quotes = [q.strip() for q in quotes if q.strip() and len(q.strip()) > 10]
        
        return cleaned_quotes[:5] if cleaned_quotes else [
            "Your teen is listening, even when they seem to ignore you.",
            "Connection before correction - always.",
            "Their rebellion is often a search for identity.",
            "Listen to understand, not to reply.",
            "Your calm is their anchor in emotional storms."
        ]
    except Exception as e:
        return [f"AI Error: {str(e)}"]

# --- VISUAL REMINDERS & SCHEDULING ---
def create_visual_reminder(reminder_type: str, content: str, deadline: str) -> bytes:
    """Create visual reminder images"""
    width, height = 1080, 1920
    
    img = Image.new('RGB', (width, height), color=(30, 27, 75))
    draw = ImageDraw.Draw(img)
    
    # Type-specific styling
    if reminder_type == "daily_reminder":
        title = "Daily Parenting Reminder"
        color = (236, 72, 153)  # Pink
    elif reminder_type == "session_prep":
        title = "Session Preparation"
        color = (59, 130, 246)  # Blue
    elif reminder_type == "deadline":
        title = "Important Deadline"
        color = (239, 68, 68)  # Red
    else:
        title = "Reminder"
        color = (255, 255, 255)
    
    # Header
    draw.text((width//2, 150), title, fill=color, anchor="mm", size=50)
    
    # Content
    wrapped_content = textwrap.wrap(content, width=35)
    y_pos = 400
    for line in wrapped_content:
        draw.text((width//2, y_pos), line, fill=(255, 255, 255), anchor="mm", size=35)
        y_pos += 60
    
    # Deadline
    if deadline:
        draw.text((width//2, height - 200), f"Deadline: {deadline}", 
                 fill=color, anchor="mm", size=30)
    
    # Brand
    draw.text((width//2, height - 100), "@ParenTeenKenya", 
             fill=(200, 200, 200), anchor="mm", size=25)
    
    img_buffer = io.BytesIO()
    img.save(img_buffer, format='PNG')
    img_buffer.seek(0)
    return img_buffer.getvalue()

# --- DISCUSSION VISUALS ---
def create_discussion_visual(topic: str, key_points: List[str], questions: List[str]) -> bytes:
    """Create visual discussion guide"""
    width, height = 1080, 1920
    
    img = Image.new('RGB', (width, height), color=(30, 27, 75))
    draw = ImageDraw.Draw(img)
    
    # Title
    draw.text((width//2, 150), f"Discussion: {topic}", 
             fill=(255, 255, 255), anchor="mm", size=45)
    
    # Key Points Section
    draw.text((width//2, 300), "Key Points to Cover:", 
             fill=(236, 72, 153), anchor="mm", size=35)
    
    y_pos = 400
    for i, point in enumerate(key_points[:4]):
        wrapped = textwrap.wrap(point, width=40)
        for j, line in enumerate(wrapped):
            draw.text((width//2, y_pos), f"{i+1}. {line}", 
                     fill=(255, 255, 255), anchor="mm", size=28)
            y_pos += 45
        y_pos += 20
    
    # Questions Section
    if questions:
        draw.text((width//2, y_pos + 50), "Discussion Questions:", 
                 fill=(236, 72, 153), anchor="mm", size=35)
        y_pos += 120
        
        for i, question in enumerate(questions[:3]):
            wrapped = textwrap.wrap(question, width=45)
            for j, line in enumerate(wrapped):
                draw.text((width//2, y_pos), f"Q{i+1}: {line}", 
                         fill=(255, 255, 255), anchor="mm", size=26)
                y_pos += 40
            y_pos += 20
    
    # Brand
    draw.text((width//2, height - 100), "@ParenTeenKenya", 
             fill=(200, 200, 200), anchor="mm", size=25)
    
    img_buffer = io.BytesIO()
    img.save(img_buffer, format='PNG')
    img_buffer.seek(0)
    return img_buffer.getvalue()

# --- MEETING SCHEDULER (Images) ---
def create_meeting_visual_invitation(meeting_info: dict) -> bytes:
    """Create visual meeting invitation"""
    width, height = 1080, 1920
    
    img = Image.new('RGB', (width, height), color=(30, 27, 75))
    draw = ImageDraw.Draw(img)
    
    # Header
    draw.text((width//2, 150), "You're Invited", 
             fill=(255, 255, 255), anchor="mm", size=50)
    
    draw.text((width//2, 220), meeting_info.get('title', 'Session'), 
             fill=(236, 72, 153), anchor="mm", size=40)
    
    # Meeting details
    details = [
        f"📅 {meeting_info.get('date', 'TBD')}",
        f"⏰ {meeting_info.get('time', 'TBD')}",
        f"📍 {meeting_info.get('location', 'Online')}",
        f"⏱️ {meeting_info.get('duration', 60)} min"
    ]
    
    y_pos = 400
    for detail in details:
        draw.text((width//2, y_pos), detail, 
                 fill=(255, 255, 255), anchor="mm", size=35)
        y_pos += 80
    
    # Special instructions
    if meeting_info.get('special_instructions'):
        draw.text((width//2, y_pos + 50), "Special Instructions:", 
                 fill=(236, 72, 153), anchor="mm", size=30)
        y_pos += 100
        
        wrapped = textwrap.wrap(meeting_info['special_instructions'], width=40)
        for line in wrapped:
            draw.text((width//2, y_pos), line, 
                     fill=(255, 255, 255), anchor="mm", size=28)
            y_pos += 50
    
    # Brand
    draw.text((width//2, height - 100), "@ParenTeenKenya", 
             fill=(200, 200, 200), anchor="mm", size=25)
    
    img_buffer = io.BytesIO()
    img.save(img_buffer, format='PNG')
    img_buffer.seek(0)
    return img_buffer.getvalue()

# --- ROUTES ---
@app.get("/")
async def home(request: Request):
    """Main dashboard with visual tools"""
    ai_quotes = generate_groq_quotes()
    upcoming_meetings = [m for m in client_manager.meetings if m['status'] == 'scheduled'][:3]
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request, 
        "quotes": ai_quotes,
        "upcoming_meetings": upcoming_meetings,
        "total_clients": len(client_manager.clients),
        "total_meetings": len(client_manager.meetings)
    })

@app.post("/analyze")
async def analyze_youtube(youtube_url: str = Form(...)):
    """Analyze YouTube video using proxy and extract quotes"""
    video_id = extract_video_id(youtube_url)
    quotes = get_insightful_quotes(video_id)
    return {"quotes": quotes, "video_id": video_id, "proxy_enabled": True}

# --- VISUAL REMINDER ROUTES ---
@app.post("/create-visual-reminder")
async def create_visual_reminder_endpoint(reminder_type: str = Form(...), 
                                        content: str = Form(...), 
                                        deadline: str = Form(...)):
    """Create visual reminder"""
    try:
        image_data = create_visual_reminder(reminder_type, content, deadline)
        return Response(content=image_data, media_type="image/png")
    except Exception as e:
        return {"error": str(e)}

@app.post("/create-meeting-reminder")
async def create_meeting_reminder_endpoint(client_name: str = Form(...), 
                                         meeting_data: str = Form(...)):
    """Create meeting reminder image"""
    try:
        meeting_info = json.loads(meeting_data)
        image_data = create_meeting_reminder_image(client_name, meeting_info)
        return Response(content=image_data, media_type="image/png")
    except Exception as e:
        return {"error": str(e)}

@app.post("/create-educational-infographic")
async def create_educational_infographic_endpoint(topic: str = Form(...), 
                                                key_points: str = Form(...)):
    """Create educational infographic"""
    try:
        points = json.loads(key_points)
        image_data = create_educational_infographic(topic, points)
        return Response(content=image_data, media_type="image/png")
    except Exception as e:
        return {"error": str(e)}

@app.post("/create-session-summary")
async def create_session_summary_endpoint(client_name: str = Form(...), 
                                        session_data: str = Form(...)):
    """Create session summary image"""
    try:
        session_info = json.loads(session_data)
        image_data = create_session_summary_image(client_name, session_info)
        return Response(content=image_data, media_type="image/png")
    except Exception as e:
        return {"error": str(e)}

@app.post("/create-discussion-visual")
async def create_discussion_visual_endpoint(topic: str = Form(...), 
                                          key_points: str = Form(...), 
                                          questions: str = Form(...)):
    """Create discussion visual guide"""
    try:
        points = json.loads(key_points)
        questions_list = json.loads(questions)
        image_data = create_discussion_visual(topic, points, questions_list)
        return Response(content=image_data, media_type="image/png")
    except Exception as e:
        return {"error": str(e)}

@app.post("/create-meeting-invitation")
async def create_meeting_invitation_endpoint(meeting_info: str = Form(...)):
    """Create meeting invitation image"""
    try:
        meeting_data = json.loads(meeting_info)
        image_data = create_meeting_visual_invitation(meeting_data)
        return Response(content=image_data, media_type="image/png")
    except Exception as e:
        return {"error": str(e)}

@app.post("/generate-quotes-from-content")
async def generate_quotes_from_content(content: str = Form(...), source: str = Form("content")):
    """Generate quotes and OG images from content"""
    analysis = analyze_content_with_groq(content, "quotes")
    
    quotes_with_images = []
    for i, quote in enumerate(analysis.get('quotes', [])):
        try:
            og_image = create_og_image(quote, f"Quote {i+1}")
            quotes_with_images.append({
                'text': quote,
                'og_image': f"data:image/png;base64,{og_image.hex()}" if isinstance(og_image, bytes) else "",
                'source': source,
                'index': i + 1
            })
        except Exception as e:
            quotes_with_images.append({
                'text': quote,
                'og_image': "",
                'source': source,
                'index': i + 1,
                'error': str(e)
            })
    
    return {
        "quotes": quotes_with_images,
        "keywords": analysis.get('keywords', []),
        "summary": analysis.get('summary', ''),
        "source": source
    }

@app.post("/generate-og-image")
async def generate_og_image_endpoint(text: str = Form(...), title: str = Form(""), 
                                   author: str = Form("Jane Kariuki")):
    """Generate OG image for social sharing"""
    try:
        image_data = create_og_image(text, title, author)
        return Response(content=image_data, media_type="image/png")
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/health")
async def health():
    return {
        "status": "healthy",
        "features": {
            "youtube_support": True,
            "proxy_enabled": True,
            "visual_content": True,
            "client_management": True,
            "meeting_images": True,
            "educational_materials": True,
            "og_images": True,
            "groq_ai": GROQ_API_KEY is not None
        },
        "timestamp": datetime.now().isoformat()
    }
