import re
import shutil
import uuid
import logging
from datetime import datetime
from pathlib import Path
from typing import Tuple

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def create_vault_structure(base_dir: Path) -> Tuple[Path, Path]:
    sources_dir = base_dir / "02_Sources"
    concepts_dir = base_dir / "03_Concepts"
    
    sources_dir.mkdir(parents=True, exist_ok=True)
    concepts_dir.mkdir(parents=True, exist_ok=True)
    
    return sources_dir, concepts_dir

def clean_filename(title: str) -> str:
    cleaned = re.sub(r'[\\/*?:"<>|#]', "", title)
    return cleaned.strip()

def generate_frontmatter(title: str, source_filename: str) -> str:
    timestamp_id = datetime.now().strftime("%Y%m%d%H%M%S")
    unique_suffix = uuid.uuid4().hex[:4]
    document_id = f"{timestamp_id}-{unique_suffix}"
    
    date_created = datetime.now().strftime("%Y-%m-%d")
    
    frontmatter = f"""---
id: {document_id}
aliases: ["{title}"]
type: concept
status: "#processing"
genesis: deterministic script
confidence: high
sources: ["[[{source_filename}]]"]
date_created: {date_created}
---
"""
    return frontmatter

def chunk_markdown_document(input_filepath: Path, sources_dir: Path, concepts_dir: Path) -> None:
    if not input_filepath.exists():
        logging.error(f"Could not find {input_filepath}. Please ensure the file exists.")
        return

    source_filename = input_filepath.name
    source_destination = sources_dir / source_filename
    
    try:
        shutil.copy2(input_filepath, source_destination)
        logging.info(f"Copied immutable source to: {source_destination}")
    except IOError as e:
        logging.error(f"Failed to copy source file: {e}")
        return

    try:
        with open(input_filepath, 'r', encoding='utf-8') as file:
            content = file.read()
    except IOError as e:
        logging.error(f"Failed to read source file: {e}")
        return

    chunks = re.split(r'\n(?=## )', content)

    for index, chunk in enumerate(chunks):
        chunk = chunk.strip()
        if not chunk:
            continue

        lines = chunk.split('\n')
        first_line = lines[0].strip()
        
        if first_line.startswith('## '):
            title = first_line[3:].strip()
            body = '\n'.join(lines[1:]).strip()
        elif first_line.startswith('# '):
            title = first_line[2:].strip()
            body = '\n'.join(lines[1:]).strip()
        else:
            title = f"Extracted Section {index + 1}"
            body = chunk

        semantic_filename = f"{clean_filename(title)}.md"
        output_filepath = concepts_dir / semantic_filename
        
        frontmatter = generate_frontmatter(title, source_filename)
        final_content = f"{frontmatter}\n# {title}\n\n{body}\n"
        
        try:
            with open(output_filepath, 'w', encoding='utf-8') as out_file:
                out_file.write(final_content)
            logging.info(f"Generated atomic note: {semantic_filename}")
        except IOError as e:
            logging.error(f"Failed to write atomic note {semantic_filename}: {e}")

if __name__ == "__main__":
    current_directory = Path.cwd()
    target_input_file = current_directory / "source_document.md"
    
    dir_02, dir_03 = create_vault_structure(current_directory)
    
    logging.info("Initiating deterministic markdown-aware chunking...")
    chunk_markdown_document(target_input_file, dir_02, dir_03)
    logging.info("Assimilation pipeline complete.")
