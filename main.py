from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
import asyncio
import re

app = FastAPI()

# Hold pending requests using asyncio.Event
pending_tasks = {}
task_counter = 0

def clean_text(raw_text):
    """Strips the app's hidden system prompt and metadata from the message"""
    # Remove the intent and rules block
    cleaned = re.sub(r'DETECTED INTENT:.*?STRICT RESPONSE TEMPLATE:.*?examples\.', '', raw_text, flags=re.IGNORECASE | re.DOTALL)
    # Remove any stray system instructions
    cleaned = re.sub(r'ANSWER SHAPE:.*?maxInitialLatencyMs: \d+', '', cleaned, flags=re.IGNORECASE | re.DOTALL)
    cleaned = cleaned.strip()
    return cleaned if cleaned else "Screenshot uploaded (no text prompt)."

@app.post("/v1/chat/completions")
async def ai_endpoint(request: Request):
    global task_counter
    task_id = task_counter
    task_counter += 1
    
    data = await request.json()
    
    # 1. Extract and clean the text prompt
    user_text = "No text"
    if "messages" in data and len(data["messages"]) > 0:
        content = data["messages"][-1].get("content")
        if isinstance(content, str):
            user_text = content
        elif isinstance(content, list):
            text_parts = [item["text"] for item in content if item.get("type") == "text"]
            if text_parts:
                user_text = " ".join(text_parts)
                
    cleaned_prompt = clean_text(user_text)
    
    # 2. Extract the image
    image_data = data.get("image", "")
    if not image_data and "messages" in data and len(data["messages"]) > 0:
        content = data["messages"][-1].get("content")
        if isinstance(content, list):
            for item in content:
                if item.get("type") == "image_url":
                    image_data = item.get("image_url", {}).get("url", "")
                    break

    if image_data == "{{IMAGE_BASE64}}" or not image_data:
        image_data = None
    elif not image_data.startswith("data:image"):
        image_data = f"data:image/jpeg;base64,{image_data}"
        
    # 3. Create the event to pause this request
    event = asyncio.Event()
    pending_tasks[task_id] = {
        "event": event, 
        "prompt": cleaned_prompt, 
        "image": image_data,
        "answer": None
    }
    
    # 4. HOLD THE CONNECTION OPEN until your friend replies
    await event.wait()
    
    # 5. Grab the answer and clean up
    answer = pending_tasks[task_id]["answer"]
    del pending_tasks[task_id] 
    
    # Return directly to the app!
    return {
        "choices": [{
            "message": {
                "role": "assistant",
                "content": answer
            }
        }]
    }

# --- The interface for your friend ---

@app.get("/friend", response_class=HTMLResponse)
async def friend_dashboard():
    html = """
    <html>
    <head><title>AI Control Panel</title></head>
    <body style="font-family: sans-serif; padding: 20px; background: #f9f9f9;">
        <h2>Incoming API Requests</h2>
    """
    
    if not pending_tasks:
        html += "<p style='color: #666;'>No active requests. Waiting for the app...</p>"
        
    for tid, task in pending_tasks.items():
        html += f"""
        <div style="background: white; border: 1px solid #ccc; padding: 15px; margin-bottom: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
            <p><strong>App text:</strong> {task['prompt']}</p>
        """
        
        if task["image"]:
            html += f"""
            <div style="margin-top: 15px; margin-bottom: 15px;">
                <strong>Screenshot:</strong><br>
                <img src="{task['image']}" style="max-width: 100%; max-height: 500px; border: 1px solid #ddd; border-radius: 4px; margin-top: 5px;">
            </div>
            """
            
        html += f"""
            <form action="/answer/{tid}" method="post" style="display: flex; gap: 10px; margin-top: 15px;">
                <input type="text" name="reply" placeholder="Type your response..." style="flex-grow: 1; padding: 10px; border-radius: 4px; border: 1px solid #aaa;" required autocomplete="off"/>
                <button type="submit" style="padding: 10px 20px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer;">Send to App</button>
            </form>
        </div>
        """
        
    html += """
        <script>
            setInterval(() => {
                const inputFields = document.querySelectorAll('input[name="reply"]');
                let isTyping = false;
                inputFields.forEach(input => {
                    if (input.value.trim() !== '' || document.activeElement === input) {
                        isTyping = true;
                    }
                });
                if (!isTyping) {
                    location.reload();
                }
            }, 2000);
        </script>
    </body>
    </html>
    """
    return html

@app.post("/answer/{task_id}")
async def submit_answer(task_id: int, reply: str = Form(...)):
    if task_id in pending_tasks:
        pending_tasks[task_id]["answer"] = reply
        # This instantly resumes the paused API request and fires the text back to your app!
        pending_tasks[task_id]["event"].set() 
        
    return RedirectResponse(url="/friend", status_code=303)
