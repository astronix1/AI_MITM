from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse

app = FastAPI()

# Inbox now stores the image as well
inbox = {
    "current_prompt": None,
    "current_image": None,
    "friend_reply": None
}

def reply_json(text):
    return {
        "choices": [{
            "message": {
                "role": "assistant",
                "content": text
            }
        }]
    }

@app.post("/v1/chat/completions")
async def ai_endpoint(request: Request):
    data = await request.json()
    
    # 1. Extract the user's text prompt
    user_text = "No text"
    if "messages" in data and len(data["messages"]) > 0:
        content = data["messages"][-1].get("content")
        # Handle standard text or OpenAI's array format
        if isinstance(content, str):
            user_text = content.strip()
        elif isinstance(content, list):
            text_parts = [item["text"] for item in content if item.get("type") == "text"]
            if text_parts:
                user_text = " ".join(text_parts).strip()
    
    # 2. If you are just checking for an update
    if user_text.lower() in ["check", "update"]:
        if inbox["friend_reply"]:
            answer = inbox["friend_reply"]
            # Clear inbox after sending
            inbox["friend_reply"] = None 
            inbox["current_prompt"] = None
            inbox["current_image"] = None
            return reply_json(answer)
        else:
            return reply_json("⏳ Your friend is still typing... Type 'check' again in a moment.")
            
    # 3. Extract the image data
    image_data = data.get("image", "")
    
    # Check if the app sent the image inside the standard OpenAI messages array instead
    if not image_data and "messages" in data and len(data["messages"]) > 0:
        content = data["messages"][-1].get("content")
        if isinstance(content, list):
            for item in content:
                if item.get("type") == "image_url":
                    image_data = item.get("image_url", {}).get("url", "")
                    break

    # Format the image correctly for the HTML <img> tag
    if image_data == "{{IMAGE_BASE64}}" or not image_data:
        image_data = None
    elif not image_data.startswith("data:image"):
        image_data = f"data:image/jpeg;base64,{image_data}"
            
    # 4. Save to inbox
    inbox["current_prompt"] = user_text
    inbox["current_image"] = image_data
    inbox["friend_reply"] = None 
    
    return reply_json("✅ Screenshot and message delivered! Type 'check' when you want to see their reply.")

# --- The interface for your friend ---

@app.get("/friend", response_class=HTMLResponse)
async def friend_dashboard():
    html = """
    <html>
    <head><title>AI Control Panel</title></head>
    <body style="font-family: sans-serif; padding: 20px; background: #f9f9f9;">
        <h2>Incoming Message</h2>
    """
    
    if not inbox["current_prompt"] and not inbox["current_image"]:
        html += "<p style='color: #666;'>No pending messages. Waiting...</p>"
    elif inbox["friend_reply"]:
        html += "<p style='color: green;'>Reply saved! Waiting for them to type 'check' in the app to receive it.</p>"
    else:
        html += f"""
        <div style="background: white; border: 1px solid #ccc; padding: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
            <p><strong>They said:</strong> {inbox['current_prompt']}</p>
        """
        
        # Inject the image if it exists
        if inbox["current_image"]:
            html += f"""
            <div style="margin-top: 15px; margin-bottom: 15px;">
                <strong>Screenshot received:</strong><br>
                <img src="{inbox['current_image']}" style="max-width: 100%; max-height: 500px; border: 1px solid #ddd; border-radius: 4px; margin-top: 5px;">
            </div>
            """
            
        html += """
            <form action="/answer" method="post" style="display: flex; gap: 10px; margin-top: 15px;">
                <input type="text" name="reply" placeholder="Type your response..." style="flex-grow: 1; padding: 10px; border-radius: 4px; border: 1px solid #aaa;" required autocomplete="off"/>
                <button type="submit" style="padding: 10px 20px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer;">Save Reply</button>
            </form>
        </div>
        """
        
    html += """
        <script>setTimeout(() => location.reload(), 2000);</script>
    </body>
    </html>
    """
    return html

@app.post("/answer")
async def submit_answer(reply: str = Form(...)):
    inbox["friend_reply"] = reply
    return RedirectResponse(url="/friend", status_code=303)
