import os
from typing import Optional, Dict, Any
from google.cloud import speech_v1, translate_v2, language_v1
from google.cloud.speech_v1 import RecognitionAudio
from google_cloud_config import SPEECH_CONFIG, TRANSLATION_CONFIG, LANGUAGE_CONFIG
import logging

logger = logging.getLogger(__name__)

class AIProcessor:
    def __init__(self):
        self.speech_client = speech_v1.SpeechClient()
        self.translate_client = translate_v2.Client()
        self.language_client = language_v1.LanguageServiceClient()

    async def process_voice(self, audio_path: str) -> Optional[str]:
        """
        Process voice message using Google Cloud Speech-to-Text
        """
        try:
            with open(audio_path, 'rb') as audio_file:
                content = audio_file.read()

            audio = RecognitionAudio(content=content)
            response = self.speech_client.recognize(
                config=SPEECH_CONFIG,
                audio=audio
            )

            if not response.results:
                return None

            transcript = response.results[0].alternatives[0].transcript
            confidence = response.results[0].alternatives[0].confidence

            logger.info(f"Voice processed with confidence: {confidence}")
            return transcript

        except Exception as e:
            logger.error(f"Error processing voice: {e}")
            return None

    async def analyze_text(self, text: str) -> Dict[str, Any]:
        """
        Analyze text using Google Cloud Natural Language API
        """
        try:
            document = language_v1.Document(
                content=text,
                type_=LANGUAGE_CONFIG['type'],
                language=LANGUAGE_CONFIG['language']
            )

            # Analyze sentiment
            sentiment = self.language_client.analyze_sentiment(
                request={'document': document}
            ).document_sentiment

            # Analyze entities
            entities = self.language_client.analyze_entities(
                request={'document': document}
            ).entities

            # Analyze syntax
            syntax = self.language_client.analyze_syntax(
                request={'document': document}
            ).tokens

            return {
                'sentiment': {
                    'score': sentiment.score,
                    'magnitude': sentiment.magnitude
                },
                'entities': [
                    {
                        'name': entity.name,
                        'type': entity.type_.name,
                        'salience': entity.salience
                    }
                    for entity in entities
                ],
                'syntax': [
                    {
                        'text': token.text.content,
                        'part_of_speech': token.part_of_speech.tag.name
                    }
                    for token in syntax
                ]
            }

        except Exception as e:
            logger.error(f"Error analyzing text: {e}")
            return {}

    async def translate_text(self, text: str, target_language: str = 'fa') -> Optional[str]:
        """
        Translate text using Google Cloud Translate
        """
        try:
            result = self.translate_client.translate(
                text,
                target_language=target_language
            )
            return result['translatedText']

        except Exception as e:
            logger.error(f"Error translating text: {e}")
            return None

    async def detect_language(self, text: str) -> Optional[str]:
        """
        Detect the language of the text
        """
        try:
            result = self.translate_client.detect_language(text)
            return result['language']

        except Exception as e:
            logger.error(f"Error detecting language: {e}")
            return None 