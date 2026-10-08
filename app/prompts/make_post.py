"""Prompt templates for the make-post tool."""

MAKE_POST_SYSTEM_PROMPT = (
    "Return only valid HTML. No markdown, code fences, or explanations."
)


def get_generate_post_prompt(current_post: str, new_text: str) -> str:
    """Build the make-post user prompt from legacy template."""
    return f"""Given:  
1. Current Post in HTML format (can be an empty string).  
2. New Text Content (plain text, may contain unwanted line breaks, bad formatting, or non-meaningful words, e.g., extracted from PDFs).  

Current Post: `{current_post}`  
New Text Content: `{new_text}`  

Task:  
1. Clean the `new_text` by removing unwanted line breaks, fixing formatting, and removing non-meaningful or redundant words.  
2. Optionally summarize or rephrase the `new_text` to make it clear and meaningful **without changing its meaning**.  
3. Merge the cleaned text into the current post and return a **final clean HTML post**.  

Rules:  
1. If `current_post` is empty → create a new post using only the cleaned text.  
2. If `current_post` exists → seamlessly merge the cleaned text into it, preserving structure.  
3. Apply a **minimal, consistent text style** to the entire post:  
   - Body:  
     - Font: system-ui, sans-serif  
     - Max width: 600px  
     - Line height: 1.6  
     - Font size: 16px  
     - Text color: #222  
     - Padding: 16px  
   - Headings (`h1`, `h2`, `h3`):  
     - Font: Georgia, serif  
     - Font weight: 600  
     - Line height: 1.3  
     - Color: #111  
     - Margins: top 1em, bottom 0.5em  

4. Use only clean semantic HTML (e.g., `<div>`, `<p>`, `<h1>`–`<h3>`). No inline JavaScript, no external libraries.  
5. Output must be **valid HTML** (parsable and renderable in a browser).  
6. Do not include markdown, code fences, explanations, or extra text. Return the **final HTML only**.  
"""
