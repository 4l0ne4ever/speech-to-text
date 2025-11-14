"""
Google Cloud Speech-to-Text V2 service for transcribing Japanese audio files.

This module provides a high-level interface for transcribing audio files using
Google Cloud's Speech-to-Text V2 API optimized for Japanese.
"""

import logging
import time
from typing import Optional, List, Tuple
from datetime import datetime

from google.cloud.speech_v2 import SpeechClient
from google.cloud.speech_v2.types import cloud_speech
from google.api_core import exceptions as google_exceptions
from google.api_core import retry

from ..models import (
    TranscriptionResult,
    TranscriptionOptions,
    WordInfo,
    ProcessingStatus,
)

logger = logging.getLogger(__name__)


class SpeechToTextError(Exception):
    """Base exception for Speech-to-Text errors."""
    pass


class AudioFormatError(SpeechToTextError):
    """Audio format is not supported or invalid."""
    pass


class AudioTooLongError(SpeechToTextError):
    """Audio file exceeds maximum duration."""
    pass


class TranscriptionError(SpeechToTextError):
    """Generic transcription error."""
    pass


class SpeechToTextService:
    """
    Service for transcribing audio files using Google Cloud Speech-to-Text API.
    
    This service handles:
    - Configuration building for optimal Japanese transcription
    - Long-running recognition operations
    - Operation polling and result retrieval
    - Error handling and retry logic
    - Result parsing and structuring
    """
    
    # Constants
    MAX_AUDIO_DURATION_MINUTES = 480  # 8 hours
    POLLING_INTERVAL_SECONDS = 5
    MAX_POLLING_TIME_SECONDS = 3600  # 1 hour max wait
    
    # Cost per 15 seconds (in USD)
    COST_PER_15_SECONDS = {
        "chirp": 0.024,
        "latest_long": 0.009,
        "latest_short": 0.009,
    }
    
    def __init__(self, credentials_path: Optional[str] = None, project_id: Optional[str] = None):
        """
        Initialize Speech-to-Text V2 service.
        
        Args:
            credentials_path: Path to service account JSON key file.
                             If None, uses default credentials from environment.
            project_id: Google Cloud project ID (required for V2 API)
        """
        if credentials_path:
            self.client = SpeechClient.from_service_account_file(credentials_path)
        else:
            self.client = SpeechClient()
        
        self.project_id = project_id
        logger.info("SpeechToTextService V2 initialized")
    
    def build_recognition_config(
        self,
        options: TranscriptionOptions
    ) -> cloud_speech.RecognitionConfig:
        """
        Build recognition configuration for Google Cloud Speech V2 API.
        
        Args:
            options: Transcription options
            
        Returns:
            RecognitionConfig object for V2 API
        """
        # V2 API uses explicit decoding config for audio format
        explicit_decoding_config = None
        if options.audio_encoding:
            encoding_map = {
                "LINEAR16": cloud_speech.ExplicitDecodingConfig.AudioEncoding.LINEAR16,
                "FLAC": cloud_speech.ExplicitDecodingConfig.AudioEncoding.FLAC,
                "MP3": cloud_speech.ExplicitDecodingConfig.AudioEncoding.MP3,
                "OGG_OPUS": cloud_speech.ExplicitDecodingConfig.AudioEncoding.OGG_OPUS,
            }
            encoding = encoding_map.get(
                options.audio_encoding.upper(),
                cloud_speech.ExplicitDecodingConfig.AudioEncoding.MP3
            )
            
            explicit_decoding_config = cloud_speech.ExplicitDecodingConfig(
                encoding=encoding,
                sample_rate_hertz=options.sample_rate_hertz or 16000,
                audio_channel_count=1,  # Mono
            )
        
        # V2 API uses RecognitionFeatures for all feature flags
        features = cloud_speech.RecognitionFeatures(
            enable_automatic_punctuation=options.enable_automatic_punctuation,
            enable_word_time_offsets=options.enable_word_timestamps,
            max_alternatives=options.max_alternatives,
            profanity_filter=options.profanity_filter,
        )
        
        # Speaker diarization config (if enabled)
        if options.enable_speaker_diarization:
            features.diarization_config = cloud_speech.SpeakerDiarizationConfig(
                min_speaker_count=1,
                max_speaker_count=6,
            )
        
        # Build main config
        config = cloud_speech.RecognitionConfig(
            features=features,
            model=options.model or "latest_long",
            language_codes=[options.language_code],  # V2 uses list of language codes
        )
        
        # Add explicit decoding config if specified
        if explicit_decoding_config:
            config.explicit_decoding_config = explicit_decoding_config
        
        logger.info(
            f"Built V2 recognition config: model={options.model}, "
            f"language={options.language_code}, "
            f"encoding={options.audio_encoding}, "
            f"sample_rate={options.sample_rate_hertz}"
        )
        
        return config
    
    async def transcribe_audio(
        self,
        gcs_uri: str,
        presentation_id: str,
        options: Optional[TranscriptionOptions] = None
    ) -> TranscriptionResult:
        """
        Transcribe audio file from Google Cloud Storage using V2 API.
        
        This method performs batch recognition and polls for completion.
        
        Args:
            gcs_uri: GCS URI of audio file (gs://bucket/path/to/file)
            presentation_id: Unique identifier for the presentation
            options: Transcription options. Uses defaults if None.
            
        Returns:
            TranscriptionResult with transcript, segments, and metadata
            
        Raises:
            AudioFormatError: If audio format is not supported
            AudioTooLongError: If audio exceeds maximum duration
            TranscriptionError: If transcription fails
        """
        start_time = time.time()
        
        # Use default options if not provided
        if options is None:
            options = TranscriptionOptions()
        
        logger.info(
            f"Starting V2 transcription for presentation {presentation_id}: {gcs_uri}"
        )
        
        try:
            # Build configuration
            config = self.build_recognition_config(options)
            
            # Build recognizer name (V2 API requirement)
            if not self.project_id:
                raise TranscriptionError("project_id is required for V2 API")
            
            recognizer = f"projects/{self.project_id}/locations/global/recognizers/_"
            
            # Build request
            request = cloud_speech.BatchRecognizeRequest(
                recognizer=recognizer,
                config=config,
                files=[cloud_speech.BatchRecognizeFileMetadata(uri=gcs_uri)],
                recognition_output_config=cloud_speech.RecognitionOutputConfig(
                    inline_response_config=cloud_speech.InlineOutputConfig()
                ),
            )
            
            # Submit batch recognition request
            try:
                operation = self.client.batch_recognize(request=request)
            except google_exceptions.InvalidArgument as e:
                # If model fails, retry with default
                if "model" in str(e).lower() and options.model:
                    logger.warning(f"Model '{options.model}' failed: {e}. Retrying with default model...")
                    options.model = "latest_long"
                    config = self.build_recognition_config(options)
                    request.config = config
                    operation = self.client.batch_recognize(request=request)
                else:
                    raise
            
            operation_id = operation.operation.name
            logger.info(f"Submitted V2 operation {operation_id}")
            
            # Poll for completion
            result = self._poll_operation(operation, operation_id)
            
            # Parse results
            transcription_result = self._parse_results(
                result,
                presentation_id=presentation_id,
                gcs_uri=gcs_uri,
                operation_id=operation_id,
                options=options
            )
            
            # Calculate processing time
            processing_time = time.time() - start_time
            transcription_result.processing_time_seconds = processing_time
            
            # Estimate cost
            cost = self._estimate_cost(
                transcription_result.duration_seconds,
                options.model
            )
            
            logger.info(
                f"V2 Transcription completed for {presentation_id}: "
                f"{transcription_result.word_count} words, "
                f"confidence={transcription_result.confidence:.2f}, "
                f"duration={transcription_result.duration_seconds:.1f}s, "
                f"processing_time={processing_time:.1f}s, "
                f"estimated_cost=${cost:.2f}"
            )
            
            return transcription_result
            
        except google_exceptions.InvalidArgument as e:
            logger.error(f"Invalid audio format: {e}")
            raise AudioFormatError(f"Invalid audio format: {e}")
        
        except google_exceptions.DeadlineExceeded as e:
            logger.error(f"Operation timeout: {e}")
            raise TranscriptionError(f"Operation timeout: {e}")
        
        except google_exceptions.ResourceExhausted as e:
            logger.error(f"Rate limit exceeded: {e}")
            raise TranscriptionError(f"Rate limit exceeded, please retry: {e}")
        
        except Exception as e:
            logger.error(f"Transcription failed: {e}", exc_info=True)
            raise TranscriptionError(f"Transcription failed: {e}")
    
    def _poll_operation(
        self,
        operation,
        operation_id: str
    ) -> cloud_speech.BatchRecognizeResponse:
        """
        Poll operation until completion.
        
        Args:
            operation: BatchRecognizeOperation object
            operation_id: Operation ID for logging
            
        Returns:
            BatchRecognizeResponse
            
        Raises:
            TranscriptionError: If polling times out or operation fails
        """
        start_time = time.time()
        poll_count = 0
        
        logger.info(f"Polling operation {operation_id}")
        
        while not operation.done():
            poll_count += 1
            elapsed = time.time() - start_time
            
            # Check timeout
            if elapsed > self.MAX_POLLING_TIME_SECONDS:
                raise TranscriptionError(
                    f"Operation polling timeout after {elapsed:.0f} seconds"
                )
            
            # Log progress
            if poll_count % 10 == 0:  # Every 50 seconds
                logger.info(
                    f"Still polling operation {operation_id}: "
                    f"{elapsed:.0f}s elapsed, {poll_count} polls"
                )
            
            # Wait before next poll
            time.sleep(self.POLLING_INTERVAL_SECONDS)
        
        # Operation completed
        elapsed = time.time() - start_time
        logger.info(
            f"Operation {operation_id} completed after {elapsed:.1f}s "
            f"({poll_count} polls)"
        )
        
        # Get result
        try:
            result = operation.result()
            return result
        except Exception as e:
            logger.error(f"Failed to get operation result: {e}")
            raise TranscriptionError(f"Failed to get operation result: {e}")
    
    def _parse_results(
        self,
        response: cloud_speech.BatchRecognizeResponse,
        presentation_id: str,
        gcs_uri: str,
        operation_id: str,
        options: TranscriptionOptions
    ) -> TranscriptionResult:
        """
        Parse Google Cloud V2 API response into TranscriptionResult.
        
        Args:
            response: V2 API response
            presentation_id: Presentation ID
            gcs_uri: GCS URI of audio file
            operation_id: Operation ID
            options: Transcription options used
            
        Returns:
            TranscriptionResult
        """
        # V2 response structure: response.results is a dict with GCS URI as key
        if not response.results:
            logger.warning("No transcription results returned")
            return TranscriptionResult(
                presentation_id=presentation_id,
                transcript="",
                language=options.language_code,
                confidence=0.0,
                duration_seconds=0.0,
                word_count=0,
                gcs_uri=gcs_uri,
                operation_id=operation_id,
                model=options.model,
                quality_flags=["empty_results"],
            )
        
        # Get file-specific results - results is a dict keyed by GCS URI
        file_result = response.results.get(gcs_uri)
        
        if not file_result:
            logger.warning(f"No results found for URI: {gcs_uri}")
            logger.warning(f"Available URIs: {list(response.results.keys())}")
            return TranscriptionResult(
                presentation_id=presentation_id,
                transcript="",
                language=options.language_code,
                confidence=0.0,
                duration_seconds=0.0,
                word_count=0,
                gcs_uri=gcs_uri,
                operation_id=operation_id,
                model=options.model,
                quality_flags=["empty_results"],
            )
        
        # Check for transcript in results
        if not hasattr(file_result, 'transcript') or not file_result.transcript:
            logger.warning("No transcript in file result")
            return TranscriptionResult(
                presentation_id=presentation_id,
                transcript="",
                language=options.language_code,
                confidence=0.0,
                duration_seconds=0.0,
                word_count=0,
                gcs_uri=gcs_uri,
                operation_id=operation_id,
                model=options.model,
                quality_flags=["empty_results"],
            )
        
        # Check for results in transcript
        if not hasattr(file_result.transcript, 'results') or not file_result.transcript.results:
            logger.warning("No results in transcript")
            return TranscriptionResult(
                presentation_id=presentation_id,
                transcript="",
                language=options.language_code,
                confidence=0.0,
                duration_seconds=0.0,
                word_count=0,
                gcs_uri=gcs_uri,
                operation_id=operation_id,
                model=options.model,
                quality_flags=["empty_results"],
            )
        
        # Extract transcript and words from all results
        full_transcript_parts = []
        all_words = []
        confidences = []
        
        for result in file_result.transcript.results:
            # Get the best alternative (highest confidence)
            if not result.alternatives:
                continue
                
            alternative = result.alternatives[0]
            
            # Add transcript part
            transcript = alternative.transcript
            full_transcript_parts.append(transcript)
            confidences.append(alternative.confidence)
            
            # Extract word-level information
            if hasattr(alternative, 'words') and alternative.words:
                for word_info in alternative.words:
                    word = WordInfo(
                        word=word_info.word,
                        start_time=self._to_seconds(word_info.start_offset),
                        end_time=self._to_seconds(word_info.end_offset),
                        confidence=word_info.confidence if hasattr(word_info, 'confidence') else alternative.confidence,
                    )
                    all_words.append(word)
        
        # Combine transcript parts
        full_transcript = " ".join(full_transcript_parts)
        
        # Calculate overall confidence
        overall_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        
        # Calculate duration from word timings
        duration_seconds = 0.0
        if all_words:
            duration_seconds = all_words[-1].end_time
        
        # Count words
        word_count = len(all_words)
        
        # Quality flags
        quality_flags = []
        has_low_confidence = False
        
        if overall_confidence < 0.5:
            quality_flags.append("low_confidence")
            has_low_confidence = True
        
        if word_count == 0:
            quality_flags.append("no_words")
        
        # Create result
        result = TranscriptionResult(
            presentation_id=presentation_id,
            transcript=full_transcript,
            language=options.language_code,
            confidence=overall_confidence,
            duration_seconds=duration_seconds,
            word_count=word_count,
            words=all_words,
            model=options.model,
            gcs_uri=gcs_uri,
            operation_id=operation_id,
            has_low_confidence=has_low_confidence,
            quality_flags=quality_flags,
        )
        
        return result
    
    def _to_seconds(self, duration) -> float:
        """
        Convert Google's Duration or timedelta to seconds.
        
        Args:
            duration: google.protobuf.duration_pb2.Duration or datetime.timedelta
            
        Returns:
            Seconds as float
        """
        # Handle datetime.timedelta
        if hasattr(duration, 'total_seconds'):
            return duration.total_seconds()
        # Handle protobuf Duration
        elif hasattr(duration, 'nanos'):
            return duration.seconds + duration.nanos / 1e9
        # Fallback
        else:
            return float(duration)
    
    def _estimate_cost(self, duration_seconds: float, model: str) -> float:
        """
        Estimate transcription cost.
        
        Args:
            duration_seconds: Audio duration in seconds
            model: Model name
            
        Returns:
            Estimated cost in USD
        """
        # Calculate number of 15-second increments
        increments = (duration_seconds / 15.0)
        
        # Get cost per increment
        cost_per_increment = self.COST_PER_15_SECONDS.get(model, 0.024)
        
        # Calculate total cost
        total_cost = increments * cost_per_increment
        
        return total_cost
    
    def transcribe_audio_sync(
        self,
        gcs_uri: str,
        presentation_id: str,
        options: Optional[TranscriptionOptions] = None
    ) -> TranscriptionResult:
        """
        Synchronous wrapper for transcribe_audio.
        
        This is a convenience method for non-async contexts.
        """
        import asyncio
        
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If loop is already running, create a new task
            raise RuntimeError(
                "Cannot run transcribe_audio_sync in an already running event loop. "
                "Use transcribe_audio() instead."
            )
        
        return loop.run_until_complete(
            self.transcribe_audio(gcs_uri, presentation_id, options)
        )
