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
once the ipynb is run in jupyter notebook it will give you a json file which we need to download and upload in vertex ai pipelines.
Before runnning the pipelines we need to give the service account permissions:
- go to IAM roles and choose the service account which is used in to build the pipline and click on the pencil icon which is to edit the permission roles and give these permissions
1.Owner
2.Editor
3.service usage admin
4.Storage object admin
5.Vertex AI Custom Code Service Agent
6.artifact registry administrator
