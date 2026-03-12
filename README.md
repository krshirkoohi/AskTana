# Tana Chat Server (Mobile-Optimized)

A standalone Python server that turns any Tana node into a real-time AI chat interface. Optimized for the Tana Mobile app, but works anywhere.

## Features
- **Real-Time Polling**: Watches for new messages in Tana and responds instantly.
- **Mobile Optimized**: Uses a `⏳ Thinking...` state for immediate visual feedback on mobile.
- **Structured Responses**: Formats AI output into clean, indented Tana nodes.
- **Persistent State**: Uses a local SQLite database to track processed messages and handle crashes/sleep gracefully.
- **Multi-Chat Support**: Process multiple conversations in parallel.

## Prerequisites
1. **Tana Desktop**: Must be running with MCP enabled (Settings > Developers > Enable MCP).
2. **Python 3.9+**.
3. **Gemini CLI**: This server currently uses the [Gemini CLI](https://github.com/google/gemini-cli) for inference.

## Setup

1. **Clone the repo**:
   ```bash
   git clone https://github.com/yourusername/tana-chat-server.git
   cd tana-chat-server
   ```

2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment**:
   - Copy `.env.example` to `.env`.
   - Add your `TANA_TOKEN` (found in Tana Settings).
   - Ensure `GEMINI_PATH` points to your Gemini CLI executable.

4. **Tana Configuration**:
   - Create a supertag in Tana named `#AI Chat (Prototype)`.
   - Ensure the tag has a field (or uses the default) that the server can scan.

5. **Start the Server**:
   ```bash
   python tana_chat_server.py
   ```

## How to Use
1. On your phone (or desktop), create a node with the `#AI Chat (Prototype)` tag.
2. Type a message.
3. Press Enter to create an empty child node.
4. The server will detect the empty node, rename it to `⏳ Thinking...`, and then deliver the AI response.

## License
MIT
