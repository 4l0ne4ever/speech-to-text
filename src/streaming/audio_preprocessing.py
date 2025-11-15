"""
Audio Preprocessing for Real-Time Streaming.

Implements:
- Voice Activity Detection (VAD) to save costs during silence
- Automatic Gain Control (AGC) for volume normalization
- Noise suppression for better transcription quality
"""

import logging
import numpy as np
from typing import Optional, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class AudioActivity(Enum):
    """Audio activity status."""
    SPEECH = "speech"
    SILENCE = "silence"
    UNKNOWN = "unknown"


@dataclass
class VADConfig:
    """Voice Activity Detection configuration."""
    # Energy threshold for speech detection (dB)
    energy_threshold_db: float = -40.0
    
    # Minimum speech duration to consider it speech (seconds)
    min_speech_duration: float = 0.3
    
    # Minimum silence duration before marking as silence (seconds)
    min_silence_duration: float = 2.0
    
    # Sample rate (Hz)
    sample_rate: int = 16000
    
    # Frame size for analysis (samples)
    frame_size: int = 160  # 10ms at 16kHz


@dataclass
class AGCConfig:
    """Automatic Gain Control configuration."""
    # Target RMS level (dBFS)
    target_db: float = -1.0
    
    # Max gain adjustment (dB)
    max_gain_db: float = 30.0
    
    # Min gain adjustment (dB)
    min_gain_db: float = -10.0
    
    # Smoothing factor (0.0-1.0)
    smoothing_factor: float = 0.1


class VoiceActivityDetector:
    """
    Voice Activity Detection using energy-based approach.
    
    Detects speech vs silence in audio chunks to:
    - Save API costs by not sending silence
    - Improve transcription by filtering out non-speech
    - Provide better UX by detecting when speaker pauses
    """
    
    def __init__(self, config: Optional[VADConfig] = None):
        """
        Initialize VAD.
        
        Args:
            config: VAD configuration
        """
        self.config = config or VADConfig()
        
        # State tracking
        self.current_state = AudioActivity.UNKNOWN
        self.speech_frames = 0
        self.silence_frames = 0
        
        # Statistics
        self.total_frames = 0
        self.total_speech_frames = 0
        self.total_silence_frames = 0
        
        logger.info(
            f"VAD initialized: "
            f"threshold={self.config.energy_threshold_db}dB, "
            f"min_speech={self.config.min_speech_duration}s, "
            f"min_silence={self.config.min_silence_duration}s"
        )
    
    def process_chunk(self, audio_bytes: bytes) -> AudioActivity:
        """
        Process audio chunk and detect voice activity.
        
        Args:
            audio_bytes: LINEAR16 audio bytes
            
        Returns:
            AudioActivity status (SPEECH or SILENCE)
        """
        # Convert bytes to numpy array (int16)
        audio_int16 = np.frombuffer(audio_bytes, dtype=np.int16)
        
        # Calculate energy (RMS in dB)
        energy_db = self._calculate_energy_db(audio_int16)
        
        # Determine if speech or silence
        is_speech = energy_db > self.config.energy_threshold_db
        
        # Update frame counters
        self.total_frames += 1
        
        if is_speech:
            self.speech_frames += 1
            self.silence_frames = 0
            self.total_speech_frames += 1
        else:
            self.silence_frames += 1
            self.speech_frames = 0
            self.total_silence_frames += 1
        
        # Determine state based on duration
        speech_duration = (
            self.speech_frames * len(audio_bytes) / 
            (self.config.sample_rate * 2)  # 2 bytes per sample
        )
        silence_duration = (
            self.silence_frames * len(audio_bytes) / 
            (self.config.sample_rate * 2)
        )
        
        # Update state
        if speech_duration >= self.config.min_speech_duration:
            self.current_state = AudioActivity.SPEECH
        elif silence_duration >= self.config.min_silence_duration:
            self.current_state = AudioActivity.SILENCE
        # else: keep current state
        
        logger.debug(
            f"VAD: energy={energy_db:.1f}dB, "
            f"state={self.current_state.value}, "
            f"speech_frames={self.speech_frames}, "
            f"silence_frames={self.silence_frames}"
        )
        
        return self.current_state
    
    def _calculate_energy_db(self, audio_int16: np.ndarray) -> float:
        """
        Calculate audio energy in dB.
        
        Args:
            audio_int16: Audio samples as int16
            
        Returns:
            Energy in dBFS (decibels relative to full scale)
        """
        if len(audio_int16) == 0:
            return -100.0  # Very low energy
        
        # Convert to float32 [-1.0, 1.0]
        audio_float = audio_int16.astype(np.float32) / 32768.0
        
        # Calculate RMS (Root Mean Square)
        rms = np.sqrt(np.mean(audio_float ** 2))
        
        # Convert to dB (with floor to avoid log(0))
        if rms < 1e-10:
            return -100.0
        
        db = 20 * np.log10(rms)
        return db
    
    def reset(self):
        """Reset VAD state."""
        self.current_state = AudioActivity.UNKNOWN
        self.speech_frames = 0
        self.silence_frames = 0
    
    def get_stats(self) -> dict:
        """Get VAD statistics."""
        if self.total_frames == 0:
            return {
                "total_frames": 0,
                "speech_ratio": 0.0,
                "silence_ratio": 0.0,
            }
        
        return {
            "total_frames": self.total_frames,
            "total_speech_frames": self.total_speech_frames,
            "total_silence_frames": self.total_silence_frames,
            "speech_ratio": self.total_speech_frames / self.total_frames,
            "silence_ratio": self.total_silence_frames / self.total_frames,
            "current_state": self.current_state.value,
        }


class AutomaticGainControl:
    """
    Automatic Gain Control for audio normalization.
    
    Normalizes audio volume to a target level for:
    - Consistent transcription quality
    - Better handling of quiet speakers
    - Preventing distortion from loud speakers
    """
    
    def __init__(self, config: Optional[AGCConfig] = None):
        """
        Initialize AGC.
        
        Args:
            config: AGC configuration
        """
        self.config = config or AGCConfig()
        
        # Current gain level
        self.current_gain_db = 0.0
        
        # Statistics
        self.total_chunks = 0
        self.gain_adjustments = []
        
        logger.info(
            f"AGC initialized: "
            f"target={self.config.target_db}dB, "
            f"range=[{self.config.min_gain_db}, {self.config.max_gain_db}]dB"
        )
    
    def process_chunk(self, audio_bytes: bytes) -> bytes:
        """
        Process audio chunk with automatic gain control.
        
        Args:
            audio_bytes: LINEAR16 audio bytes
            
        Returns:
            Normalized audio bytes
        """
        # Convert bytes to numpy array
        audio_int16 = np.frombuffer(audio_bytes, dtype=np.int16)
        audio_float = audio_int16.astype(np.float32) / 32768.0
        
        # Calculate current RMS
        current_rms = np.sqrt(np.mean(audio_float ** 2))
        
        if current_rms < 1e-10:
            # Silent chunk, no adjustment needed
            return audio_bytes
        
        # Calculate current level in dB
        current_db = 20 * np.log10(current_rms)
        
        # Calculate required gain
        required_gain_db = self.config.target_db - current_db
        
        # Clamp gain to limits
        required_gain_db = max(
            self.config.min_gain_db,
            min(self.config.max_gain_db, required_gain_db)
        )
        
        # Smooth gain changes
        self.current_gain_db = (
            self.config.smoothing_factor * required_gain_db +
            (1 - self.config.smoothing_factor) * self.current_gain_db
        )
        
        # Apply gain
        gain_linear = 10 ** (self.current_gain_db / 20.0)
        audio_gained = audio_float * gain_linear
        
        # Clamp to [-1.0, 1.0] to prevent clipping
        audio_gained = np.clip(audio_gained, -1.0, 1.0)
        
        # Convert back to int16
        audio_int16_gained = (audio_gained * 32767).astype(np.int16)
        
        # Track statistics
        self.total_chunks += 1
        self.gain_adjustments.append(self.current_gain_db)
        
        logger.debug(
            f"AGC: current={current_db:.1f}dB, "
            f"gain={self.current_gain_db:.1f}dB, "
            f"target={self.config.target_db}dB"
        )
        
        return audio_int16_gained.tobytes()
    
    def reset(self):
        """Reset AGC state."""
        self.current_gain_db = 0.0
    
    def get_stats(self) -> dict:
        """Get AGC statistics."""
        if not self.gain_adjustments:
            return {
                "total_chunks": 0,
                "avg_gain_db": 0.0,
                "min_gain_db": 0.0,
                "max_gain_db": 0.0,
            }
        
        return {
            "total_chunks": self.total_chunks,
            "avg_gain_db": np.mean(self.gain_adjustments),
            "min_gain_db": np.min(self.gain_adjustments),
            "max_gain_db": np.max(self.gain_adjustments),
            "current_gain_db": self.current_gain_db,
        }


class AudioPreprocessor:
    """
    Combined audio preprocessing pipeline.
    
    Applies VAD, AGC, and other preprocessing steps in sequence.
    """
    
    def __init__(
        self,
        enable_vad: bool = True,
        enable_agc: bool = True,
        vad_config: Optional[VADConfig] = None,
        agc_config: Optional[AGCConfig] = None,
    ):
        """
        Initialize audio preprocessor.
        
        Args:
            enable_vad: Enable voice activity detection
            enable_agc: Enable automatic gain control
            vad_config: VAD configuration
            agc_config: AGC configuration
        """
        self.enable_vad = enable_vad
        self.enable_agc = enable_agc
        
        self.vad = VoiceActivityDetector(vad_config) if enable_vad else None
        self.agc = AutomaticGainControl(agc_config) if enable_agc else None
        
        logger.info(
            f"AudioPreprocessor initialized: "
            f"VAD={enable_vad}, AGC={enable_agc}"
        )
    
    def process_chunk(
        self,
        audio_bytes: bytes
    ) -> Tuple[bytes, AudioActivity]:
        """
        Process audio chunk through preprocessing pipeline.
        
        Args:
            audio_bytes: LINEAR16 audio bytes
            
        Returns:
            Tuple of (processed_audio_bytes, activity_status)
        """
        processed_audio = audio_bytes
        activity = AudioActivity.UNKNOWN
        
        # Step 1: AGC (before VAD for better detection)
        if self.enable_agc and self.agc:
            processed_audio = self.agc.process_chunk(processed_audio)
        
        # Step 2: VAD
        if self.enable_vad and self.vad:
            activity = self.vad.process_chunk(processed_audio)
        
        return processed_audio, activity
    
    def should_send_chunk(self, activity: AudioActivity) -> bool:
        """
        Determine if chunk should be sent to API based on activity.
        
        Args:
            activity: Audio activity status
            
        Returns:
            True if chunk should be sent
        """
        if not self.enable_vad:
            return True  # Always send if VAD disabled
        
        # Send speech chunks, skip silence
        return activity == AudioActivity.SPEECH
    
    def reset(self):
        """Reset all preprocessors."""
        if self.vad:
            self.vad.reset()
        if self.agc:
            self.agc.reset()
    
    def get_stats(self) -> dict:
        """Get preprocessing statistics."""
        stats = {
            "vad_enabled": self.enable_vad,
            "agc_enabled": self.enable_agc,
        }
        
        if self.vad:
            stats["vad"] = self.vad.get_stats()
        
        if self.agc:
            stats["agc"] = self.agc.get_stats()
        
        return stats
