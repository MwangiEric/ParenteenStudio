import os
import cv2
import numpy as np
import requests
import textwrap
from PIL import Image, ImageDraw, ImageFont
from fastapi import FastAPI, Response, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from groq import Groq
from youtube_transcript_api import YouTubeTranscriptApi
import tempfile
import re
from pathlib import Path

app = FastAPI()

# Fix template path for Vercel
current_dir = Path(__file__).parent
templates = Jinja2Templates(directory=str(current_dir / "templates"))

# Configuration
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
LOGO_URL = "https://ik.imagekit.io/ericmwangi/cropped-Parenteen-Kenya-Logo-rec.png"

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
    """Extract insightful quotes from YouTube video"""
    try:
        transcript = YouTubeTranscriptApi().fetch(video_id, languages=['en'])
        
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

# --- GROQ QUOTE GENERATION ---
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

# --- VIDEO ENGINE (Enhanced with YouTube segments) ---
def create_video(text: str, bg_image=None):
    """Create branded video with enhanced visuals"""
    width, height = 1080, 1920
    fps, duration = 24, 6  # Increased FPS for smoother video
    
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        video = cv2.VideoWriter(tmp.name, fourcc, fps, (width, height))
        
        # Pre-wrap text
        wrapped = "\n".join(textwrap.wrap(text, width=20))

        for i in range(fps * duration):
            # Create gradient background
            img = Image.new('RGB', (width, height), color=(30, 27, 75))
            draw = ImageDraw.Draw(img)
            
            # Add subtle gradient effect
            for y in range(height):
                factor = y / height
                r = int(30 * (1 - factor * 0.3))
                g = int(27 * (1 - factor * 0.3))
                b = int(75 * (1 - factor * 0.3))
                draw.line([(0, y), (width, y)], fill=(r, g, b))
            
            # Draw text with animation effect
            alpha = min(1.0, i / (fps * 1.5))  # Fade in effect
            text_color = (255, 255, 255)
            
            # Main quote text
            draw.multiline_text((width//2, height//2), wrapped, 
                               fill=text_color, anchor="mm", align="center",
                               font_size=60)
            
            # Author text (smaller, with fade-in)
            if i > fps * 1:  # Appear after main text
                draw.text((width//2, height//2 + 200), 
                         "- Jane Kariuki, Teen Psychologist", 
                         fill=(236, 72, 153), anchor="mm", font_size=30)
            
            # Brand text
            if i > fps * 2:  # Appear last
                draw.text((width//2, height - 100), "@ParenTeenKenya", 
                         fill=(200, 200, 200), anchor="mm", font_size=25)

            frame = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
            video.write(frame)

        video.release()
        return tmp.name

def create_quote_image(text: str) -> bytes:
    """Create enhanced branded quote image"""
    width, height = 1080, 1080
    
    # Create base image with gradient
    img = Image.new('RGB', (width, height), color=(30, 27, 75))
    draw = ImageDraw.Draw(img)
    
    # Add gradient background
    for y in range(height):
        factor = y / height
        r = int(30 + (60 - 30) * factor)
        g = int(27 + (55 - 27) * factor)
        b = int(75 + (130 - 75) * factor)
        draw.line([(0, y), (width, y)], fill=(r, g, b))
    
    # Wrap text
    wrapped_lines = textwrap.wrap(text, width=25)
    
    # Main text with shadow effect
    text_y = height // 2
    for i, line in enumerate(wrapped_lines):
        y_pos = text_y + (i - len(wrapped_lines)/2) * 80
        
        # Shadow
        draw.text((width//2 + 2, y_pos + 2), line, fill=(0, 0, 0), 
                 anchor="mm", size=62, alpha=128)
        
        # Main text
        draw.text((width//2, y_pos), line, fill=(255, 255, 255), 
                 anchor="mm", size=60)
    
    # Author with style
    draw.text((width//2, height - 150), "- Jane Kariuki, Teen Psychologist", 
             fill=(236, 72, 153), anchor="mm", size=30)
    
    # Brand
    draw.text((width//2, height - 100), "@ParenTeenKenya • parenteenkenya.co.ke", 
             fill=(200, 200, 200), anchor="mm", size=20)
    
    # Decorative quotes
    draw.text((width//2 - 200, height // 2 - 150), """, fill=(255, 255, 255), anchor="mm", size=80, alpha=100)
    draw.text((width//2 + 200, height // 2 + 150), """, fill=(255, 255, 255), anchor="mm", size=80, alpha=100)
    
    # Convert to bytes
    img_buffer = io.BytesIO()
    img.save(img_buffer, format='PNG', quality=95)
    img_buffer.seek(0)
    return img_buffer.getvalue()

# --- ROUTES ---
@app.get("/")
async def home(request: Request):
    ai_quotes = generate_groq_quotes()
    return templates.TemplateResponse("index.html", {"request": request, "quotes": ai_quotes})

@app.post("/analyze")
async def analyze_youtube(youtube_url: str = Form(...)):
    """Analyze YouTube video and extract quotes"""
    video_id = extract_video_id(youtube_url)
    quotes = get_insightful_quotes(video_id)
    return {"quotes": quotes, "video_id": video_id}

@app.post("/generate-video")
async def generate_video(quote: str = Form(...)):
    """Generate branded video from quote"""
    try:
        video_path = create_video(quote)
        with open(video_path, "rb") as f:
            data = f.read()
        os.remove(video_path)
        return Response(content=data, media_type="video/mp4")
    except Exception as e:
        return {"error": str(e)}

@app.post("/generate-image")
async def generate_image(quote: str = Form(...)):
    """Generate branded image from quote"""
    try:
        image_data = create_quote_image(quote)
        return Response(content=image_data, media_type="image/png")
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/health")
async def health():
    return {"status": "healthy", "youtube_support": True}
