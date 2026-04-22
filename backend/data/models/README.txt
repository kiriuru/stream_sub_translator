Current official local ASR target:
- nvidia/parakeet-tdt-0.6b-v3

Expected installed file:
- parakeet-tdt-0.6b-v3/parakeet-tdt-0.6b-v3.nemo

Install command:
- .venv\Scripts\python.exe -m backend.install_asr_model --model eu

Notes:
- This is the official EU multilingual Parakeet model path currently used by the app.
- The file is downloaded locally from Hugging Face and stored under this directory.
- CPU-first local inference is the default runtime behavior.
- If the model is missing or invalid, the app still opens but runtime start fails with a clear ASR readiness error.
- Mock ASR is only used when STREAM_SUB_TRANSLATOR_ALLOW_MOCK_ASR=1 is set explicitly.
