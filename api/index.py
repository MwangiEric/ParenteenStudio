from fastapi import FastAPI, Request, Form, Response
from fastapi.templating import Jinja2Templates
from youtube_transcript_api import YouTubeTranscriptApi
import re
import json
import textwrap
from PIL import Image, ImageDraw
import io
import cv2
import numpy as np
import tempfile
import os

app = FastAPI()
templates = Jinja2Templates(directory="templates")

API_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(API_DIR)

# YouTube URL parser
def extract_video_id(url: str) -> str:
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
    """Extract best quotes from YouTube video"""
    try:
        transcript = YouTubeTranscriptApi().fetch(video_id, languages=['en'])
        
        # Score segments for insightfulness
        quotes = []
        insight_keywords = [
            'important', 'key', 'crucial', 'essential', 'remember', 'understand',
            'realize', 'discover', 'breakthrough', 'insight', 'lesson', 'wisdom',
            'experience', 'advice', 'perspective', 'meaning', 'purpose'
        ]
        
        for segment in transcript:
            text = segment.text.strip()
            score = 0
            
            # Score based on keywords and length
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
        
        # Sort by score and return top 8
        quotes.sort(key=lambda x: x['score'], reverse=True)
        return quotes[:8]
        
    except Exception as e:
        return [{'text': f'Error: {str(e)}', 'timestamp': 0, 'youtube_url': '', 'score': 0}]

def create_quote_image(text: str) -> bytes:
    """Create branded quote image"""
    width, height = 1080, 1080
    
    # Create base image
    img = Image.new('RGB', (width, height), color=(30, 27, 75))
    draw = ImageDraw.Draw(img)
    
    # Wrap text
    wrapped_lines = textwrap.wrap(text, width=25)
    
    # Draw main text
    text_y = height // 2
    for i, line in enumerate(wrapped_lines):
        y_pos = text_y + (i - len(wrapped_lines)/2) * 80
        draw.text((width//2, y_pos), line, fill=(255, 255, 255), 
                 anchor="mm", size=60)
    
    # Draw author
    draw.text((width//2, height - 150), "- Jane Kariuki, Teen Psychologist", 
             fill=(236, 72, 153), anchor="mm", size=30)
    
    # Draw brand
    draw.text((width//2, height - 100), "@ParenTeenKenya", 
             fill=(200, 200, 200), anchor="mm", size=25)
    
    # Convert to bytes
    img_buffer = io.BytesIO()
    img.save(img_buffer, format='PNG')
    img_buffer.seek(0)
    return img_buffer.getvalue()

@app.get("/")
async def home(request: Request):
    quotes = [
        "Your teen is listening, even when they seem to ignore you.",
        "Connection before correction - always.",
        "Their rebellion is often a search for identity.",
        "Listen to understand, not to reply.",
        "Your calm is their anchor in emotional storms."
    ]
    return templates.TemplateResponse("index.html", {"request": request, "quotes": quotes})

@app.post("/analyze")
async def analyze_youtube(youtube_url: str = Form(...)):
    video_id = extract_video_id(youtube_url)
    quotes = get_insightful_quotes(video_id)
    return {"quotes": quotes, "video_id": video_id}

@app.post("/generate-image")
async def generate_image(quote: str = Form(...)):
    image_data = create_quote_image(quote)
    return Response(content=image_data, media_type="image/png")

@app.get("/api/health")
async def health():
    return {"status": "healthy"}

# ---------- STATIC FILES MOUNTING ----------
static_path = os.path.join(API_DIR, "static")
if os.path.exists(static_path):
    app.mount("/", StaticFiles(directory=static_path, html=True), name="static")
else:
    @app.get("/")
    def index_missing():
        return {"error": "Static folder not found", "checked": static_path}
