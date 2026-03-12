import os
import json
import asyncio
import aiohttp
import sqlite3
import time
import re
import subprocess
from dotenv import load_dotenv

# --- Local Path Resolution ---
# Ensures all files (DB, logs, .env) stay within the script's folder
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

# --- Configuration (from .env) ---
TANA_TOKEN = os.getenv("TANA_TOKEN")
TANA_URL = os.getenv("TANA_URL", "http://127.0.0.1:8262/mcp")
GEMINI_PATH = os.getenv("GEMINI_PATH", "gemini")
DB_PATH = os.path.join(BASE_DIR, "state.db")

# --- Fixed Supertag IDs ---
# These are the default IDs for a fresh workspace implementation
CHAT_TAG_ID = "Y_bFazilblQ2" # Default for #AI Chat (Prototype)
FIELD_CHAT_ID = "b1L_j8Bfspju" # Default for Chat ID field
FIELD_MODEL = "VyI2uZi7mg8m" # Default for AI Model field

# --- Database Setup ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS processed_nodes (node_id TEXT PRIMARY KEY, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)")
    conn.commit()
    conn.close()

def is_processed(node_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT node_id FROM processed_nodes WHERE node_id = ?", (node_id,))
    res = c.fetchone()
    conn.close()
    return res is not None

def mark_processed(node_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO processed_nodes (node_id) VALUES (?)", (node_id,))
    conn.commit()
    conn.close()

# --- Concurrency Management ---
TANA_SEMAPHORE = asyncio.Semaphore(1) # Tana Desktop Bridge is single-threaded

async def call_mcp(session, method, params, retries=3):
    payload = {"jsonrpc": "2.0", "method": "tools/call", "params": {"name": method, "arguments": params}, "id": 1}
    headers = {
        "Authorization": f"Bearer {TANA_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream"
    }
    
    for attempt in range(retries):
        async with TANA_SEMAPHORE:
            try:
                async with session.post(TANA_URL, json=payload, headers=headers, timeout=30) as response:
                    if response.status == 200:
                        json_res = await response.json()
                        result = json_res.get("result", {})
                        if "content" in result and isinstance(result["content"], list):
                            text_content = result["content"][0].get("text", "")
                            try: return json.loads(text_content)
                            except: return text_content
                        return result
                    elif response.status == 500:
                        await asyncio.sleep(1)
                        continue
                    else:
                        return None
            except Exception as e:
                if attempt < retries - 1:
                    await asyncio.sleep(1)
                    continue
                return None
    return None

async def get_gemini_response(prompt, session_id=None, model=None):
    cmd = [GEMINI_PATH, "-p", prompt, "--yolo", "--output-format", "json"]
    if model: cmd.extend(["-m", model])
    if session_id: cmd.extend(["--resume", session_id])
    
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            cwd=BASE_DIR
        )
        stdout, stderr = await process.communicate()
        out = stdout.decode().strip()
        
        j_start = out.find('{')
        if j_start != -1:
            data = json.loads(out[j_start:])
            resp = data.get("response", "")
            return resp.strip(), data.get("session_id")
        return out, None
    except:
        return f"Error: Failed to call {GEMINI_PATH}", None

async def process_chat(session, chat_node):
    c_id = chat_node["id"]
    c_name = chat_node.get("name", "Chat")
    
    # 1. Check for new messages or stuck Thinking nodes
    res = await call_mcp(session, "get_children", {"nodeId": c_id})
    if not res or "children" not in res: return
    nodes = [c for c in res["children"] if c.get("docType") != "tuple"]

    for i in range(len(nodes) - 1, 0, -1):
        placeholder = nodes[i]
        msg = nodes[i-1]
        m_id, m_text, p_text = msg["id"], msg["name"].strip(), placeholder["name"].strip()
        
        is_new = not is_processed(m_id) and m_text and not p_text and not m_text.startswith("🤖")
        is_stuck = p_text == "⏳ Thinking..." and not is_processed(placeholder["id"])

        if is_new or is_stuck:
            mark_processed(m_id)
            mark_processed(placeholder["id"])
            
            if is_new: await call_mcp(session, "edit_node", {"nodeId": placeholder["id"], "name": {"old_string": "", "new_string": "⏳ Thinking..."}})
            
            # 2. Inference
            response, new_id = await get_gemini_response(m_text)
            
            if response:
                # 3. Formatted Delivery
                lines = [l.strip() for l in response.split('\n') if l.strip()]
                paste = f"%%tana%%\n- !! 🤖 Assistant:\n"
                current_indent = "  "
                for line in lines:
                    is_header = re.match(r'^(\*\*|__)?(\d+\.|\*|-|#+)\s+', line)
                    if is_header:
                        paste += f"  - {line}\n"
                        current_indent = "    "
                    else:
                        paste += f"{current_indent}- {line}\n"
                
                await call_mcp(session, "import_tana_paste", {"parentNodeId": c_id, "content": paste})
                await call_mcp(session, "trash_node", {"nodeId": placeholder["id"]})
                break

async def main():
    print(f"[{time.strftime('%H:%M:%S')}] 🚀 Tana Chat Engine starting...")
    init_db()
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                res = await call_mcp(session, "search_nodes", {"query": {"hasType": CHAT_TAG_ID}})
                all_chats = res if isinstance(res, list) else []
                chats = [c for c in all_chats if not c.get("inTrash", False)]
                
                if chats:
                    tasks = [process_chat(session, chat) for chat in chats]
                    await asyncio.gather(*tasks)
            except Exception as e:
                print(f"[{time.strftime('%H:%M:%S')}] ❌ Loop Error: {e}")
            await asyncio.sleep(2)

if __name__ == "__main__":
    asyncio.run(main())
