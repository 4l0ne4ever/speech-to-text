"""
PDF Text Extractor for Japanese Slides

Extracts text, structure, and metadata from PDF files using PyMuPDF.
Supports Japanese text and identifies slide structure (titles, bullets, body).
"""

import fitz  # PyMuPDF
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class TextBlock:
    """Represents a text block extracted from PDF"""
    text: str
    page_number: int
    bbox: Tuple[float, float, float, float]  # (x0, y0, x1, y1)
    font_size: float
    font_name: str
    block_type: str  # 'title', 'heading', 'bullet', 'body'
    position: int  # Position within page


@dataclass
class SlideContent:
    """Represents processed content from one slide"""
    page_number: int
    title: Optional[str]
    headings: List[str]
    bullets: List[str]
    body: List[str]
    all_text: str
    text_blocks: List[TextBlock]


class PDFExtractor:
    """
    Extract text and structure from PDF slides.
    
    Uses PyMuPDF to extract text with position and font information,
    then identifies slide structure based on heuristics.
    """
    
    def __init__(self, 
                 title_font_size_threshold: float = 18.0,
                 heading_font_size_threshold: float = 14.0,
                 bullet_chars: str = "•●○◦▪▫■□-・"):
        """
        Initialize PDF extractor.
        
        Args:
            title_font_size_threshold: Font size threshold for title detection
            heading_font_size_threshold: Font size threshold for heading detection
            bullet_chars: Characters that indicate bullet points
        """
        self.title_font_size_threshold = title_font_size_threshold
        self.heading_font_size_threshold = heading_font_size_threshold
        self.bullet_chars = bullet_chars
        
    def extract_from_file(self, pdf_path: str) -> List[SlideContent]:
        """
        Extract content from PDF file.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            List of SlideContent objects, one per page
        """
        logger.info(f"Extracting content from PDF: {pdf_path}")
        
        try:
            doc = fitz.open(pdf_path)
            slides = []
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                slide_content = self._extract_page_content(page, page_num + 1)
                slides.append(slide_content)
                
            doc.close()
            logger.info(f"Extracted {len(slides)} slides from PDF")
            return slides
            
        except Exception as e:
            logger.error(f"Error extracting PDF content: {e}")
            raise
            
    def _extract_page_content(self, page: fitz.Page, page_number: int) -> SlideContent:
        """Extract and structure content from a single page"""
        
        # Extract text blocks with metadata
        text_blocks = self._extract_text_blocks(page, page_number)
        
        # Classify blocks by type
        classified_blocks = self._classify_blocks(text_blocks)
        
        # Organize into structure
        title = self._extract_title(classified_blocks)
        headings = self._extract_headings(classified_blocks)
        bullets = self._extract_bullets(classified_blocks)
        body = self._extract_body(classified_blocks)
        
        # Combine all text
        all_text = " ".join([
            title or "",
            " ".join(headings),
            " ".join(bullets),
            " ".join(body)
        ]).strip()
        
        return SlideContent(
            page_number=page_number,
            title=title,
            headings=headings,
            bullets=bullets,
            body=body,
            all_text=all_text,
            text_blocks=text_blocks
        )
        
    def _extract_text_blocks(self, page: fitz.Page, page_number: int) -> List[TextBlock]:
        """Extract raw text blocks with metadata from page"""
        
        text_blocks = []
        blocks = page.get_text("dict")["blocks"]
        
        for block_idx, block in enumerate(blocks):
            if block["type"] == 0:  # Text block
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text = span["text"].strip()
                        if text:  # Skip empty text
                            text_block = TextBlock(
                                text=text,
                                page_number=page_number,
                                bbox=(span["bbox"][0], span["bbox"][1], 
                                     span["bbox"][2], span["bbox"][3]),
                                font_size=span["size"],
                                font_name=span["font"],
                                block_type="unknown",  # Will be classified later
                                position=block_idx
                            )
                            text_blocks.append(text_block)
                            
        return text_blocks
        
    def _classify_blocks(self, text_blocks: List[TextBlock]) -> List[TextBlock]:
        """Classify text blocks by type (title, heading, bullet, body)"""
        
        if not text_blocks:
            return text_blocks
            
        # Find max font size for relative comparison
        max_font_size = max(block.font_size for block in text_blocks)
        
        for block in text_blocks:
            # Classify by font size and position
            if block.position == 0 and block.font_size >= self.title_font_size_threshold:
                block.block_type = "title"
            elif block.font_size >= self.heading_font_size_threshold:
                block.block_type = "heading"
            elif any(block.text.startswith(char) for char in self.bullet_chars):
                block.block_type = "bullet"
            else:
                block.block_type = "body"
                
        return text_blocks
        
    def _extract_title(self, text_blocks: List[TextBlock]) -> Optional[str]:
        """Extract slide title (first title block)"""
        titles = [block.text for block in text_blocks if block.block_type == "title"]
        return titles[0] if titles else None
        
    def _extract_headings(self, text_blocks: List[TextBlock]) -> List[str]:
        """Extract headings"""
        return [block.text for block in text_blocks if block.block_type == "heading"]
        
    def _extract_bullets(self, text_blocks: List[TextBlock]) -> List[str]:
        """Extract bullet points"""
        bullets = []
        for block in text_blocks:
            if block.block_type == "bullet":
                # Remove bullet character
                text = block.text
                for char in self.bullet_chars:
                    if text.startswith(char):
                        text = text[len(char):].strip()
                        break
                bullets.append(text)
        return bullets
        
    def _extract_body(self, text_blocks: List[TextBlock]) -> List[str]:
        """Extract body text"""
        return [block.text for block in text_blocks if block.block_type == "body"]
        
    def extract_metadata(self, pdf_path: str) -> Dict[str, Any]:
        """
        Extract PDF metadata.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Dictionary with metadata (page_count, title, author, etc.)
        """
        try:
            doc = fitz.open(pdf_path)
            metadata = {
                "page_count": len(doc),
                "title": doc.metadata.get("title", ""),
                "author": doc.metadata.get("author", ""),
                "subject": doc.metadata.get("subject", ""),
                "creator": doc.metadata.get("creator", ""),
                "producer": doc.metadata.get("producer", ""),
                "format": doc.metadata.get("format", ""),
            }
            doc.close()
            return metadata
        except Exception as e:
            logger.error(f"Error extracting PDF metadata: {e}")
            raise
