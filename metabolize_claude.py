import json
import re
import uuid
import logging
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def process_claude_export():
    base_dir = Path.cwd()
    input_file = base_dir / "conversations.json"
    concepts_dir = base_dir / "03_Concepts"
    code_dir = base_dir / "04_Code"
    
    for d in [concepts_dir, code_dir]: d.mkdir(parents=True, exist_ok=True)
    
    if not input_file.exists():
        logging.error("conversations.json not found in current directory.")
        return

    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Claude JSON is a list of conversation objects
    for conv in data:
        conv_title = conv.get('name', 'Untitled Conversation')
        chat_id = conv.get('uuid', uuid.uuid4().hex[:8])
        chat_date = datetime.now().strftime("%Y-%m-%d") # Use current if not in root
        
        # Collect all assistant messages that have code
        extracted_assets = []
        
        # Claude chat messages are usually in 'chat_messages'
        for msg in conv.get('chat_messages', []):
            if msg.get('sender') == 'assistant':
                text = msg.get('text', '')
                # Hunt for fenced code blocks
                code_blocks = re.findall(r'```(\w*)\n(.*?)\n```', text, re.DOTALL)
                
                for lang, code in code_blocks:
                    lang = lang.strip() or "txt"
                    asset_id = uuid.uuid4().hex[:4]
                    code_filename = f"claude_{asset_id}.{lang if lang != 'python' else 'py'}"
                    
                    with open(code_dir / code_filename, 'w', encoding='utf-8') as cf:
                        cf.write(f"// Context: {conv_title}\n// Source: Claude Export\n\n{code}")
                    
                    extracted_assets.append(f"- [[{code_filename}]] ({lang})")

        # Create the Concept Note if code was found
        if extracted_assets:
            filename = f"Chat_{re.sub(r'[\\/*?:\u0022<>|]', '', conv_title)[:50]}.md"
            with open(concepts_dir / filename, 'w', encoding='utf-8') as out:
                out.write(f"--- \ntype: chat-history\nsource: claude-export\ndate: {chat_date}\n---\n\n# {conv_title}\n\nThis node contains code assets extracted from a Claude conversation.\n\n### Extracted Code\n" + "\n".join(extracted_assets))

    logging.info("Claude metabolism complete.")

if __name__ == "__main__":
    process_claude_export()
