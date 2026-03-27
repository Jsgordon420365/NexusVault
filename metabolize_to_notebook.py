import json
import re
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def create_notebook_vault():
    base_dir = Path.cwd()
    input_file = base_dir / "conversations.json"
    output_dir = base_dir / "NotebookVault"
    output_dir.mkdir(exist_ok=True)
    
    if not input_file.exists(): return

    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # To stay under 250 files, we will take the top 240 most substantial conversations
    # Sort by text length as a proxy for 'importance'
    sorted_convs = sorted(data, key=lambda x: sum(len(m.get('text', '')) for m in x.get('chat_messages', [])), reverse=True)
    top_convs = sorted_convs[:240]

    for conv in top_convs:
        title = conv.get('name', 'Untitled').strip()
        safe_title = re.sub(r'[\\/*?:\u0022<>|]', '', title)[:50]
        
        full_text = []
        tags = set()
        
        for msg in conv.get('chat_messages', []):
            role = msg.get('sender', 'unknown').upper()
            text = msg.get('text', '')
            
            # Simple Tag Extraction (Dominant Terms)
            found_tags = re.findall(r'\b(python|javascript|css|html|sql|api|json|vault|obsidian|legal|contract)\b', text.lower())
            tags.update(found_tags)
            
            full_text.append(f"### {role}\n{text}\n")

        filename = f"{safe_title}.md"
        with open(output_dir / filename, 'w', encoding='utf-8') as out:
            tag_str = ", ".join(list(tags))
            out.write(f"--- \ntitle: \"{title}\"\ntags: [{tag_str}]\ntype: notebook-source\n---\n\n# {title}\n\n" + "\n".join(full_text))

    logging.info(f"NotebookVault created with {len(top_convs)} consolidated files.")

if __name__ == "__main__":
    create_notebook_vault()
