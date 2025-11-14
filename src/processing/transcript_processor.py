"""
Transcript processor for segmenting and formatting transcription results.

This module handles:
- Sentence-based segmentation using Japanese punctuation
- Timestamp alignment from word-level data
- Confidence score calculation per segment
"""

import logging
import re
from typing import List, Tuple, Optional

from ..models import (
    TranscriptionResult,
    TranscriptionSegment,
    WordInfo,
)

logger = logging.getLogger(__name__)


class TranscriptProcessor:
    """
    Processor for segmenting and formatting transcripts.
    
    This service handles:
    - Japanese sentence segmentation using punctuation marks
    - Timestamp alignment from word-level data
    - Confidence score averaging per segment
    - Segment ID generation
    """
    
    # Japanese punctuation marks for sentence boundaries
    JAPANESE_SENTENCE_ENDINGS = [
        '。',  # Period (U+3002)
        '？',  # Question mark (U+FF1F)
        '！',  # Exclamation mark (U+FF01)
    ]
    
    # Regex pattern for sentence boundaries
    SENTENCE_BOUNDARY_PATTERN = re.compile(r'[。？！]')
    
    def __init__(self):
        """Initialize transcript processor."""
        logger.info("TranscriptProcessor initialized")
    
    def segment_by_sentences(
        self,
        result: TranscriptionResult
    ) -> TranscriptionResult:
        """
        Segment transcript into sentences based on Japanese punctuation.
        
        Args:
            result: TranscriptionResult with full transcript and words
            
        Returns:
            Updated TranscriptionResult with populated segments
        """
        if not result.transcript or not result.words:
            logger.warning(
                f"Cannot segment: empty transcript or no words for {result.presentation_id}"
            )
            return result
        
        logger.info(
            f"Segmenting transcript for {result.presentation_id}: "
            f"{result.word_count} words, {len(result.transcript)} chars"
        )
        
        # Split transcript into sentences
        sentences = self._split_into_sentences(result.transcript)
        
        if not sentences:
            logger.warning(f"No sentences found in transcript for {result.presentation_id}")
            return result
        
        # Create segments with timing information
        segments = []
        word_index = 0
        
        for i, sentence_text in enumerate(sentences):
            segment = self._create_segment_from_sentence(
                sentence_text=sentence_text,
                segment_number=i + 1,
                words=result.words,
                word_start_index=word_index,
                presentation_id=result.presentation_id
            )
            
            if segment:
                segments.append(segment)
                word_index += segment.word_count
        
        result.segments = segments
        
        logger.info(
            f"Created {len(segments)} segments for {result.presentation_id}"
        )
        
        return result
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """
        Split text into sentences using Japanese punctuation.
        
        Args:
            text: Full transcript text
            
        Returns:
            List of sentence strings
        """
        # Split by sentence boundaries, keeping the punctuation
        parts = self.SENTENCE_BOUNDARY_PATTERN.split(text)
        
        sentences = []
        current_sentence = ""
        
        # Reconstruct sentences with punctuation
        for i, part in enumerate(parts):
            part = part.strip()
            if not part:
                continue
            
            # Add the part
            current_sentence += part
            
            # Check if this part ends with punctuation in original text
            # (punctuation is removed by split, so we need to add it back)
            if i < len(parts) - 1:  # Not the last part
                # Find the punctuation that was used to split
                original_pos = text.find(part)
                if original_pos >= 0:
                    next_char_pos = original_pos + len(part)
                    if next_char_pos < len(text):
                        next_char = text[next_char_pos]
                        if next_char in self.JAPANESE_SENTENCE_ENDINGS:
                            current_sentence += next_char
                            sentences.append(current_sentence.strip())
                            current_sentence = ""
        
        # Add any remaining text as a sentence
        if current_sentence.strip():
            sentences.append(current_sentence.strip())
        
        # Alternative simpler approach: split and keep delimiters
        if not sentences:
            sentences = [s.strip() for s in re.split(r'([。？！])', text) if s.strip()]
            # Recombine text with punctuation
            final_sentences = []
            temp = ""
            for s in sentences:
                temp += s
                if s in self.JAPANESE_SENTENCE_ENDINGS:
                    final_sentences.append(temp)
                    temp = ""
            if temp:
                final_sentences.append(temp)
            sentences = final_sentences
        
        return [s for s in sentences if s.strip()]
    
    def _create_segment_from_sentence(
        self,
        sentence_text: str,
        segment_number: int,
        words: List[WordInfo],
        word_start_index: int,
        presentation_id: str
    ) -> Optional[TranscriptionSegment]:
        """
        Create a segment from a sentence with timing information.
        
        Args:
            sentence_text: Sentence text
            segment_number: Sequential segment number
            words: List of all words from transcription
            word_start_index: Starting index in words list
            presentation_id: Presentation ID for logging
            
        Returns:
            TranscriptionSegment or None if cannot be created
        """
        # Find words that belong to this sentence
        # This is tricky because the sentence text may not exactly match word text
        # due to spacing and punctuation
        
        # Simple approach: take the next N words where N is roughly the word count
        sentence_words = []
        sentence_clean = sentence_text.replace('。', '').replace('？', '').replace('！', '').strip()
        
        # Count words in sentence (rough estimate)
        estimated_word_count = len(sentence_clean.split())
        
        # Get words starting from word_start_index
        for i in range(word_start_index, min(word_start_index + estimated_word_count + 5, len(words))):
            if i >= len(words):
                break
            
            word = words[i]
            sentence_words.append(word)
            
            # Check if we've covered the sentence
            # (this is approximate - word text may differ from transcript)
            combined_text = ''.join([w.word for w in sentence_words])
            if len(combined_text) >= len(sentence_clean):
                break
        
        if not sentence_words:
            logger.warning(
                f"No words found for segment {segment_number} in {presentation_id}: '{sentence_text[:50]}...'"
            )
            return None
        
        # Calculate timing from first and last word
        start_time = sentence_words[0].start_time
        end_time = sentence_words[-1].end_time
        
        # Calculate average confidence
        confidences = [w.confidence for w in sentence_words]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        
        # Create segment
        segment = TranscriptionSegment(
            segment_id=f"seg_{segment_number:03d}",
            text=sentence_text,
            start_time=start_time,
            end_time=end_time,
            confidence=avg_confidence,
            word_count=len(sentence_words),
            words=sentence_words,
        )
        
        return segment
    
    def validate_segments(
        self,
        segments: List[TranscriptionSegment],
        min_confidence: float = 0.5
    ) -> Tuple[List[str], int]:
        """
        Validate segments and identify quality issues.
        
        Args:
            segments: List of transcript segments
            min_confidence: Minimum confidence threshold
            
        Returns:
            Tuple of (quality_flags, low_confidence_count)
        """
        quality_flags = []
        low_confidence_count = 0
        
        for segment in segments:
            if segment.confidence < min_confidence:
                low_confidence_count += 1
        
        if low_confidence_count > 0:
            quality_flags.append(f"low_confidence_segments: {low_confidence_count}")
        
        # Check for very short segments (might indicate issues)
        very_short_segments = [s for s in segments if s.duration() < 0.5]
        if len(very_short_segments) > len(segments) * 0.2:  # > 20% very short
            quality_flags.append("many_short_segments")
        
        # Check for very long segments (might need better segmentation)
        very_long_segments = [s for s in segments if s.duration() > 30.0]
        if very_long_segments:
            quality_flags.append(f"long_segments: {len(very_long_segments)}")
        
        return quality_flags, low_confidence_count
