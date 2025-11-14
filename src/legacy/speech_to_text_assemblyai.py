import assemblyai as aai
from config import ASSEMBLYAI_API_KEY, DEFAULT_LANGUAGE, DEFAULT_CONFIG


class SpeechToText:    
    def __init__(self):
        """Initialize AssemblyAI with API key"""
        aai.settings.api_key = ASSEMBLYAI_API_KEY
        self.transcriber = aai.Transcriber()
        self.default_language = DEFAULT_LANGUAGE
    
    def transcribe_file(self, audio_file_path: str, language_code: str = None) -> dict:
        try:
            lang = language_code or self.default_language
            print(f"Đang transcribe file: {audio_file_path} (Language: {lang})")
            
            config = aai.TranscriptionConfig(
                language_code=lang,
                punctuate=DEFAULT_CONFIG.get("punctuate", True),
                format_text=DEFAULT_CONFIG.get("format_text", True)
            )
            transcript = self.transcriber.transcribe(audio_file_path, config=config)
            
            if transcript.status == aai.TranscriptStatus.error:
                return {
                    "success": False,
                    "error": transcript.error
                }
            
            return {
                "success": True,
                "text": transcript.text,
                "confidence": transcript.confidence,
                "audio_duration": transcript.audio_duration,
                "language": lang,
                "words": transcript.words
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def transcribe_url(self, audio_url: str, language_code: str = None) -> dict:
        return self.transcribe_file(audio_url, language_code)
    
    def transcribe_with_config(self, audio_file_path: str, **kwargs) -> dict:
        try:
            # Nếu không có language_code và không bật language_detection, dùng default từ config
            if "language_code" not in kwargs and not kwargs.get("language_detection"):
                kwargs["language_code"] = self.default_language
            
            # Apply default config nếu chưa được set
            for key, value in DEFAULT_CONFIG.items():
                if key not in kwargs:
                    kwargs[key] = value
            
            config = aai.TranscriptionConfig(**kwargs)
            transcript = self.transcriber.transcribe(audio_file_path, config=config)
            
            if transcript.status == aai.TranscriptStatus.error:
                return {
                    "success": False,
                    "error": transcript.error
                }
            
            result = {
                "success": True,
                "text": transcript.text,
                "confidence": transcript.confidence,
                "audio_duration": transcript.audio_duration,
            }
            
            # Thêm thông tin về speakers nếu có
            if kwargs.get("speaker_labels") and transcript.utterances:
                result["speakers"] = [
                    {
                        "speaker": u.speaker,
                        "text": u.text,
                        "start": u.start,
                        "end": u.end
                    }
                    for u in transcript.utterances
                ]
            
            return result
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
