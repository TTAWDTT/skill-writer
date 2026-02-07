import logging
import os
import uuid
import sys
import traceback
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
import subprocess
import tempfile

from backend.core.llm.config_store import get_llm_config, get_llm_client
from backend.config import DATA_DIR

logger = logging.getLogger(__name__)

class SchematicsGenerator:
    """
    Generates diagrams by writing and executing Python code using
    scientific libraries (Schemdraw, Matplotlib, NetworkX, Graphviz).
    Acts as a fallback when no AI Image Model is available.
    """

    def __init__(self):
        self.output_dir = Path(DATA_DIR) / "temp_schematics"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def generate(self, context_text: str, diagram_type: str, title: str) -> Tuple[Optional[bytes], Optional[str], str]:
        """
        Generates a diagram based on text.
        Returns: (png_bytes, svg_text, code_used)
        """
        # 1. Select library and template based on intent
        library_hint, code_template = self._get_template_and_hint(diagram_type, context_text)

        # 2. Generate Python code using LLM
        code = await self._generate_code(context_text, title, library_hint, code_template)

        # 3. Execute code to generate file
        try:
            png_path, svg_path = self._execute_code(code)

            png_bytes = None
            svg_text = None

            if png_path and png_path.exists():
                png_bytes = png_path.read_bytes()

            if svg_path and svg_path.exists():
                svg_text = svg_path.read_text(encoding="utf-8", errors="ignore")

            return png_bytes, svg_text, code

        except Exception as e:
            logger.error(f"Schematics execution failed: {e}")
            raise

    def _get_template_and_hint(self, diagram_type: str, context: str) -> Tuple[str, str]:
        """Determine which library to use."""
        context_lower = context.lower()

        if "circuit" in context_lower or "circuit" in diagram_type:
            return "schemdraw", """
import schemdraw
import schemdraw.elements as elm

d = schemdraw.Drawing()
# ... add elements ...
# d.add(elm.Resistor().label('R1'))
d.save('OUTPUT_FILE.svg')
d.save('OUTPUT_FILE.png', dpi=300)
"""
        elif "pathway" in context_lower or "interaction" in context_lower:
            return "matplotlib_pathway", """
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyArrowPatch

fig, ax = plt.subplots(figsize=(10, 6))
# ... add patches and arrows ...
ax.set_xlim(0, 10)
ax.set_ylim(0, 10)
ax.axis('off')
plt.savefig('OUTPUT_FILE.png', dpi=300, bbox_inches='tight')
plt.savefig('OUTPUT_FILE.svg', bbox_inches='tight')
"""
        elif "network" in context_lower or "topology" in context_lower:
            return "networkx", """
import networkx as nx
import matplotlib.pyplot as plt

G = nx.DiGraph()
# ... add nodes and edges ...
pos = nx.spring_layout(G)
nx.draw(G, pos, with_labels=True)
plt.savefig('OUTPUT_FILE.png', dpi=300)
plt.savefig('OUTPUT_FILE.svg')
"""
        else:
            # Default to Graphviz for structural diagrams
            return "graphviz", """
import graphviz

dot = graphviz.Digraph(format='png')
dot.attr(rankdir='TB')
# ... add nodes and edges ...
dot.render('OUTPUT_FILE', cleanup=True)
# This produces OUTPUT_FILE.png and OUTPUT_FILE.svg if format set
"""

    async def _generate_code(self, context: str, title: str, lib_hint: str, template: str) -> str:
        prompt = f"""
You are a Python Data Visualization Expert.
Write a complete, runnable Python script to generate a scientific diagram based on the requirement.

Requirement:
{context[:2000]}

Diagram Title: {title}

Library to use: {lib_hint}

Template/Example:
{template}

Constraints:
1. The script MUST save the output image to a file.
2. Use the placeholder filename 'OUTPUT_FILE' (without extension, or with .png/.svg as shown in template) so I can replace it with a real path.
3. Code must be self-contained (imports included).
4. Use professional styling (white background, clear fonts).
5. Do NOT include markdown fences (```python). Just the code.
6. Handle Chinese text correctly (e.g., in Matplotlib use a font that supports Chinese if possible, or keep text simple).

Generate Python Code:
"""
        config = get_llm_config()
        client = get_llm_client(config)

        messages = [{"role": "user", "content": prompt}]
        code = await client.chat(messages, temperature=0.2)

        # Cleanup markdown
        code = code.replace("```python", "").replace("```", "").strip()
        return code

    def _execute_code(self, code: str) -> Tuple[Optional[Path], Optional[Path]]:
        """
        Execute the generated code in a separate process.
        Injects the real output path.
        """
        session_id = str(uuid.uuid4())
        base_name = self.output_dir / f"diagram_{session_id}"
        png_out = base_name.with_suffix(".png")
        svg_out = base_name.with_suffix(".svg")

        # Replace placeholders
        # Graphviz render appends extension automatically, others might need explicit extension
        # We try to handle both generic 'OUTPUT_FILE' and explicit 'OUTPUT_FILE.png'

        safe_code = code.replace("'OUTPUT_FILE.png'", f"r'{str(png_out)}'")
        safe_code = safe_code.replace("'OUTPUT_FILE.svg'", f"r'{str(svg_out)}'")
        safe_code = safe_code.replace("'OUTPUT_FILE'", f"r'{str(base_name)}'")
        safe_code = safe_code.replace('"OUTPUT_FILE.png"', f"r'{str(png_out)}'")
        safe_code = safe_code.replace('"OUTPUT_FILE.svg"', f"r'{str(svg_out)}'")
        safe_code = safe_code.replace('"OUTPUT_FILE"', f"r'{str(base_name)}'")

        # Write script to temp file
        script_path = self.output_dir / f"run_{session_id}.py"
        script_path.write_text(safe_code, encoding="utf-8")

        try:
            # Run with timeout
            result = subprocess.run(
                [sys.executable, str(script_path)],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(self.output_dir) # Execute in temp dir
            )

            if result.returncode != 0:
                logger.error(f"Diagram script error: {result.stderr}")
                raise RuntimeError(f"Script execution failed: {result.stderr}")

            # Check outputs
            # Graphviz .render('path') creates 'path.png'
            final_png = png_out if png_out.exists() else None
            final_svg = svg_out if svg_out.exists() else None

            # If graphviz used render with no format extension in name, it adds it
            if not final_png and Path(f"{str(base_name)}.png").exists():
                final_png = Path(f"{str(base_name)}.png")

            return final_png, final_svg

        finally:
            # Cleanup script
            try:
                if script_path.exists():
                    os.remove(script_path)
            except:
                pass
