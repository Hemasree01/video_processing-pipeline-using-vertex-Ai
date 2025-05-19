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
### Setup Instructions
-  Step 1: Prepare Your Notebook
  - Run the provided pipeline.ipynb in Jupyter Notebook.This will generate a pipeline.json file (your compiled pipeline definition).

- Step 2: Upload Pipeline to Vertex AI
   - Go to the Vertex AI Pipelines section in the Google Cloud Console.
   - Click on "Upload Pipeline".
   - Upload the generated pipeline.json.

- Step 3: Set Service Account Permissions
  - Before running the pipeline, assign the necessary roles to the service account used for pipeline execution.
  -  How to grant permissions:
     - Navigate to IAM & Admin in the Google Cloud Console.
     - Find the service account used for Vertex AI Pipelines.
     - Click the ✏️ (pencil) icon to edit roles.
     - Assign the following roles:
        - Owner	:Full access (optional but simplifies setup)
        - Editor :General resource editing
        - Service Usage Admin :	Manage service usage and quotas
        - Storage Object Admin : Read/write access to GCS
        - Vertex AI Custom Code Service Agent :	Needed for running custom containers
        - Artifact Registry Administrator :	Pull/push container images

- Running the Pipeline
  - After uploading and configuring permissions:
     - Trigger the pipeline run in Vertex AI Pipelines UI.
     - Monitor the pipeline’s progress through each component.
     - Final subtitled video will be written back to GCS.

