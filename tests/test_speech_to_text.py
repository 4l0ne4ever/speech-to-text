"""
Unit tests for Google Cloud Speech-to-Text service.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from src.google_cloud.speech_to_text import (
    SpeechToTextService,
    SpeechToTextError,
    AudioFormatError,
    TranscriptionError,
)
from src.models import (
    TranscriptionOptions,
    TranscriptionResult,
    WordInfo,
)


class TestSpeechToTextService:
    """Test cases for SpeechToTextService."""
    
    @pytest.fixture
    def service(self):
        """Create service instance for testing."""
        with patch('src.google_cloud.speech_to_text.speech_v1.SpeechClient'):
            service = SpeechToTextService()
            return service
    
    @pytest.fixture
    def default_options(self):
        """Default transcription options."""
        return TranscriptionOptions(
            language_code="ja-JP",
            model="chirp",
            enable_automatic_punctuation=True,
            enable_word_timestamps=True,
            enable_speaker_diarization=False,
        )
    
    def test_build_recognition_config_basic(self, service, default_options):
        """Test building basic recognition config."""
        config = service.build_recognition_config(default_options)
        
        assert config.language_code == "ja-JP"
        assert config.model == "chirp"
        assert config.enable_automatic_punctuation is True
        assert config.enable_word_time_offsets is True
    
    def test_build_recognition_config_with_diarization(self, service):
        """Test building config with speaker diarization."""
        options = TranscriptionOptions(
            language_code="ja-JP",
            model="chirp",
            enable_speaker_diarization=True,
        )
        
        config = service.build_recognition_config(options)
        
        assert hasattr(config, 'diarization_config')
        assert config.diarization_config.enable_speaker_diarization is True
    
    def test_build_recognition_config_with_audio_encoding(self, service):
        """Test building config with specific audio encoding."""
        options = TranscriptionOptions(
            language_code="ja-JP",
            model="chirp",
            audio_encoding="MP3",
            sample_rate_hertz=48000,
        )
        
        config = service.build_recognition_config(options)
        
        assert config.sample_rate_hertz == 48000
    
    def test_estimate_cost_chirp(self, service):
        """Test cost estimation for chirp model."""
        # 60 seconds = 4 increments of 15 seconds
        cost = service._estimate_cost(60.0, "chirp")
        expected = 4.0 * 0.024  # $0.096
        
        assert cost == pytest.approx(expected)
    
    def test_estimate_cost_latest_long(self, service):
        """Test cost estimation for latest_long model."""
        # 120 seconds = 8 increments of 15 seconds
        cost = service._estimate_cost(120.0, "latest_long")
        expected = 8.0 * 0.009  # $0.072
        
        assert cost == pytest.approx(expected)
    
    def test_to_seconds(self, service):
        """Test converting Duration to seconds."""
        # Mock Duration object
        duration = Mock()
        duration.seconds = 5
        duration.nanos = 500000000  # 0.5 seconds in nanoseconds
        
        seconds = service._to_seconds(duration)
        
        assert seconds == 5.5
    
    @pytest.mark.asyncio
    async def test_transcribe_audio_empty_results(self, service, default_options):
        """Test handling of empty transcription results."""
        # Mock operation with empty results
        mock_operation = Mock()
        mock_operation.operation.name = "test_operation_123"
        mock_operation.done.return_value = True
        
        mock_response = Mock()
        mock_response.results = []
        mock_operation.result.return_value = mock_response
        
        service.client.long_running_recognize = Mock(return_value=mock_operation)
        
        # Transcribe
        result = await service.transcribe_audio(
            gcs_uri="gs://test-bucket/test.mp3",
            presentation_id="test_pres_001",
            options=default_options
        )
        
        # Verify empty result
        assert result.transcript == ""
        assert result.word_count == 0
        assert result.confidence == 0.0
        assert "empty_results" in result.quality_flags
    
    @pytest.mark.asyncio
    async def test_transcribe_audio_with_words(self, service, default_options):
        """Test transcription with word-level timestamps."""
        # Mock word info
        mock_word_1 = Mock()
        mock_word_1.word = "こんにちは"
        mock_word_1.start_time = Mock(seconds=0, nanos=0)
        mock_word_1.end_time = Mock(seconds=1, nanos=200000000)
        mock_word_1.confidence = 0.95
        
        mock_word_2 = Mock()
        mock_word_2.word = "今日"
        mock_word_2.start_time = Mock(seconds=1, nanos=500000000)
        mock_word_2.end_time = Mock(seconds=2, nanos=0)
        mock_word_2.confidence = 0.92
        
        # Mock alternative with words
        mock_alternative = Mock()
        mock_alternative.transcript = "こんにちは 今日"
        mock_alternative.confidence = 0.94
        mock_alternative.words = [mock_word_1, mock_word_2]
        
        # Mock result
        mock_result = Mock()
        mock_result.alternatives = [mock_alternative]
        
        # Mock response
        mock_response = Mock()
        mock_response.results = [mock_result]
        
        # Mock operation
        mock_operation = Mock()
        mock_operation.operation.name = "test_operation_123"
        mock_operation.done.return_value = True
        mock_operation.result.return_value = mock_response
        
        service.client.long_running_recognize = Mock(return_value=mock_operation)
        
        # Transcribe
        result = await service.transcribe_audio(
            gcs_uri="gs://test-bucket/test.mp3",
            presentation_id="test_pres_001",
            options=default_options
        )
        
        # Verify result
        assert result.transcript == "こんにちは 今日"
        assert result.word_count == 2
        assert result.confidence == pytest.approx(0.94)
        assert result.duration_seconds == pytest.approx(2.0)
        
        # Verify words
        assert len(result.words) == 2
        assert result.words[0].word == "こんにちは"
        assert result.words[0].start_time == 0.0
        assert result.words[0].end_time == pytest.approx(1.2)
        assert result.words[1].word == "今日"
    
    @pytest.mark.asyncio
    async def test_transcribe_audio_low_confidence(self, service, default_options):
        """Test handling of low confidence results."""
        # Mock alternative with low confidence
        mock_alternative = Mock()
        mock_alternative.transcript = "不明瞭な音声"
        mock_alternative.confidence = 0.3
        mock_alternative.words = []
        
        # Mock result
        mock_result = Mock()
        mock_result.alternatives = [mock_alternative]
        
        # Mock response
        mock_response = Mock()
        mock_response.results = [mock_result]
        
        # Mock operation
        mock_operation = Mock()
        mock_operation.operation.name = "test_operation_123"
        mock_operation.done.return_value = True
        mock_operation.result.return_value = mock_response
        
        service.client.long_running_recognize = Mock(return_value=mock_operation)
        
        # Transcribe
        result = await service.transcribe_audio(
            gcs_uri="gs://test-bucket/test.mp3",
            presentation_id="test_pres_001",
            options=default_options
        )
        
        # Verify low confidence flags
        assert result.has_low_confidence is True
        assert "low_confidence" in result.quality_flags
        assert result.confidence < 0.5


class TestTranscriptionOptions:
    """Test TranscriptionOptions model."""
    
    def test_default_options(self):
        """Test default option values."""
        options = TranscriptionOptions()
        
        assert options.language_code == "ja-JP"
        assert options.model == "chirp"
        assert options.enable_automatic_punctuation is True
        assert options.enable_word_timestamps is True
        assert options.enable_speaker_diarization is False
    
    def test_to_dict(self):
        """Test converting options to dictionary."""
        options = TranscriptionOptions(
            language_code="en-US",
            model="latest_long",
        )
        
        result = options.to_dict()
        
        assert result["language_code"] == "en-US"
        assert result["model"] == "latest_long"
        assert "enable_automatic_punctuation" in result


class TestWordInfo:
    """Test WordInfo model."""
    
    def test_duration_calculation(self):
        """Test word duration calculation."""
        word = WordInfo(
            word="こんにちは",
            start_time=1.0,
            end_time=2.5,
            confidence=0.95
        )
        
        assert word.duration() == 1.5


class TestTranscriptionResult:
    """Test TranscriptionResult model."""
    
    def test_to_dict_basic(self):
        """Test converting result to dictionary."""
        result = TranscriptionResult(
            presentation_id="test_pres_001",
            transcript="こんにちは",
            language="ja-JP",
            confidence=0.95,
            duration_seconds=2.5,
            word_count=1,
            model="chirp",
        )
        
        result_dict = result.to_dict()
        
        assert result_dict["presentation_id"] == "test_pres_001"
        assert result_dict["transcript"] == "こんにちは"
        assert result_dict["confidence"] == 0.95
        assert result_dict["model"] == "chirp"
