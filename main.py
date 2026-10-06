from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse

app = FastAPI()

# A simple inbox to store the current conversation state
inbox = {
    "current_prompt": None,
    "friend_reply": None
}

def reply_json(text):
    """Helper to format the OpenAI JSON structure"""
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
    
    # Extract the user's prompt
    user_text = "No text"
    if "messages" in data and len(data["messages"]) > 0:
        user_text = data["messages"][-1].get("content", "").strip()
        
    # 1. If the user is just checking for an update
    if user_text.lower() in ["check", "update"]:
        if inbox["friend_reply"]:
            answer = inbox["friend_reply"]
            # Clear the inbox after sending the answer
            inbox["friend_reply"] = None 
            inbox["current_prompt"] = None
            return reply_json(answer)
        else:
            return reply_json("⏳ Your friend is still typing... Type 'check' again in a moment.")
            
    # 2. Otherwise, it's a new prompt. Put it in the inbox.
    inbox["current_prompt"] = user_text
    inbox["friend_reply"] = None 
    
    return reply_json("✅ Message delivered to your friend! Type 'check' when you want to see their reply.")

# --- The interface for your friend ---

@app.get("/friend", response_class=HTMLResponse)
async def friend_dashboard():
    html = """
    <html>
    <head><title>AI Control Panel</title></head>
    <body style="font-family: sans-serif; padding: 20px; background: #f9f9f9;">
        <h2>Incoming Message</h2>
    """
    
    if not inbox["current_prompt"]:
        html += "<p style='color: #666;'>No pending messages. Waiting...</p>"
    elif inbox["friend_reply"]:
        html += "<p style='color: green;'>Reply saved! Waiting for them to type 'check' in the app to receive it.</p>"
    else:
        html += f"""
        <div style="background: white; border: 1px solid #ccc; padding: 15px; border-radius: 8px;">
            <p><strong>They said:</strong> {inbox['current_prompt']}</p>
            <form action="/answer" method="post" style="display: flex; gap: 10px; margin-top: 15px;">
                <input type="text" name="reply" placeholder="Type your response..." style="flex-grow: 1; padding: 10px; border-radius: 4px;" required autocomplete="off"/>
                <button type="submit" style="padding: 10px 20px; background: #007bff; color: white; border: none; border-radius: 4px;">Save Reply</button>
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
