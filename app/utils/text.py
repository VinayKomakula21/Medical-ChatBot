import re
import logging
from typing import List, Tuple
from collections import Counter
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize, sent_tokenize

logger = logging.getLogger(__name__)

# Download NLTK data if not already present
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')

try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords')

def clean_text(text: str) -> str:
    # Remove extra whitespaces
    text = re.sub(r'\s+', ' ', text)

    # Remove special characters but keep medical terms
    text = re.sub(r'[^\w\s\-\.\/\+]', '', text)

    # Remove extra line breaks
    text = re.sub(r'\n+', '\n', text)

    return text.strip()

def extract_medical_terms(text: str) -> List[str]:
    # Common medical term patterns
    patterns = [
        r'\b[A-Z]{2,}\b',  # Acronyms (e.g., HIV, AIDS, MRI)
        r'\b\w+itis\b',  # Inflammation terms
        r'\b\w+osis\b',  # Condition terms
        r'\b\w+emia\b',  # Blood condition terms
        r'\b\w+pathy\b',  # Disease terms
        r'\b\w+ectomy\b',  # Surgical removal terms
        r'\b\w+ostomy\b',  # Surgical opening terms
        r'\b\w+plasty\b',  # Surgical repair terms
        r'\bmg\b|\bml\b|\bIU\b',  # Medical units
    ]

    medical_terms = []
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        medical_terms.extend(matches)

    return list(set(medical_terms))

def summarize_text(text: str, max_sentences: int = 3) -> str:
    sentences = sent_tokenize(text)

    if len(sentences) <= max_sentences:
        return text

    # Simple extractive summarization
    # Score sentences based on word frequency
    stop_words = set(stopwords.words('english'))
    words = word_tokenize(text.lower())
    words = [word for word in words if word.isalnum() and word not in stop_words]

    word_freq = Counter(words)
    max_freq = max(word_freq.values()) if word_freq else 1

    # Normalize frequencies
    for word in word_freq:
        word_freq[word] = word_freq[word] / max_freq

    # Score sentences
    sentence_scores = {}
    for sentence in sentences:
        words_in_sentence = word_tokenize(sentence.lower())
        score = 0
        word_count = 0

        for word in words_in_sentence:
            if word in word_freq:
                score += word_freq[word]
                word_count += 1

        if word_count > 0:
            sentence_scores[sentence] = score / word_count

    # Get top sentences
    top_sentences = sorted(sentence_scores.items(), key=lambda x: x[1], reverse=True)[:max_sentences]
    top_sentences = [sent for sent, _ in top_sentences]

    # Maintain original order
    summary = []
    for sentence in sentences:
        if sentence in top_sentences:
            summary.append(sentence)
            if len(summary) >= max_sentences:
                break

    return ' '.join(summary)

def chunk_text_by_sentences(text: str, sentences_per_chunk: int = 5) -> List[str]:
    sentences = sent_tokenize(text)
    chunks = []

    for i in range(0, len(sentences), sentences_per_chunk):
        chunk = ' '.join(sentences[i:i + sentences_per_chunk])
        chunks.append(chunk)

    return chunks

def extract_key_phrases(text: str, num_phrases: int = 10) -> List[Tuple[str, float]]:
    # Simple key phrase extraction using n-grams and frequency
    stop_words = set(stopwords.words('english'))
    words = word_tokenize(text.lower())

    # Extract bigrams and trigrams
    bigrams = []
    trigrams = []

    for i in range(len(words) - 1):
        if words[i] not in stop_words and words[i + 1] not in stop_words:
            bigrams.append(f"{words[i]} {words[i + 1]}")

    for i in range(len(words) - 2):
        if words[i] not in stop_words and words[i + 2] not in stop_words:
            trigrams.append(f"{words[i]} {words[i + 1]} {words[i + 2]}")

    # Count frequencies
    phrase_freq = Counter(bigrams + trigrams)

    # Get top phrases
    top_phrases = phrase_freq.most_common(num_phrases)

    # Normalize scores
    if top_phrases:
        max_count = top_phrases[0][1]
        top_phrases = [(phrase, count / max_count) for phrase, count in top_phrases]

    return top_phrases

def detect_language(text: str) -> str:
    # Simple language detection based on character patterns
    # This is a basic implementation - consider using langdetect library for production
    if re.search(r'[а-яА-Я]', text):
        return 'russian'
    elif re.search(r'[一-龯]', text):
        return 'chinese'
    elif re.search(r'[ぁ-ゔ]', text):
        return 'japanese'
    elif re.search(r'[가-힣]', text):
        return 'korean'
    else:
        return 'english'

def calculate_text_statistics(text: str) -> dict:
    sentences = sent_tokenize(text)
    words = word_tokenize(text)
    characters = len(text)

    return {
        "character_count": characters,
        "word_count": len(words),
        "sentence_count": len(sentences),
        "average_word_length": sum(len(word) for word in words) / len(words) if words else 0,
        "average_sentence_length": len(words) / len(sentences) if sentences else 0
    }