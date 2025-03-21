# video_processing
Vertex ai pipeline:
- This Vertex AI pipeline takes an MP4 video from Google Cloud Storage (GCS), processes it through several stages to extract audio, transcribe the speech, generate subtitles, and overlay those subtitles back onto the original video. The final output is a video with embedded subtitles, stored back in GCS.
- The pipeline consists of four main components:
1. Extract MP3 audio from MP4 video
2. Transcribe audio to text using Google Cloud Speech-to-Text
3. Generate SRT subtitles from the transcription
4. Overlay the subtitles on the original video
- Each component is implemented as a Kube Flow Pipeline (KFP) component that runs in its own container, with the output of each component feeding into the next
Pipeline architecture:
The pipeline follows this data flow:
Input Video (MP4) → Extract Audio → MP3 Audio → Transcribe → JSON Transcript → Generate Subtitles →
Each component:

1.Takes input from GCS
2.Processes the data
3.Writes output back to GCS
4.Passes the GCS path to the next component
