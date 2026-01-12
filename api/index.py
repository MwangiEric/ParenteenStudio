import os
import cv2
import numpy as np
import requests
import textwrap
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont
from fastapi import FastAPI, Response, Request, Form
from fastapi.templating import Jinja2Templates
from groq import Groq
import tempfile

app = FastAPI()

# Setup Jinja2 Templates
templates = Jinja2Templates(directory="api/templates")

# Configuration
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
LOGO_URL = "https://ik.imagekit.io/ericmwangi/cropped-Parenteen-Kenya-Logo-rec.png"

# --- GROQ QUOTE GENERATION ---
def generate_groq_quotes():
    client = Groq(api_key=GROQ_API_KEY)
    prompt = "Generate 5 short, impactful parenting quotes for teenagers. Keep them under 15 words each."
    
    completion = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}]
    )
    # Basic parsing (assumes numbered list)
    quotes = completion.choices[0].message.content.split('\n')
    return [q.strip() for q in quotes if q.strip() and any(char.isdigit() for char in q[:2])]

# --- VIDEO ENGINE (Simplified with Brand Colors) ---
def create_video(text: str):
    width, height = 1080, 1920
    fps, duration = 12, 6
    
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        video = cv2.VideoWriter(tmp.name, fourcc, fps, (width, height))
        
        # Pre-wrap text
        wrapped = "\n".join(textwrap.wrap(text, width=20))

        for i in range(fps * duration):
            # Use ParenTeen Brand Color: bg_dark (#1E1B4B)
            img = Image.new('RGB', (width, height), color=(30, 27, 75)) 
            draw = ImageDraw.Draw(img)
            
            # Draw Logo (Centered at top)
            # (In production, download logo once and reuse)
            
            # Draw Quote
            draw.multiline_text((width//2, height//2), wrapped, fill=(255,255,255), anchor="mm", align="center")
            
            # Draw Author (Jane Kariuki)
            draw.text((width//2, height//2 + 200), "- Jane Kariuki, Teen Psychologist", fill=(236, 72, 153), anchor="mm")

            frame = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
            video.write(frame)

        video.release()
        return tmp.name

# --- ROUTES ---

@app.get("/")
async def home(request: Request):
    # Fetch 5 quotes from Groq for the dashboard
    ai_quotes = generate_groq_quotes() if GROQ_API_KEY else ["Listening is the first step to connection."]
    return templates.TemplateResponse("index.html", {"request": request, "quotes": ai_quotes})

@app.post("/generate")
async def handle_generate(quote: str = Form(...)):
    video_path = create_video(quote)
    with open(video_path, "rb") as f:
        data = f.read()
    os.remove(video_path)
    return Response(content=data, media_type="video/mp4")
