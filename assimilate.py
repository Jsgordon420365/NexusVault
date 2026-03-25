import re
import shutil
import uuid
import logging
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def extract_metadata(text):
    # Extract wiki-links for cross-referencing (Ref Section 4.2)
    links = re.findall(r'\[\[(.*?)\]\]', text)
    return list(set(links))

def generate_frontmatter(title, source_filename, links):
    timestamp_id = datetime.now().strftime("%Y%m%d%H%M%S")
    unique_id = f"{timestamp_id}-{uuid.uuid4().hex[:4]}"
    
    # Format links for YAML (Ref Section 3.4)
    out_links = "\n".join([f"  - \"[[{l}]]\"" for l in links])
    link_section = f"\nrelated_concepts:\n{out_links}" if links else ""
    
    return f"""---
id: {unique_id}
title: "{title}"
created: {datetime.now().strftime("%Y-%m-%d")}
type: atomic-concept
status: permanent
source: "[[{source_filename}]]"{link_section}
confidence: high
author: agentic-pipeline-v3
tags: [assimilated, granular-memory, legal-standard]
---
"""

def process_vault():
    base_dir = Path.cwd()
    input_file = base_dir / "source_document.md"
    concepts_dir = base_dir / "03_Concepts"
    sources_dir = base_dir / "02_Sources"
    
    for d in [concepts_dir, sources_dir]: d.mkdir(exist_ok=True)
    if not input_file.exists(): return

    shutil.copy2(input_file, sources_dir / input_file.name)

    with open(input_file, 'r') as f:
        content = f.read()

    # Maximum Granularity: Split at any header level (Ref Section 8.2)
    chunks = re.split(r'\n(?=#{1,3} )', content)
    
    for i, chunk in enumerate(chunks):
        lines = chunk.strip().split('\n')
        if not lines: continue
        
        # Clean Title and Level (Ref Section 3.3)
        header_match = re.match(r'^(#{1,3}) (.*)', lines[0])
        if header_match:
            level = len(header_match.group(1))
            title = header_match.group(2).strip()
            body = '\n'.join(lines[1:]).strip()
        else:
            level = 4
            title = f"Data Fragment {i}"
            body = chunk

        links = extract_metadata(body)
        filename = f"{re.sub(r'[\\/*?:\u0022<>|]', '', title)[:50]}.md"
        
        frontmatter = generate_frontmatter(title, input_file.name, links)
        
        # Strict Provenance Block (Ref Section 6.4)
        provenance = f"\n\n---\n**Provenance**\nSource: [[{input_file.name}]]\nProcessed: {datetime.now().isoformat()}\nGranularity: Level {level}"
        
        with open(concepts_dir / filename, 'w') as out:
            out.write(f"{frontmatter}\n# {title}\n\n{body}{provenance}")
            
    logging.info(f"Metabolism complete. Generated {len(chunks)} hyper-granular nodes.")

if __name__ == "__main__":
    process_vault()
