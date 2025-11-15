"""
Japanese NLP Module for Text Processing

Provides Japanese text tokenization, normalization, and processing
using MeCab tokenizer.
"""

import MeCab
import unicodedata
import re
from typing import List, Set, Dict, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class Token:
    """Represents a tokenized word"""
    surface: str  # Original text
    base_form: str  # Dictionary form
    reading: str  # Hiragana reading
    pos: str  # Part of speech
    pos_detail: str  # Detailed POS


class JapaneseNLP:
    """
    Japanese text processing with MeCab tokenizer.
    
    Provides:
    - Tokenization into morphemes
    - Text normalization (full-width to half-width, kanji numbers)
    - Stop word removal
    - Reading extraction (furigana)
    """
    
    # Japanese stop words (particles, common verbs, etc.)
    STOP_WORDS = {
        # Particles
        'は', 'の', 'を', 'に', 'が', 'と', 'で', 'から', 'まで', 'より',
        'へ', 'や', 'か', 'も', 'ね', 'よ', 'な', 'わ', 'ば', 'ど',
        # Common verbs and auxiliaries
        'する', 'ある', 'いる', 'なる', 'れる', 'られる', 'せる', 'させる',
        'です', 'ます', 'ません', 'でした', 'ました', 'ない', 'た', 'だ',
        # Demonstratives
        'この', 'その', 'あの', 'どの', 'こう', 'そう', 'ああ', 'どう',
        'ここ', 'そこ', 'あそこ', 'どこ', 'こちら', 'そちら', 'あちら', 'どちら',
        # Common words
        'こと', 'もの', 'ため', 'よう', 'ところ', 'とき', 'ほど', 'くらい',
    }
    
    # Kanji numbers to Arabic
    KANJI_NUMBERS = {
        '零': '0', '〇': '0', 'ゼロ': '0',
        '一': '1', '二': '2', '三': '3', '四': '4', '五': '5',
        '六': '6', '七': '7', '八': '8', '九': '9', '十': '10',
        '百': '100', '千': '1000', '万': '10000',
    }
    
    def __init__(self, use_stop_words: bool = True):
        """
        Initialize Japanese NLP processor.
        
        Args:
            use_stop_words: Whether to filter stop words
        """
        self.use_stop_words = use_stop_words
        
        try:
            # Initialize MeCab with ipadic dictionary
            self.mecab = MeCab.Tagger()
            logger.info("MeCab tokenizer initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize MeCab: {e}")
            raise
            
    def tokenize(self, text: str) -> List[Token]:
        """
        Tokenize Japanese text into morphemes.
        
        Args:
            text: Input text
            
        Returns:
            List of Token objects
        """
        if not text:
            return []
            
        tokens = []
        node = self.mecab.parseToNode(text)
        
        while node:
            if node.surface:  # Skip BOS/EOS nodes
                features = node.feature.split(',')
                
                token = Token(
                    surface=node.surface,
                    base_form=features[6] if len(features) > 6 else node.surface,
                    reading=features[7] if len(features) > 7 else node.surface,
                    pos=features[0] if len(features) > 0 else "unknown",
                    pos_detail=features[1] if len(features) > 1 else "unknown"
                )
                tokens.append(token)
                
            node = node.next
            
        return tokens
        
    def extract_keywords(self, text: str) -> List[str]:
        """
        Extract content keywords (nouns, verbs, adjectives).
        
        Args:
            text: Input text
            
        Returns:
            List of keyword base forms
        """
        tokens = self.tokenize(text)
        keywords = []
        
        for token in tokens:
            # Keep nouns, verbs, and adjectives
            if token.pos in ['名詞', '動詞', '形容詞']:
                # Skip stop words
                if self.use_stop_words and token.base_form in self.STOP_WORDS:
                    continue
                # Skip single character words (usually not meaningful)
                if len(token.base_form) < 2:
                    continue
                keywords.append(token.base_form)
                
        return keywords
        
    def normalize_text(self, text: str) -> str:
        """
        Normalize Japanese text.
        
        - Convert full-width to half-width (alphanumeric)
        - Convert kanji numbers to Arabic
        - Normalize whitespace
        
        Args:
            text: Input text
            
        Returns:
            Normalized text
        """
        if not text:
            return ""
            
        # Convert full-width alphanumeric to half-width
        text = self._full_to_half(text)
        
        # Convert kanji numbers to Arabic
        text = self._kanji_to_arabic(text)
        
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
        
    def _full_to_half(self, text: str) -> str:
        """Convert full-width alphanumeric to half-width"""
        result = []
        for char in text:
            code = ord(char)
            # Full-width alphanumeric range: 0xFF01-0xFF5E
            # Convert to half-width: 0x0021-0x007E
            if 0xFF01 <= code <= 0xFF5E:
                result.append(chr(code - 0xFEE0))
            else:
                result.append(char)
        return ''.join(result)
        
    def _kanji_to_arabic(self, text: str) -> str:
        """Convert simple kanji numbers to Arabic numerals"""
        for kanji, arabic in self.KANJI_NUMBERS.items():
            text = text.replace(kanji, arabic)
        return text
        
    def get_reading(self, text: str) -> str:
        """
        Get hiragana reading of text.
        
        Args:
            text: Input text
            
        Returns:
            Hiragana reading
        """
        tokens = self.tokenize(text)
        readings = [token.reading for token in tokens]
        return ''.join(readings)
        
    def to_hiragana(self, text: str) -> str:
        """
        Convert katakana to hiragana.
        
        Args:
            text: Input text
            
        Returns:
            Text with katakana converted to hiragana
        """
        result = []
        for char in text:
            code = ord(char)
            # Katakana range: 0x30A0-0x30FF
            # Hiragana range: 0x3040-0x309F
            if 0x30A0 <= code <= 0x30FF:
                result.append(chr(code - 0x60))
            else:
                result.append(char)
        return ''.join(result)
        
    def segment_sentences(self, text: str) -> List[str]:
        """
        Segment text into sentences using Japanese punctuation.
        
        Args:
            text: Input text
            
        Returns:
            List of sentences
        """
        # Japanese sentence endings
        endings = ['。', '！', '？', '!', '?']
        
        sentences = []
        current = []
        
        for char in text:
            current.append(char)
            if char in endings:
                sentence = ''.join(current).strip()
                if sentence:
                    sentences.append(sentence)
                current = []
                
        # Add remaining text
        if current:
            sentence = ''.join(current).strip()
            if sentence:
                sentences.append(sentence)
                
        return sentences
        
    def extract_content_words(self, text: str, 
                             include_pos: Optional[Set[str]] = None) -> List[str]:
        """
        Extract content words (non-functional words).
        
        Args:
            text: Input text
            include_pos: POS tags to include (default: nouns, verbs, adjectives)
            
        Returns:
            List of content words
        """
        if include_pos is None:
            include_pos = {'名詞', '動詞', '形容詞'}
            
        tokens = self.tokenize(text)
        words = []
        
        for token in tokens:
            if token.pos in include_pos:
                if not self.use_stop_words or token.base_form not in self.STOP_WORDS:
                    words.append(token.base_form)
                    
        return words
