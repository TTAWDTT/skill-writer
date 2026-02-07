
import logging
from typing import Optional, Dict, Any, Tuple
from backend.core.llm.gemini_client import GeminiClient
from backend.core.diagrams.infographic import render_infographic_png_svg

logger = logging.getLogger(__name__)

class SmartDiagramGenerator:
    """
    Generates high-quality research diagrams by:
    1. Using Gemini to analyze text and extract structured data (JSON).
    2. Using local Infographic engine to render the JSON into PNG/SVG.
    """

    def __init__(self, gemini_key: Optional[str] = None):
        self.client = GeminiClient(api_key=gemini_key)

    async def generate(self, context_text: str, diagram_type: str, title: str = "") -> Tuple[bytes, str]:
        """
        Returns (png_bytes, svg_text)
        """
        if diagram_type == "technical_route":
            spec = await self._generate_technical_route_spec(context_text, title)
        elif diagram_type == "research_framework":
            spec = await self._generate_research_framework_spec(context_text, title)
        else:
            raise ValueError(f"Unknown diagram type: {diagram_type}")

        # Render locally
        png, svg, _ = render_infographic_png_svg(diagram_type, spec, title=spec.get("title", title))
        return png, svg

    async def _generate_technical_route_spec(self, text: str, title: str) -> Dict[str, Any]:
        prompt = f"""
        You are a Research Architect. Analyze the following research proposal text and design a "Technical Route" (Technological Roadmap).

        Input Text:
        {text[:8000]}

        Task:
        Extract the key research stages, steps, and methods to form a structured technical route.

        Output format (JSON):
        {{
            "title": "{title or 'Technical Route'}",
            "stages": [
                {{
                    "title": "Stage Name (e.g., Data Collection)",
                    "bullets": ["Method 1", "Key Activity", "Output"]
                }},
                ... (3 to 6 stages)
            ]
        }}

        Constraints:
        1. "stages" must be a list of 3-6 items.
        2. Each "bullets" list should have 2-4 concise items (short phrases).
        3. Use professional academic language (Chinese).
        4. JSON only.
        """
        return await self.client.generate_json(prompt)

    async def _generate_research_framework_spec(self, text: str, title: str) -> Dict[str, Any]:
        prompt = f"""
        You are a Research Architect. Analyze the following research proposal text and design a "Research Framework" structure.

        Input Text:
        {text[:8000]}

        Task:
        Structure the research into Goal, Hypotheses, Support, Work Packages (WPs), and Outcomes.

        Output format (JSON):
        {{
            "title": "{title or 'Research Framework'}",
            "goal": {{ "title": "Research Goal", "bullets": ["Core Goal 1", "Core Goal 2"] }},
            "hypotheses": {{ "title": "Scientific Issues", "bullets": ["Issue 1", "Issue 2"] }},
            "support": {{ "title": "Support/Foundation", "bullets": ["Data", "Equipment"] }},
            "work_packages": [
                {{ "title": "WP1: Name", "bullets": ["Task 1", "Method 1"] }},
                ... (3 work packages)
            ],
            "outcomes": {{ "title": "Expected Outcomes", "bullets": ["Paper", "System", "Patent"] }}
        }}

        Constraints:
        1. "work_packages" must have exactly 3 items.
        2. "bullets" should be concise (2-4 items).
        3. Use professional academic language (Chinese).
        4. JSON only.
        """
        return await self.client.generate_json(prompt)
