# Real-Time Streaming Demo Setup

## Quick Start

### 1. Install Dependencies

```bash
# Install PortAudio (required for microphone access)
brew install portaudio

# Install Python packages
pip install pyaudio google-cloud-speech
```

### 2. Setup Google Cloud Credentials

**Option A: Use existing credentials file**

```bash
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/your/service-account.json
export GOOGLE_CLOUD_PROJECT=your-project-id
```

**Option B: Use gcloud CLI**

```bash
gcloud auth application-default login
export GOOGLE_CLOUD_PROJECT=$(gcloud config get-value project)
```

### 3. Run the Demo

```bash
python demo_realtime_streaming.py
```

## What You'll See

```
================================================================================
🎤 REAL-TIME JAPANESE SPEECH-TO-TEXT DEMO
================================================================================

Instructions:
  • Speak Japanese into your microphone
  • Gray text = Interim results (partial, may change)
  • Green text = Final results (confirmed)
  • Press Ctrl+C to stop

================================================================================

🔗 Connecting to Google Cloud Speech API...
   Project: your-project-id
   Model: latest_long (ja-JP)
   Sample Rate: 16000 Hz
   Chunk Size: 1600 samples (100ms)

📝 Creating streaming session...
🚀 Starting speech recognition...

🎙️  Recording... (speak now)

--------------------------------------------------------------------------------

  こんにちは                                    ← Interim (gray)
✓ こんにちは、今日は良い天気ですね。            ← Final (green)
  音声認識のテストを                           ← Interim (gray)
✓ 音声認識のテストを行っています。             ← Final (green)

⏹️  Stopping...

Finalizing session...

================================================================================
📊 SESSION STATISTICS
================================================================================

Session:
  Duration: 45.2 seconds
  Chunks sent: 452
  Bytes sent: 723,200

Audio:
  Valid chunks: 452
  Invalid chunks: 0
  Avg chunk size: 1600 bytes

Results:
  Interim results: 87
  Final results: 12
  Avg confidence: 94.50%

================================================================================
STREAMING METRICS DASHBOARD
================================================================================
... (detailed metrics) ...

✅ Demo completed successfully!
```

## Features Demonstrated

### 1. Real-Time Streaming

- Audio captured from microphone in 100ms chunks
- Sent to Google Cloud Speech API via gRPC bidirectional stream
- Results displayed as they arrive

### 2. Interim vs Final Results

- **Interim Results (Gray):** Partial transcription that updates as you speak
- **Final Results (Green):** Confirmed transcription that won't change

### 3. Metrics Collection

- Latency tracking (p50/p95/p99)
- Confidence scores
- Throughput (chunks/second, bytes/second)
- Cost calculation

### 4. Alert System

- Monitors for high latency
- Detects stuck sessions
- Alerts on errors

## Troubleshooting

### "GOOGLE_APPLICATION_CREDENTIALS not set"

```bash
# Set your credentials file path
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json

# Or use gcloud default credentials
gcloud auth application-default login
```

### "No audio input device found"

```bash
# Check available devices
python -c "import pyaudio; p=pyaudio.PyAudio(); [print(f'{i}: {p.get_device_info_by_index(i)[\"name\"]}') for i in range(p.get_device_count())]"

# Grant microphone permissions in System Preferences > Security & Privacy
```

### "Permission denied" for microphone

- On macOS: System Preferences > Security & Privacy > Microphone
- Enable access for Terminal or your IDE

### "Module not found" errors

```bash
# Reinstall dependencies
pip install --upgrade google-cloud-speech pyaudio
```

### High latency or poor quality

- Check internet connection
- Use wired connection instead of WiFi
- Reduce background noise
- Speak clearly at normal volume

## Advanced Usage

### Custom Configuration

Edit `demo_realtime_streaming.py`:

```python
# Change language
language_code="en-US"  # English
language_code="vi-VN"  # Vietnamese

# Change model
model="latest_short"   # Faster interim results
model="latest_long"    # Better accuracy (default)

# Adjust chunk size
CHUNK = int(RATE / 5)  # 200ms chunks (lower latency)
CHUNK = int(RATE / 20) # 50ms chunks (higher CPU)
```

### Monitor Metrics in Real-Time

The demo automatically tracks and displays:

- Session duration
- Audio chunks sent/received
- Latency percentiles
- Confidence scores
- Cost estimation

### Alert Thresholds

Modify alert configuration:

```python
alert_config = AlertConfig(
    latency_p95_warning=500.0,     # Alert if p95 > 500ms
    latency_p95_critical=1000.0,   # Critical if > 1000ms
    error_rate_warning=3.0,        # Warn at 3% errors
    error_rate_critical=10.0,      # Critical at 10%
)
```

## Testing Different Scenarios

### 1. Continuous Speech

Speak without pausing - tests sustained streaming performance

### 2. Natural Pauses

Speak with normal pauses - tests silence handling and VAD

### 3. Long Sessions

Speak for >5 minutes - tests automatic session renewal

### 4. Background Noise

Test in noisy environment - validates noise handling

### 5. Varying Volume

Whisper and shout - tests AGC (Automatic Gain Control)

## Next Steps

After testing the demo:

1. **Integration:** Integrate into your application
2. **Customization:** Adjust parameters for your use case
3. **Scale Testing:** Test with multiple concurrent sessions
4. **Production Deploy:** Add error handling, logging, monitoring

## Cost Estimation

Google Cloud Speech-to-Text V2 pricing:

- $2.16 per hour of audio (latest_long model)
- $0.036 per minute
- $0.0006 per second

Example costs:

- 1 minute demo: ~$0.04
- 10 minute presentation: ~$0.36
- 1 hour meeting: ~$2.16

The demo displays actual cost in the final statistics.

## Support

For issues:

1. Check error messages in terminal
2. Verify Google Cloud credentials
3. Test microphone access
4. Review troubleshooting section above
5. Check `tests/README.md` for more details
