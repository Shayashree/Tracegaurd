"""Document search tool for local knowledge base."""
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from backend.config import settings
from backend.tools.base import BaseTool

class DocumentSearchArgs(BaseModel):
    query: str = Field(..., min_length=1, description="Keywords or question to search within documents")
    max_results: Optional[int] = Field(5, ge=1, le=20, description="Maximum number of passage snippets to return")

class DocumentSearchTool(BaseTool):
    name = "document_search"
    description = (
        "Search the local text document collection for matching passages and policies. "
        "Returns relevant excerpts with document IDs, filenames, and evidence snippets."
    )
    args_schema = DocumentSearchArgs

    def __init__(self, docs_dir: Optional[Path] = None):
        self.docs_dir = Path(docs_dir) if docs_dir else settings.documents_dir_path

    def _extract_doc_id(self, text: str, filename: str) -> str:
        """Attempt to extract Document ID: DOC-... from text or fallback to filename."""
        match = re.search(r"Document ID:\s*([A-Z0-9_\-]+)", text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return filename

    def _run(self, args: DocumentSearchArgs) -> dict:
        if not self.docs_dir.exists():
            return {
                "count": 0,
                "matches": [],
                "message": f"Document directory does not exist: {self.docs_dir}"
            }

        query_terms = [t.lower() for t in re.findall(r"\w+", args.query) if len(t) > 1]
        if not query_terms:
            return {
                "count": 0,
                "matches": [],
                "message": f"Query '{args.query}' did not contain searchable terms."
            }

        matches: List[Dict[str, Any]] = []

        # Iterate through text/markdown files
        for doc_file in sorted(self.docs_dir.glob("*.txt")):
            try:
                content = doc_file.read_text(encoding="utf-8")
            except Exception:
                continue

            doc_id = self._extract_doc_id(content, doc_file.name)
            # Split into paragraphs or numbered lines
            sections = [s.strip() for s in content.split("\n\n") if s.strip()]
            if not sections:
                sections = [l.strip() for l in content.splitlines() if l.strip()]

            for sec in sections:
                sec_lower = sec.lower()
                # Compute term relevance score
                matched_count = sum(1 for term in query_terms if term in sec_lower)
                if matched_count > 0:
                    matches.append({
                        "document_id": doc_id,
                        "filename": doc_file.name,
                        "snippet": sec,
                        "score": matched_count
                    })

        # Sort matches by relevance score descending
        matches.sort(key=lambda x: x["score"], reverse=True)
        top_matches = matches[:args.max_results]

        if not top_matches:
            return {
                "count": 0,
                "matches": [],
                "message": f"No relevant evidence found for query: '{args.query}'"
            }

        return {
            "count": len(top_matches),
            "matches": [
                {
                    "document_id": m["document_id"],
                    "filename": m["filename"],
                    "snippet": m["snippet"]
                }
                for m in top_matches
            ],
            "message": f"Found {len(top_matches)} relevant passage(s)."
        }
