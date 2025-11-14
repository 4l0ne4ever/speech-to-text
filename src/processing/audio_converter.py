"""
Audio conversion utilities for optimal Speech-to-Text performance.

This module provides utilities to convert audio files to the optimal format
for Google Cloud Speech-to-Text V2 API:
- Mono channel
- 16 kHz sample rate
- 16-bit signed PCM (LINEAR16)
"""

import logging
from pathlib import Path
from typing import Optional, Union

import soundfile as sf
import librosa
import numpy as np

logger = logging.getLogger(__name__)


class AudioConversionError(Exception):
    """Error during audio conversion."""
    pass


def convert_to_linear16(
    input_path: Union[str, Path],
    output_path: Optional[Union[str, Path]] = None,
    normalize: bool = True,
) -> Path:
    """
    Convert audio file to LINEAR16 format for optimal Speech-to-Text accuracy.
    
    Google Cloud recommends sending raw PCM audio instead of compressed formats
    like MP3. This conversion typically improves accuracy by 15-25%.
    
    Output format:
    - Mono (1 channel)
    - 16 kHz sample rate
    - 16-bit signed PCM (LINEAR16)
    
    Args:
        input_path: Path to input audio file (MP3, WAV, M4A, etc.)
        output_path: Path for output WAV file. If None, uses input path with .wav extension
        normalize: If True, normalize audio volume to ±1dB for consistent loudness
        
    Returns:
        Path to converted WAV file
        
    Raises:
        AudioConversionError: If conversion fails
        
    Example:
        >>> convert_to_linear16("audio/CD02.mp3", "audio/CD02_converted.wav")
        Path('audio/CD02_converted.wav')
    """
    input_path = Path(input_path)
    
    if not input_path.exists():
        raise AudioConversionError(f"Input file not found: {input_path}")
    
    # Determine output path
    if output_path is None:
        output_path = input_path.with_suffix(".wav")
    else:
        output_path = Path(output_path)
    
    logger.info(f"Converting {input_path.name} to LINEAR16 format...")
    
    try:
        # Load audio with librosa (automatically resamples and converts to mono)
        # sr=16000 resamples to 16kHz, mono=True converts to mono
        audio, sr = librosa.load(str(input_path), sr=16000, mono=True)
        
        # Log properties
        duration = len(audio) / sr
        logger.info(
            f"Loaded: {len(audio)} samples, "
            f"{sr}Hz, "
            f"{duration:.1f}s"
        )
        
        # Normalize volume if requested
        if normalize:
            # Normalize to -1dBFS (0.891 amplitude) to avoid clipping
            # This ensures consistent volume across different audio files
            max_amplitude = np.abs(audio).max()
            if max_amplitude > 0:
                target_amplitude = 0.891  # -1dBFS
                if max_amplitude < target_amplitude * 0.9 or max_amplitude > target_amplitude:
                    gain = target_amplitude / max_amplitude
                    audio = audio * gain
                    gain_db = 20 * np.log10(gain)
                    logger.info(f"Normalized volume: {gain_db:+.1f}dB")
        
        # Ensure audio is in float32 format for soundfile
        audio = audio.astype(np.float32)
        
        # Export as WAV with LINEAR16 (16-bit PCM)
        # subtype='PCM_16' specifies 16-bit signed PCM
        sf.write(
            str(output_path),
            audio,
            sr,
            subtype='PCM_16'
        )
        
        logger.info(
            f"✅ Conversion complete: {output_path.name} "
            f"(mono, 16kHz, LINEAR16, {duration:.1f}s)"
        )
        
        return output_path
        
    except Exception as e:
        logger.error(f"Audio conversion failed: {e}", exc_info=True)
        raise AudioConversionError(f"Failed to convert audio: {e}")


def get_audio_info(audio_path: Union[str, Path]) -> dict:
    """
    Get audio file properties.
    
    Args:
        audio_path: Path to audio file
        
    Returns:
        Dictionary with audio properties:
        - duration_seconds: Audio duration
        - channels: Number of audio channels
        - sample_rate: Sample rate in Hz
        - bit_depth: Bit depth
        - format: File format
        
    Raises:
        AudioConversionError: If file cannot be read
    """
    audio_path = Path(audio_path)
    
    if not audio_path.exists():
        raise AudioConversionError(f"Audio file not found: {audio_path}")
    
    try:
        # Get file info
        info = sf.info(str(audio_path))
        
        return {
            "duration_seconds": info.duration,
            "channels": info.channels,
            "sample_rate": info.samplerate,
            "bit_depth": info.subtype_info.split('_')[-1] if '_' in info.subtype_info else info.subtype_info,
            "format": audio_path.suffix.lstrip(".").upper(),
        }
        
    except Exception as e:
        raise AudioConversionError(f"Failed to read audio file: {e}")
