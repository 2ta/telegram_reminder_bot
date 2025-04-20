import os
from google.cloud import speech, translate, language
from google.cloud import speech_v1
from google.cloud.speech_v1 import enums
from google.cloud import translate_v2 as translate
from google.cloud import language_v1

# Google Cloud configuration
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY', 'AIzaSyBPAkx_LdoL_WXMDCFfmHbYEcnyhViS_ro')

# Speech recognition settings
SPEECH_CONFIG = speech_v1.RecognitionConfig(
    encoding=enums.RecognitionConfig.AudioEncoding.LINEAR16,
    sample_rate_hertz=16000,
    language_code="fa-IR",
    enable_automatic_punctuation=True,
)

# Translation settings
TRANSLATION_CONFIG = {
    'target_language': 'fa',
    'source_language': 'en'
}

# Natural Language settings
LANGUAGE_CONFIG = {
    'type': language_v1.Document.Type.PLAIN_TEXT,
    'language': 'fa'
} 