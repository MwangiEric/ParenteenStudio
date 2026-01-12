import cv2
import numpy as np
import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont
from fastapi import FastAPI, Response, Query
import tempfile
import os

app = FastAPI()

# --- UTILITY: SCRAPER ---
def fetch_blog_content(url: str):
    try:
        res = requests.get(url, timeout=5)
        soup = BeautifulSoup(res.text, 'html.parser')
        # Adjust these selectors to match your theme
        title = soup.find('h1').text.strip()
        # Get the first paragraph as the "quote"
        excerpt = soup.find('p').text.strip()[:120] + "..."
        return {"title": title, "text": excerpt}
    except Exception:
        return {"title": "ParenTeen Kenya", "text": "Empowering parents and teens."}

# --- UTILITY: VIDEO ENGINE ---
def generate_video_stream(text: str):
    width, height = 1080, 1920
    fps = 12
    duration = 6
    total_frames = fps * duration
    
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        # Define the codec and VideoWriter
        fourcc = cv2.VideoWriter_fourcc(*'mp4v') 
        video = cv2.VideoWriter(tmp.name, fourcc, fps, (width, height))

        for i in range(total_frames):
            # 1. Create a frame with PIL (for better text rendering)
            img = Image.new('RGB', (width, height), color=(0, 128, 128)) # Teal background
            draw = ImageDraw.Draw(img)
            
            # Simple fade-in logic (change opacity/color based on frame index)
            opacity = min(255, int((i / (fps * 2)) * 255)) 
            fill_color = (255, 255, 255) if i > fps else (opacity, opacity, opacity)
            
            # Draw Text (Use a default font or load a .ttf)
            draw.text((width//2, height//2), text, fill=fill_color, anchor="mm", align="center")
            draw.text((width//2, height-200), "www.parenteenkenya.co.ke", fill=(255, 255, 0), anchor="mm")

            # 2. Convert PIL to OpenCV format (BGR)
            frame = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
            video.write(frame)

        video.release()
        
        with open(tmp.name, "rb") as f:
            data = f.read()
    
    os.remove(tmp.name)
    return data

# --- ROUTES ---

@app.get("/api/manual")
def manual_quote(quote: str):
    video_data = generate_video_stream(quote)
    return Response(content=video_data, media_type="video/mp4")

@app.get("/api/from-blog")
def blog_quote(url: str = Query(..., description="Full URL of the blog post")):
    blog_data = fetch_blog_content(url)
    video_data = generate_video_stream(blog_data['text'])
    return Response(content=video_data, media_type="video/mp4")
