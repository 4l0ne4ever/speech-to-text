#!/usr/bin/env python3
"""
Generate test audio files for Phase 2 testing using Google Cloud Text-to-Speech.

This script creates Japanese audio samples of various lengths for testing
the Speech-to-Text pipeline.
"""

import os
from pathlib import Path
from google.cloud import texttospeech


def generate_test_audio(
    output_file: str,
    text: str,
    duration_description: str = "test"
):
    """
    Generate a Japanese audio file using Google Cloud TTS.
    
    Args:
        output_file: Path to save the audio file
        text: Japanese text to convert to speech
        duration_description: Description of audio (for logging)
    """
    print(f"Generating {duration_description} audio: {output_file}")
    
    # Initialize client
    client = texttospeech.TextToSpeechClient()
    
    # Set up the synthesis request
    synthesis_input = texttospeech.SynthesisInput(text=text)
    
    # Configure voice (female Japanese neural voice)
    voice = texttospeech.VoiceSelectionParams(
        language_code="ja-JP",
        name="ja-JP-Neural2-B",  # Female voice
        # Alternative: "ja-JP-Neural2-C" (male voice)
    )
    
    # Configure audio output
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.LINEAR16,
        sample_rate_hertz=16000,
        speaking_rate=1.0,  # Normal speed
    )
    
    # Generate speech
    response = client.synthesize_speech(
        input=synthesis_input,
        voice=voice,
        audio_config=audio_config
    )
    
    # Save to file
    with open(output_file, "wb") as out:
        out.write(response.audio_content)
    
    print(f"✅ Generated: {output_file} ({len(response.audio_content)} bytes)")


def main():
    """Generate all test audio files."""
    # Get the test data directory
    script_dir = Path(__file__).parent
    audio_dir = script_dir / "tests" / "test_data" / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Output directory: {audio_dir}")
    print("-" * 60)
    
    # 1. Short audio (30 seconds)
    short_text = """
こんにちは。今日は機械学習について説明します。
機械学習は人工知能の一分野です。
データからパターンを学習することができます。
ディープラーニングは特に重要な技術です。
これで短いサンプルを終わります。
ありがとうございました。
"""
    
    generate_test_audio(
        output_file=str(audio_dir / "short_japanese_speech_30s.wav"),
        text=short_text,
        duration_description="short (30s)"
    )
    
    # 2. Medium audio (for 5-8 minutes, we need more text)
    medium_text = """
こんにちは、皆さん。本日は人工知能と機械学習について詳しくお話しします。

第一章：機械学習の基礎

機械学習とは、コンピュータがデータから学習し、予測や判断を行う技術です。
従来のプログラミングでは、人間が明示的にルールを記述していました。
しかし、機械学習では、データから自動的にパターンを発見します。

主な機械学習の種類には、教師あり学習、教師なし学習、強化学習があります。
教師あり学習では、正解ラベル付きのデータを使って学習します。
画像認識や音声認識などに広く使われています。

第二章：ディープラーニング

ディープラーニングは、ニューラルネットワークを多層化した技術です。
人間の脳の神経回路を模倣した構造になっています。
隠れ層を複数持つことで、複雑なパターンを学習できます。

畳み込みニューラルネットワークは画像処理に優れています。
リカレントニューラルネットワークは時系列データの処理に適しています。
トランスフォーマーは自然言語処理で革命的な成果を上げました。

第三章：応用事例

自動運転車では、カメラやセンサーからのデータを処理します。
医療分野では、画像診断の精度が向上しています。
音声アシスタントは自然言語を理解できるようになりました。

機械翻訳の品質も大幅に改善されています。
推薦システムは個人の好みを学習します。
不正検知システムは異常なパターンを発見します。

第四章：今後の展開

説明可能なAIの開発が進んでいます。
エッジコンピューティングでの実装が増えています。
量子機械学習の研究も始まっています。

倫理的な課題への対応も重要です。
バイアスの除去が求められています。
プライバシー保護との両立が必要です。

第五章：まとめ

機械学習は急速に発展している分野です。
実社会での応用が広がっています。
今後もさらなる進化が期待されます。

本日の発表は以上です。
ご清聴ありがとうございました。
"""
    
    generate_test_audio(
        output_file=str(audio_dir / "medium_presentation_8min.wav"),
        text=medium_text,
        duration_description="medium (5-8min)"
    )
    
    # 3. Technical vocabulary test
    technical_text = """
今日はディープラーニングフレームワークについて説明します。

TensorFlowはGoogleが開発したオープンソースフレームワークです。
PyTorchはFacebookが開発した動的計算グラフを特徴としています。
Kerasは高レベルAPIを提供し、初心者にも使いやすいです。

バックプロパゲーションアルゴリズムで勾配を計算します。
確率的勾配降下法により、パラメータを最適化します。
過学習を防ぐため、ドロップアウトを使用します。

GPUを活用することで、高速な学習が可能です。
バッチ正規化により、学習が安定します。
転移学習で事前学習モデルを活用できます。

以上、技術的な内容でした。
ありがとうございました。
"""
    
    generate_test_audio(
        output_file=str(audio_dir / "technical_terms.wav"),
        text=technical_text,
        duration_description="technical vocabulary"
    )
    
    print("-" * 60)
    print("✅ All test audio files generated successfully!")
    print()
    print("Generated files:")
    for file in audio_dir.glob("*.wav"):
        size_kb = file.stat().st_size / 1024
        print(f"  - {file.name}: {size_kb:.1f} KB")
    print()
    print("Note: These are synthetic voices. For best testing, use real presentation recordings.")


if __name__ == "__main__":
    main()
