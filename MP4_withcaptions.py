#Install required packages
pip install google-cloud-aiplatform>=1.16.0
pip install kfp>=1.8.0
pip install google-cloud-storage>=1.44.0
pip install google-cloud-speech>=2.0.0
pip install ffmpeg
#Import required libraries
import os
import json
import tempfile
import subprocess
from typing import NamedTuple
from kfp.v2 import dsl
from kfp.v2 import compiler
from google.cloud import aiplatform
from google.cloud import storage
from google.cloud import speech_v1p1beta1 as speech
#first component
@dsl.component(
    base_image="python:3.9",
    packages_to_install=["ffmpeg-python", "google-cloud-storage"],
)
def extract_audio_from_video(
    input_video_gcs_path: str,
    output_audio_gcs_path: str
) -> str:
    """Extract MP3 audio from MP4 video."""
    import os
    import subprocess
    import tempfile
    from google.cloud import storage
    
    print(f"Extracting audio from {input_video_gcs_path} to {output_audio_gcs_path}")
    
    # Install FFmpeg directly in the component
    print("Installing FFmpeg...")
    subprocess.run(["apt-get", "update", "-y"], check=True)
    subprocess.run(["apt-get", "install", "-y", "ffmpeg"], check=True)
    print("FFmpeg installed successfully")
    
    # Create temporary directory for processing
    with tempfile.TemporaryDirectory() as temp_dir:
        # Download video from GCS
        storage_client = storage.Client()
        
        # Parse bucket and blob names
        input_path = input_video_gcs_path.replace("gs://", "")
        bucket_name = input_path.split("/")[0]
        blob_name = "/".join(input_path.split("/")[1:])
        
        # Get bucket and blob
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        
        # Download to temporary file
        local_video_path = os.path.join(temp_dir, os.path.basename(blob_name))
        blob.download_to_filename(local_video_path)
        print(f"Video downloaded to {local_video_path}")
        
        # Extract audio using FFmpeg
        local_audio_path = os.path.join(temp_dir, os.path.splitext(os.path.basename(blob_name))[0] + ".mp3")
        print(f"Extracting audio to {local_audio_path}")
        
        # Using subprocess for FFmpeg
        cmd = [
            "ffmpeg", "-i", local_video_path, 
            "-vn",  # No video
            "-acodec", "mp3",  # MP3 codec
            "-ab", "192k",  # Bitrate
            "-ar", "44100",  # Sample rate
            "-y",  # Overwrite output file
            local_audio_path
        ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            print("Audio extraction completed successfully")
        except subprocess.CalledProcessError as e:
            print(f"FFmpeg error: {e.stderr.decode()}")
            raise RuntimeError(f"Failed to extract audio: {e}")
        
        # Upload extracted audio to GCS
        print(f"Uploading audio to {output_audio_gcs_path}")
        output_path = output_audio_gcs_path.replace("gs://", "")
        output_bucket_name = output_path.split("/")[0]
        output_blob_name = "/".join(output_path.split("/")[1:])
        
        output_bucket = storage_client.bucket(output_bucket_name)
        output_blob = output_bucket.blob(output_blob_name)
        output_blob.upload_from_filename(local_audio_path)
        
        print(f"Audio extraction and upload complete")
        
        return output_audio_gcs_path
#second component
@dsl.component(
    base_image="python:3.9",
    packages_to_install=["google-cloud-speech", "google-cloud-storage"],
)
def transcribe_audio(
    audio_gcs_path: str,
    output_transcript_gcs_path: str,
    language_code: str = "en-US"
) -> str:
    """Transcribe MP3 audio to text using Google Cloud Speech-to-Text."""
    import os
    import json
    import tempfile
    from google.cloud import speech_v1p1beta1 as speech
    from google.cloud import storage
    
    print(f"Transcribing audio from {audio_gcs_path} to {output_transcript_gcs_path}")
    
    # Create Speech-to-Text client and storage client
    speech_client = speech.SpeechClient()
    storage_client = storage.Client()
    
    # Configure the speech recognition request
    audio = speech.RecognitionAudio(uri=audio_gcs_path)
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.MP3,
        sample_rate_hertz=44100,
        language_code=language_code,
        enable_word_time_offsets=True,
        enable_automatic_punctuation=True,
        model="latest_long"  # Use the latest_long model for better accuracy with video content and to include short occurances.
    )
    
    # Start the long-running recognition operation
    print("Starting transcription (this may take a while)...")
    operation = speech_client.long_running_recognize(config=config, audio=audio)
    
    # Wait for operation to complete
    response = operation.result(timeout=600)  # Increased timeout for longer audio
    print("Transcription completed")
    
    # Process the response
    transcript_data = {
        "transcript": "",
        "words": [],
        "results": []
    }
    
    for result in response.results:
        alternative = result.alternatives[0]
        transcript_data["transcript"] += alternative.transcript + " "
        
        # Add detailed results
        result_data = {
            "transcript": alternative.transcript,
            "confidence": alternative.confidence,
            "words": []
        }
        
        # Add word-level information if available
        for word_info in alternative.words:
            # Handle different response formats (timedelta vs seconds/nanos)
            if hasattr(word_info.start_time, 'seconds') and hasattr(word_info.start_time, 'nanos'):
                # Old format with seconds and nanos
                start_seconds = f"{word_info.start_time.seconds}.{word_info.start_time.nanos//1000000:03d}"
                end_seconds = f"{word_info.end_time.seconds}.{word_info.end_time.nanos//1000000:03d}"
            else:
                # New format with timedelta
                start_seconds = str(word_info.start_time.total_seconds())
                end_seconds = str(word_info.end_time.total_seconds())
            
            word_data = {
                "word": word_info.word,
                "start_time": start_seconds,
                "end_time": end_seconds
            }
            transcript_data["words"].append(word_data)
            result_data["words"].append(word_data)
        
        transcript_data["results"].append(result_data)
    
    # Save transcript to GCS
    with tempfile.TemporaryDirectory() as temp_dir:
        local_transcript_path = os.path.join(temp_dir, "transcript.json")
        
        with open(local_transcript_path, "w") as f:
            json.dump(transcript_data, f, indent=2)
        
        # Upload to GCS
        print(f"Uploading transcript to {output_transcript_gcs_path}")
        output_path = output_transcript_gcs_path.replace("gs://", "")
        output_bucket_name = output_path.split("/")[0]
        output_blob_name = "/".join(output_path.split("/")[1:])
        
        output_bucket = storage_client.bucket(output_bucket_name)
        output_blob = output_bucket.blob(output_blob_name)
        output_blob.upload_from_filename(local_transcript_path)
    
    print(f"Transcription saved to {output_transcript_gcs_path}")
    
    return output_transcript_gcs_path
#third component
@dsl.component(
    base_image="python:3.9",
    packages_to_install=["google-cloud-storage"],
)
def generate_subtitles(
    transcript_gcs_path: str,
    output_subtitles_gcs_path: str,
    max_chars_per_line: int = 42
) -> str:
    """Generate an SRT file that formats words into sentences while preserving exact timing."""
    
    import os
    import json
    import tempfile
    import re
    from google.cloud import storage

    print(f"Generating sentence-based subtitles from {transcript_gcs_path} to {output_subtitles_gcs_path}")

    storage_client = storage.Client()
    
    # Download transcript from GCS
    input_path = transcript_gcs_path.replace("gs://", "")
    bucket_name = input_path.split("/")[0]
    blob_name = "/".join(input_path.split("/")[1:])
    
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        local_transcript_path = os.path.join(temp_dir, "transcript.json")
        blob.download_to_filename(local_transcript_path)
        
        # Load transcript
        with open(local_transcript_path, "r") as f:
            transcript_data = json.load(f)
        
        words = transcript_data.get("words", [])
        if not words:
            print("No word-level timing information found in transcript")
            return None
        
        # Function to convert time to SRT format
        def format_time(time_str):
            """Convert seconds to SRT time format (HH:MM:SS,mmm)"""
            seconds = float(time_str)
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            seconds = seconds % 60
            return f"{hours:02d}:{minutes:02d}:{seconds:06.3f}".replace(".", ",")
        
        # Group words into sentences based on punctuation
        def is_sentence_end(word):
            """Check if a word marks the end of a sentence."""
            return bool(re.search(r'[.!?]$', word))

        srt_content = ""
        subtitle_count = 1
        i = 0
        
        while i < len(words):
            sentence_words = []
            start_time = words[i]["start_time"]
            end_time = words[i]["end_time"]
            
            while i < len(words):
                word = words[i]
                sentence_words.append(word["word"])
                end_time = word["end_time"]
                
                if is_sentence_end(word["word"]) or i == len(words) - 1:
                    break
                
                i += 1
            
            i += 1  # Move to the next word for the next subtitle
            
            # Format sentence text to fit within max_chars_per_line
            formatted_lines = []
            current_line = []
            current_line_chars = 0
            
            for word in sentence_words:
                if current_line_chars + len(word) + 1 > max_chars_per_line and current_line:
                    formatted_lines.append(" ".join(current_line))
                    current_line = [word]
                    current_line_chars = len(word)
                else:
                    current_line.append(word)
                    current_line_chars += len(word) + (1 if current_line_chars > 0 else 0)
            
            if current_line:
                formatted_lines.append(" ".join(current_line))
            
            # Create subtitle entry
            srt_content += f"{subtitle_count}\n"
            srt_content += f"{format_time(start_time)} --> {format_time(end_time)}\n"
            srt_content += "\n".join(formatted_lines) + "\n\n"
            subtitle_count += 1

        # Save SRT file
        local_srt_path = os.path.join(temp_dir, "subtitles.srt")
        with open(local_srt_path, "w") as f:
            f.write(srt_content)
        
        # Upload to GCS
        output_path = output_subtitles_gcs_path.replace("gs://", "")
        output_bucket_name = output_path.split("/")[0]
        output_blob_name = "/".join(output_path.split("/")[1:])
        
        output_bucket = storage_client.bucket(output_bucket_name)
        output_blob = output_bucket.blob(output_blob_name)
        output_blob.upload_from_filename(local_srt_path)
    
    print(f"Generated precise sentence-based subtitles and uploaded to {output_subtitles_gcs_path}")
    
    return output_subtitles_gcs_path
@dsl.component(
    base_image="python:3.9",
    packages_to_install=["ffmpeg-python", "google-cloud-storage"],
)
def overlay_subtitles_on_video(
    input_video_gcs_path: str,
    subtitles_gcs_path: str,
    output_video_gcs_path: str,
    font_size: int = 48,
    font_color: str = "white"
) -> str:
    """Overlay SRT subtitles on video ensuring exact sentence-based sync."""
    
    import os
    import subprocess
    import tempfile
    from google.cloud import storage

    print(f"Overlaying subtitles from {subtitles_gcs_path} on {input_video_gcs_path}")

    # Install FFmpeg
    subprocess.run(["apt-get", "update", "-y"], check=True)
    subprocess.run(["apt-get", "install", "-y", "ffmpeg"], check=True)

    storage_client = storage.Client()
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Download video from GCS
        input_video_path = input_video_gcs_path.replace("gs://", "")
        video_bucket_name = input_video_path.split("/")[0]
        video_blob_name = "/".join(input_video_path.split("/")[1:])
        
        video_bucket = storage_client.bucket(video_bucket_name)
        video_blob = video_bucket.blob(video_blob_name)
        
        local_video_path = os.path.join(temp_dir, os.path.basename(video_blob_name))
        video_blob.download_to_filename(local_video_path)

        # Download subtitles from GCS
        subtitles_path = subtitles_gcs_path.replace("gs://", "")
        subtitles_bucket_name = subtitles_path.split("/")[0]
        subtitles_blob_name = "/".join(subtitles_path.split("/")[1:])
        
        subtitles_bucket = storage_client.bucket(subtitles_bucket_name)
        subtitles_blob = subtitles_bucket.blob(subtitles_blob_name)
        
        local_subtitles_path = os.path.join(temp_dir, "subtitles.srt")
        subtitles_blob.download_to_filename(local_subtitles_path)

        # Output video path
        local_output_video_path = os.path.join(
            temp_dir, 
            f"{os.path.splitext(os.path.basename(video_blob_name))[0]}_with_subtitles.mp4"
        )

        # Overlay subtitles using FFmpeg with exact timing
        print("Overlaying subtitles with sentence-based exact sync")
        cmd = [
            "ffmpeg", "-i", local_video_path,
            "-vf", f"subtitles={local_subtitles_path}",
            "-c:a", "copy",  # Preserve original audio
            "-y",  # Overwrite output file
            local_output_video_path
        ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            print("Subtitle overlay completed successfully with exact sentence sync")
        except subprocess.CalledProcessError as e:
            print(f"FFmpeg error: {e.stderr.decode()}")
            raise RuntimeError("Failed to overlay subtitles with exact sync")

        # Upload output video to GCS
        output_path = output_video_gcs_path.replace("gs://", "")
        output_bucket_name = output_path.split("/")[0]
        output_blob_name = "/".join(output_path.split("/")[1:])
        
        output_bucket = storage_client.bucket(output_bucket_name)
        output_blob = output_bucket.blob(output_blob_name)
        output_blob.upload_from_filename(local_output_video_path)

        print(f"Video with exact subtitles uploaded to {output_video_gcs_path}")
        
        return output_video_gcs_path
from typing import NamedTuple

@dsl.pipeline(
    name="video-processing-pipeline",
    description="A pipeline that processes MP4 videos, extracts audio, generates transcriptions, and overlays subtitles"
)
def video_processing_pipeline(
    input_video_gcs_path: str,
    output_bucket: str,
    language_code: str = "en-US"
) -> NamedTuple('Outputs', [('output_video', str)]):  # Add this return type annotation
    """Pipeline that processes video files with subtitle generation."""
    
    # Define output paths
    video_basename = "video"  # Using fixed names to avoid string manipulation in pipeline
    
    output_audio_gcs_path = f"gs://{output_bucket}/output/audio/{video_basename}.mp3"
    output_transcript_gcs_path = f"gs://{output_bucket}/output/transcripts/{video_basename}.json"
    output_subtitles_gcs_path = f"gs://{output_bucket}/output/subtitles/{video_basename}.srt"
    output_video_gcs_path = f"gs://{output_bucket}/output/videos/{video_basename}_with_subtitles.mp4"
    
    # Step 1: Extract audio from video
    extract_task = extract_audio_from_video(
        input_video_gcs_path=input_video_gcs_path,
        output_audio_gcs_path=output_audio_gcs_path
    )
    
    # Step 2: Transcribe audio to text
    transcribe_task = transcribe_audio(
        audio_gcs_path=extract_task.output,
        output_transcript_gcs_path=output_transcript_gcs_path,
        language_code=language_code
    )
    
    # Step 3: Generate subtitles from transcription
    subtitles_task = generate_subtitles(
        transcript_gcs_path=transcribe_task.output,
        output_subtitles_gcs_path=output_subtitles_gcs_path
    )
    
    # Step 4: Overlay subtitles on video
    overlay_task = overlay_subtitles_on_video(
        input_video_gcs_path=input_video_gcs_path,
        subtitles_gcs_path=subtitles_task.output,
        output_video_gcs_path=output_video_gcs_path
    )
    
    # Return the final output with proper naming
    return NamedTuple('Outputs', [('output_video', str)])(overlay_task.output)

# STEP 6: Compile the Pipeline
compiler.Compiler().compile(
    pipeline_func=video_processing_pipeline,
    package_path="video_processing_pipeline.json"
)

print("Pipeline compiled successfully to video_processing_pipeline.json")
