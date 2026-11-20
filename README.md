🔊 VANI — Text-to-Speech API & Web Dashboard

<p align="center">
  <img src="https://capsule-render.vercel.app/api?type=venom&color=0:09090F,50:4C1D95,100:06B6D4&height=220&section=header&text=VANI&fontSize=85&fontColor=ffffff&animation=fadeIn&fontAlignY=40&desc=Give%20Your%20Words%20a%20Voice&descSize=18&descAlignY=65" width="100%" alt="VANI Banner"/>
</p><p align="center">
  <b>A self-hosted Text-to-Speech platform with a REST API and an interactive web dashboard.</b>
  <br/>
  Convert text into natural-sounding speech, customize voices, control playback speed, and manage generated audio.
</p><p align="center">
  <a href="https://github.com/Rg100152/Vani">
    <img src="https://img.shields.io/badge/GitHub-Repository-181717?style=for-the-badge&logo=github" alt="GitHub"/>
  </a>
  <img src="https://img.shields.io/badge/Python-3.9+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python"/>
  <img src="https://img.shields.io/badge/Flask-Web%20Framework-black?style=for-the-badge&logo=flask" alt="Flask"/>
  <img src="https://img.shields.io/badge/OpenAI-Text%20to%20Speech-412991?style=for-the-badge&logo=openai" alt="OpenAI"/>
  <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="MIT License"/>
</p><p align="center">
  <a href="#-overview">Overview</a> •
  <a href="#-features">Features</a> •
  <a href="#-installation">Installation</a> •
  <a href="#-api-reference">API Reference</a> •
  <a href="#-configuration">Configuration</a> •
  <a href="#-contributing">Contributing</a>
</p>---

📖 Overview

VANI is a lightweight, single-file Python application that transforms written text into speech using the official OpenAI Text-to-Speech API.

It combines two interfaces in one application:

- Web Dashboard: Generate speech, preview audio, manage your audio library, test API requests and inspect server settings.
- REST API: Integrate text-to-speech functionality into websites, applications, automation scripts and other Python projects.

The goal is simple:

«Make Text-to-Speech integration easier for developers, students and independent creators.»

VANI is designed as an accessible starting point for anyone interested in Python, Flask, REST APIs and AI-powered audio applications.

🎯 Who Is VANI For?

- 👨‍💻 Developers building voice-enabled applications.
- 🎓 Students learning Python and API integration.
- 🤖 AI enthusiasts experimenting with speech generation.
- 🎙️ Content creators generating audio from written text.
- 🛠️ Developers building automation workflows.
- 🌐 Independent developers who need a self-hosted TTS service.

✨ Features

🔊 Speech Generation

- Convert text into audio.
- Multiple AI voices.
- Multiple speech models.
- Adjustable speech speed.
- Custom speech instructions.
- Automatic audio playback in the dashboard.

🎛️ Audio Customization

- Select voice and model.
- Choose audio output format.
- Control speed from 0.25x to 4.0x.
- Provide optional speaking-style instructions.

📚 Audio Library

- Automatically save generated audio.
- Maintain generation history.
- Preview saved audio.
- Download generated files.
- Delete individual audio records.

🔌 Developer API

- RESTful JSON endpoints.
- Python integration support.
- cURL examples.
- API documentation endpoint.
- Interactive API playground.

🔐 Security & Management

- Optional Bearer token authentication.
- Constant-time API key comparison.
- Per-IP rate limiting.
- Input validation.
- Audio filename validation.
- Restricted output file paths.
- Request size limits.

🧰 Technology Stack

Technology| Purpose
Python| Core application
Flask| Web server and REST API
OpenAI Python SDK| Speech generation
HTML5| Dashboard structure
CSS3| Dashboard styling
JavaScript| Dashboard interactions
JSON| Audio metadata storage

🏗️ Architecture

VANI follows a simple request-processing architecture.

flowchart TD
    A["User / Developer"] --> B["VANI Application"]
    B --> C["Flask Server"]
    C --> D["Input Validation"]
    D --> E["Authentication & Rate Limit"]
    E --> F["OpenAI Text-to-Speech API"]
    F --> G["Generated Audio"]
    G --> H["Local Audio Storage"]
    H --> I["JSON Metadata"]
    I --> J["Audio Response"]
    J --> K["Dashboard / REST API"]

Application Components

1. Configuration Manager — Reads environment variables.
2. Authentication Layer — Validates optional API tokens.
3. Rate Limiter — Controls request frequency.
4. Validation Engine — Validates text, model, voice, speed and format.
5. Speech Generator — Communicates with the OpenAI API.
6. Audio Manager — Saves and retrieves generated audio.
7. Metadata Manager — Maintains generation history.
8. Flask Server — Provides dashboard and API routes.

📸 Dashboard

VANI includes a dark, responsive web dashboard with five main sections.

Section| Functionality
Generate| Create speech from text
Library| Browse, play, download and delete audio
API Playground| Test JSON API requests
Documentation| View usage instructions
Settings| Inspect configuration and server status

The dashboard also displays:

- Total generated audio count.
- Default speech model.
- API configuration status.
- Authentication status.

🚀 Installation

Requirements

- Python 3.9 or newer.
- pip package manager.
- Internet connection.
- OpenAI API key with access to the Speech API.

Step 1 — Clone Repository

git clone https://github.com/Rg100152/Vani.git

cd Vani

Step 2 — Create Virtual Environment (Recommended)

python -m venv venv

Activate:

Linux / macOS

source venv/bin/activate

Windows

venv\Scripts\activate

Step 3 — Install Dependencies

pip install flask openai

Step 4 — Configure OpenAI API Key

Linux / macOS

export OPENAI_API_KEY="your_openai_api_key"

Windows PowerShell

$env:OPENAI_API_KEY="your_openai_api_key"

Step 5 — Start VANI

python Vani.py

Step 6 — Open Dashboard

http://127.0.0.1:5060

<badge color="success">Ready to use</badge>

Your VANI server is now running locally.

⚙️ Configuration

VANI supports environment-based configuration.

Environment Variable| Default| Description
"OPENAI_API_KEY"| None| Required OpenAI API key
"VANI_API_KEY"| None| Optional API authentication
"VANI_HOST"| "127.0.0.1"| Server host
"VANI_PORT"| "5060"| Server port
"VANI_OUTPUT_DIR"| "./vani_output"| Audio storage directory
"VANI_MODEL"| "gpt-4o-mini-tts"| Default TTS model
"VANI_VOICE"| "coral"| Default voice
"VANI_RATE_LIMIT"| "10"| Requests per minute per IP

Advanced Configuration Example

export OPENAI_API_KEY="your_key"
export VANI_API_KEY="your_secret_token"

export VANI_HOST="127.0.0.1"
export VANI_PORT="5060"

export VANI_MODEL="gpt-4o-mini-tts"
export VANI_VOICE="coral"

export VANI_RATE_LIMIT="10"

python Vani.py

Security: Never publish your API keys, commit them to GitHub, or expose them in frontend JavaScript.

🎙️ Supported Speech Models

VANI currently exposes three models:

Model| Description
"gpt-4o-mini-tts"| Instruction-aware speech generation
"tts-1"| Text-to-speech generation
"tts-1-hd"| High-definition text-to-speech generation

Model access and availability depend on your OpenAI API account.

🗣️ Supported Voices

VANI currently exposes these voice identifiers:

Voice| Voice ID
Alloy| "alloy"
Ash| "ash"
Ballad| "ballad"
Coral| "coral"
Echo| "echo"
Fable| "fable"
Onyx| "onyx"
Nova| "nova"
Sage| "sage"
Shimmer| "shimmer"
Verse| "verse"
Marin| "marin"
Cedar| "cedar"

Voice availability can depend on the selected model and current API support.

🎵 Supported Audio Formats

VANI supports:

- MP3
- OPUS
- AAC
- FLAC
- WAV
- PCM

Default output format: "mp3"

🔌 API Reference

Base URL

http://127.0.0.1:5060

Endpoint Overview

Method| Endpoint| Description
GET| "/health"| Server health information
GET| "/v1/docs"| API documentation
GET| "/v1/models"| Available models, voices and formats
POST| "/v1/audio/speech"| Generate speech
GET| "/v1/audio"| List generated audio
GET| "/v1/audio/<audio_id>"| Retrieve audio
DELETE| "/v1/audio/<audio_id>"| Delete audio

1. Generate Speech

Endpoint

POST /v1/audio/speech
Content-Type: application/json

Request Body

{
  "input": "Hello! Welcome to VANI.",
  "model": "gpt-4o-mini-tts",
  "voice": "coral",
  "response_format": "mp3",
  "speed": 1.0,
  "instructions": "Speak in a warm and friendly tone."
}

Parameter| Type| Required| Description
"input"| String| Yes*| Text to convert into speech
"text"| String| Yes*| Alternative input field
"model"| String| No| TTS model
"voice"| String| No| Voice selection
"response_format"| String| No| Audio format
"speed"| Number| No| Speech speed (0.25–4.0)
"instructions"| String| No| Speaking style instructions

*Provide either "input" or "text". The default values are used for omitted optional parameters.

The maximum input length is 4096 characters.

Note: "instructions" is supported by "gpt-4o-mini-tts" in this implementation, not "tts-1" or "tts-1-hd".

2. cURL Integration

curl -X POST http://127.0.0.1:5060/v1/audio/speech \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_VANI_API_KEY" \
  -d '{
    "input": "Hello from VANI",
    "model": "gpt-4o-mini-tts",
    "voice": "coral",
    "response_format": "mp3",
    "speed": 1.0
  }'

If authentication is disabled, remove the Authorization header.

3. Python Integration

Install requests:

pip install requests

Example:

import requests

API_URL = "http://127.0.0.1:5060"

payload = {
    "input": "Hello, this is VANI speaking.",
    "model": "gpt-4o-mini-tts",
    "voice": "coral",
    "response_format": "mp3",
    "speed": 1.0
}

headers = {
    "Authorization": "Bearer YOUR_VANI_API_KEY"
}

response = requests.post(
    f"{API_URL}/v1/audio/speech",
    json=payload,
    headers=headers,
    timeout=180
)

if response.ok:
    result = response.json()
    print("Generated:", result["url"])
else:
    print("Error:", response.text)

4. Retrieve Generated Audio

curl http://127.0.0.1:5060/v1/audio/AUDIO_ID \
  -H "Authorization: Bearer YOUR_VANI_API_KEY" \
  --output generated.mp3

Replace "AUDIO_ID" with the actual generated audio ID.

5. List Audio History

curl http://127.0.0.1:5060/v1/audio \
  -H "Authorization: Bearer YOUR_VANI_API_KEY"

6. Delete Generated Audio

curl -X DELETE \
  http://127.0.0.1:5060/v1/audio/AUDIO_ID \
  -H "Authorization: Bearer YOUR_VANI_API_KEY"

7. Check Server Health

curl http://127.0.0.1:5060/health

8. Access API Documentation

http://127.0.0.1:5060/v1/docs

This endpoint returns machine-readable JSON documentation.

📂 Project Structure

Vani/
│
├── Vani.py
├── README.md
├── LICENSE
│
└── vani_output/
    ├── _metadata.json
    ├── audio-id-1.mp3
    ├── audio-id-2.wav
    └── audio-id-3.opus

Storage Details

VANI automatically creates its output directory.

- Audio files are stored locally.
- "_metadata.json" contains generation history.
- Each generated audio file receives a unique UUID.
- Metadata is updated when audio is generated or deleted.

🔒 Security & Deployment

VANI implements several basic security measures:

- Optional Bearer token authentication.
- Constant-time API token comparison.
- Per-IP in-memory rate limiting.
- Input validation and length restrictions.
- Audio extension validation.
- File path restrictions.
- 16 MB Flask request-size limit.

Production Considerations

Before exposing VANI to external users:

1. Configure a strong "VANI_API_KEY".
2. Use HTTPS.
3. Keep OpenAI credentials server-side.
4. Deploy behind a production WSGI server.
5. Use persistent rate limiting for multi-worker deployments.
6. Restrict access to audio management endpoints.
7. Monitor API usage and costs.
8. Implement suitable data retention and backup policies.

The built-in Flask development server is intended for development and testing, not production deployment.

💰 API Usage & Costs

VANI is an open-source application, but speech generation is powered by the OpenAI API.

- An OpenAI API key is required.
- API usage may incur charges.
- Pricing depends on the selected model and current provider pricing.
- VANI does not include free OpenAI API credits.

Check the official "OpenAI API Pricing" (https://openai.com/api/pricing/) before using the service.

🧪 Error Handling

HTTP Status| Meaning
"201"| Speech generated successfully
"400"| Invalid request or parameters
"401"| Missing or invalid API key
"402"| API quota or billing issue
"404"| Audio not found
"415"| Unsupported content type
"429"| Rate limit exceeded
"500"| Internal server error
"502"| OpenAI API error
"503"| OpenAI API key not configured

🛣️ Future Possibilities

Potential community-driven improvements:

- Additional language and voice examples.
- Batch speech generation.
- Improved audio metadata search.
- API usage analytics.
- Docker deployment support.
- Database-backed storage.
- Improved authentication management.
- Streaming speech output.
- Better deployment documentation.

These are proposed improvements, not claims about currently implemented functionality.

🌱 Contributing

VANI welcomes developers, students, beginners and open-source enthusiasts.

You do not need to be an expert to contribute.

Ways to contribute

- Report bugs.
- Suggest new features.
- Improve documentation.
- Share integration examples.
- Improve the dashboard.
- Test the API.
- Submit code improvements.

Contribution Workflow

1. Fork the repository.
2. Clone your fork.
3. Create a feature branch.
4. Make your changes.
5. Test your implementation.
6. Submit a Pull Request.

git clone https://github.com/YOUR_USERNAME/Vani.git

cd Vani

git checkout -b feature/your-feature

git add .

git commit -m "Add: your feature"

git push origin feature/your-feature

📜 License

VANI is licensed under the MIT License.

You are welcome to use, modify, distribute and build upon this project under the terms of the included LICENSE file.

See "LICENSE" (LICENSE) for details.

👨‍💻 Author

Raj Gautam

BCA Student | Python Learner | Linux & Open-Source Enthusiast

- GitHub: "@Rg100152" (https://github.com/Rg100152)
- Project: "VANI Repository" (https://github.com/Rg100152/Vani)

---

<p align="center">
  <img src="https://capsule-render.vercel.app/api?type=waving&color=0:4C1D95,100:06B6D4&height=120&section=footer" width="100%" alt="Footer"/>
  <b>Built for developers. Open to everyone.</b>
  <br/>
  ⭐ If VANI helps your project, consider starring this repository.
  <br/><br/>
  <i>Your words. Your voice. Your creativity.</i>
</p>
