"""macsum_eval_agent 도메인의 축별 검사 함수. agents/domain_onboarding.py 가
자동 생성함 - measure_* 함수는 샌드박스에서 판별력을 검증받은 뒤 채택된
코드다."""

from __future__ import annotations

import re
import math
import statistics
import collections

def measure_conciseness(text: str, source: str) -> float:
    # Tokenize text into words and sentences using simple splits
    words = text.split()
    sentences = [s for s in re.split(r'[.!?]+', text) if s.strip()]
    if not words or not sentences:
        return 0.5  # neutral if no content
    
    # Average sentence length in words
    avg_sent_len = len(words) / len(sentences)
    
    # Count commas and semicolons as indicators of detail/elaboration
    comma_count = text.count(',')
    semicolon_count = text.count(';')
    punctuation_detail = (comma_count + semicolon_count) / max(len(words),1)
    
    # Count unique words to total words ratio (lexical diversity)
    unique_words = len(set(words))
    lexical_diversity = unique_words / len(words)
    
    # Score combining inverse avg sentence length (shorter = concise)
    # and punctuation detail (more = detailed)
    # Normalize avg_sent_len to a 0-1 scale roughly: 5 words per sentence = concise, 25 = very detailed
    sent_len_norm = min(max((avg_sent_len - 5) / 20, 0), 1)
    # punctuation_detail usually small, scale to 0-1 by max 0.1 (10%)
    punctuation_norm = min(punctuation_detail / 0.1, 1)
    
    # Combine features: more punctuation and longer sentences => detailed (higher score)
    # So detailed score = weighted sum of sent_len_norm and punctuation_norm
    detailed_score = 0.7 * sent_len_norm + 0.3 * punctuation_norm
    
    # Return detailed_score as final measure, range 0 (concise) to 1 (detailed)
    return detailed_score


def check_conciseness(output: str, source: str, value: str, target: dict) -> tuple[float, str]:
    m = measure_conciseness(output, source)
    boundaries = {"concise": (float('-inf'), 0.5599999999999999), "moderate": (0.5599999999999999, 0.7974613402061855), "detailed": (0.7974613402061855, float('inf'))}
    lo, hi = boundaries[value]
    if lo <= m <= hi:
        return 1.0, f"conciseness 충족: 측정값 {m:.3f} (목표 '{value}')."
    if m < lo:
        distance = (lo - m) if math.isfinite(lo) else 0.0
    else:
        distance = (m - hi) if math.isfinite(hi) else 0.0
    score = max(0.0, 1.0 - distance / 0.8425)
    return score, f"conciseness 위반: 측정값 {m:.3f} (목표 '{value}' 범위 [{lo}, {hi}])."

def measure_formality(text: str, source: str) -> float:
    # Define lists of formal and informal indicators
    formal_words = {'therefore', 'moreover', 'however', 'thus', 'hence', 'whereas', 'furthermore', 'nevertheless', 'consequently', 'additionally'}
    informal_words = {'lol', 'omg', 'btw', 'idk', 'u', 'ur', 'ya', 'hey', 'hi', 'cool', 'dude', 'awesome', 'gonna', 'wanna', 'ain\'t', 'kinda', 'gotta'}
    formal_punct = {'.', ';', ':'}
    informal_punct = {'!', '...'}
    
    words = re.findall(r'\b\w+\b', text.lower())
    word_count = len(words) if len(words) > 0 else 1
    
    formal_count = sum(w in formal_words for w in words)
    informal_count = sum(w in informal_words for w in words)
    
    # Count formal and informal punctuation
    formal_punct_count = sum(text.count(p) for p in formal_punct)
    informal_punct_count = sum(text.count(p) for p in informal_punct)
    
    # Average word length (longer words tend to be more formal)
    avg_word_len = sum(len(w) for w in words) / word_count
    
    # Ratio of formal to informal indicators
    formality_score = (formal_count + formal_punct_count + avg_word_len / 5) - (informal_count + informal_punct_count)
    
    # Normalize by word count to get a continuous score
    return formality_score / word_count * 10


def check_formality(output: str, source: str, value: str, target: dict) -> tuple[float, str]:
    m = measure_formality(output, source)
    boundaries = {"informal": (float('-inf'), 0.6797520661157025), "neutral": (0.6797520661157025, 0.9750000000000001), "formal": (0.9750000000000001, float('inf'))}
    lo, hi = boundaries[value]
    if lo <= m <= hi:
        return 1.0, f"formality 충족: 측정값 {m:.3f} (목표 '{value}')."
    if m < lo:
        distance = (lo - m) if math.isfinite(lo) else 0.0
    else:
        distance = (m - hi) if math.isfinite(hi) else 0.0
    score = max(0.0, 1.0 - distance / 2.6282793209876543)
    return score, f"formality 위반: 측정값 {m:.3f} (목표 '{value}' 범위 [{lo}, {hi}])."

def measure_sentence_complexity(text: str, source: str) -> float:
    sentences = re.split(r'[.!?]+', text)
    sentences = [s.strip() for s in sentences if s.strip()]
    if not sentences:
        return 0.0
    def clause_count(sentence):
        # Count commas, semicolons, colons, conjunctions as proxies for clauses
        conj = [' and ', ' or ', ' but ', ' nor ', ' yet ', ' so ', ' although ', ' because ', ' since ', ' unless ', ' while ', ' whereas ', ' though ']
        count = sentence.count(',') + sentence.count(';') + sentence.count(':')
        for c in conj:
            count += sentence.lower().count(c)
        # At least one clause per sentence
        return max(1, count + 1)
    clauses = [clause_count(s) for s in sentences]
    avg_clauses = sum(clauses)/len(clauses)
    return avg_clauses


def check_sentence_complexity(output: str, source: str, value: str, target: dict) -> tuple[float, str]:
    m = measure_sentence_complexity(output, source)
    boundaries = {"simple": (float('-inf'), 2.0), "moderate": (2.0, 3.5), "complex": (3.5, float('inf'))}
    lo, hi = boundaries[value]
    if lo <= m <= hi:
        return 1.0, f"sentence_complexity 충족: 측정값 {m:.3f} (목표 '{value}')."
    if m < lo:
        distance = (lo - m) if math.isfinite(lo) else 0.0
    else:
        distance = (m - hi) if math.isfinite(hi) else 0.0
    score = max(0.0, 1.0 - distance / 5.0)
    return score, f"sentence_complexity 위반: 측정값 {m:.3f} (목표 '{value}' 범위 [{lo}, {hi}])."

def measure_focus_on_entities(text: str, source: str) -> float:
    # Define simple patterns for named entities: capitalized words sequences (people, orgs, places)
    # This is a heuristic: sequences of 1-3 capitalized words (excluding sentence start)
    # Count named entities and total words, return ratio scaled to [0,1]
    words = re.findall(r'\b\w+\b', text)
    if not words:
        return 0.0
    named_entities = 0
    i = 0
    n = len(words)
    while i < n:
        # Check if word is capitalized and not at sentence start (heuristic)
        w = words[i]
        if w[0].isupper():
            # Check next 1 or 2 words if also capitalized to form multi-word entity
            length = 1
            for j in range(i+1, min(i+3, n)):
                if words[j][0].isupper():
                    length += 1
                else:
                    break
            named_entities += 1
            i += length
        else:
            i += 1
    # Ratio of named entities to total words (scaled)
    ratio = named_entities / len(words)
    # Return ratio clipped to [0,1]
    return min(max(ratio, 0.0), 1.0)


def check_focus_on_entities(output: str, source: str, value: str, target: dict) -> tuple[float, str]:
    m = measure_focus_on_entities(output, source)
    boundaries = {"general": (float('-inf'), 0.09090909090909091), "mixed": (0.09090909090909091, 0.14285714285714285), "entity-focused": (0.14285714285714285, float('inf'))}
    lo, hi = boundaries[value]
    if lo <= m <= hi:
        return 1.0, f"focus_on_entities 충족: 측정값 {m:.3f} (목표 '{value}')."
    if m < lo:
        distance = (lo - m) if math.isfinite(lo) else 0.0
    else:
        distance = (m - hi) if math.isfinite(hi) else 0.0
    score = max(0.0, 1.0 - distance / 0.15826330532212884)
    return score, f"focus_on_entities 위반: 측정값 {m:.3f} (목표 '{value}' 범위 [{lo}, {hi}])."

