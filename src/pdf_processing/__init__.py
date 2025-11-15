"""
PDF Processing Module for Phase 4: Slide Synchronization

This module provides functionality to extract and process content from PDF slides
for matching with speech transcripts.

Components:
- PDFExtractor: Extract text and structure from PDF files
- JapaneseNLP: Japanese text processing and normalization
- KeywordIndexer: TF-IDF based keyword extraction and indexing
- EmbeddingGenerator: Semantic embeddings for slides
"""

from .pdf_extractor import PDFExtractor
from .japanese_nlp import JapaneseNLP
from .keyword_indexer import KeywordIndexer
from .embedding_generator import EmbeddingGenerator

__all__ = [
    'PDFExtractor',
    'JapaneseNLP',
    'KeywordIndexer',
    'EmbeddingGenerator',
]
