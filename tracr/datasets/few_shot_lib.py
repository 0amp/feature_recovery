# Copyright 2022 DeepMind Technologies Limited. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================
"""RASP programs only using the subset of RASP supported by the compiler."""

from typing import List, Sequence

from tracr.rasp import rasp
from tracr.compiler.lib import *

### Programs that work only under non-causal evaluation.

def make_token_position_encoding() -> rasp.SOp:
    """
    Encodes each token's position relative to the start and end of the sequence.

    Example usage:
      position_encoding = make_token_position_encoding()
      position_encoding(["a", "b", "c", "d"])
      >> [(0, 3), (1, 2), (2, 1), (3, 0)]

    Returns:
      A SOp that maps each token in the input sequence to a tuple representing 
      its position index from the start and its reverse index from the end.
    """
    position_encoding = rasp.SequenceMap(
        lambda start_idx, end_idx: (start_idx, end_idx),
        rasp.indices, length - rasp.indices - 1).named("position_encoding")
    return position_encoding

position_encoding = make_token_position_encoding()

def make_palindrome_detection(sop: rasp.SOp) -> rasp.SOp:
    """
    Detects palindromes in a sequence of characters.

    Example usage:
      palindrome_detect = make_palindrome_detection(rasp.tokens)
      palindrome_detect("racecar")
      >> [False, False, False, True, False, False, False]

    Args:
      sop: SOp representing the sequence to analyze.

    Returns:
      A SOp that maps an input sequence to a boolean sequence, where True 
      indicates a palindrome at that position.
    """
    reversed_sop = make_reverse(sop)
    palindrome_sop = rasp.SequenceMap(
        lambda x, y: x == y, sop, reversed_sop).named("palindrome_detection")
    return palindrome_sop

palindrome_detection = make_palindrome_detection(rasp.tokens)

def make_nested_pattern_extraction(sop: rasp.SOp, open_token: str, close_token: str) -> rasp.SOp:
    """
    Extracts nested patterns like parentheses or HTML tags from a sequence.

    Example usage:
      nested_pattern = make_nested_pattern_extraction(rasp.tokens, "(", ")")
      nested_pattern("(a(b)c)(d)")
      >> [((True, False), (False, False)), ...]

    Args:
      sop: SOp representing the sequence to analyze.
      open_token: The token representing the start of a nested pattern.
      close_token: The token representing the end of a nested pattern.

    Returns:
      A SOp that maps an input sequence to a sequence of tuples, each indicating 
      the start and end of a nested pattern.
    """
    open_detector = detect_pattern(sop, [open_token])
    close_detector = detect_pattern(sop, [close_token])
    nested_pattern_sop = rasp.SequenceMap(
        lambda x, y: (x, y), open_detector, close_detector).named("nested_pattern_extraction")
    return nested_pattern_sop

nested_pattern_extraction = make_nested_pattern_extraction(rasp.tokens, "(", ")")

def make_sequential_duplicate_removal(sop: rasp.SOp) -> rasp.SOp:
    """
    Removes consecutive duplicate tokens from a sequence.

    Example usage:
      duplicate_remove = make_sequential_duplicate_removal(rasp.tokens)
      duplicate_remove("aabbcc")
      >> ['a', None, 'b', None, 'c', None]

    Args:
      sop: SOp representing the sequence to process.

    Returns:
      A SOp that maps an input sequence to another sequence where immediate 
      duplicate occurrences of any token are removed.
    """
    shifted_sop = shift_by(1, sop)
    duplicate_removal_sop = rasp.SequenceMap(
        lambda x, y: x if x != y else None, sop, shifted_sop).named("sequential_duplicate_removal")
    return duplicate_removal_sop

sequential_duplicate_removal = make_sequential_duplicate_removal(rasp.tokens)

def make_token_counter(sop: rasp.SOp, target_token: rasp.Value) -> rasp.SOp:
    """
    Counts occurrences of a specific token in a sequence.

    Example usage:
      token_count = make_token_counter(rasp.tokens, "a")
      token_count("banana")
      >> [1, 1, 1, 1, 1, 1]

    Args:
      sop: SOp representing the sequence to analyze.
      target_token: The token to count occurrences of.

    Returns:
      A SOp that maps an input sequence to a sequence where each element is 
      the count of the target token up to that position.
    """
    token_equals = rasp.Map(lambda x: x == target_token, sop).named("token_equals")
    pre_agg = rasp.Select(rasp.indices, rasp.indices, rasp.Comparison.LEQ).named("pre_agg")
    count_sop = rasp.numerical(rasp.Aggregate(
        pre_agg,
        token_equals, default=0)).named("count_sop")
    count_sop = rasp.Map(lambda x: x if x is not None else 0, count_sop).named("count_sop")
    return count_sop

token_counter_a = make_token_counter(rasp.tokens, "a")

def make_unique_token_extractor(sop: rasp.SOp) -> rasp.SOp:
    """
    Extracts unique tokens from a sequence.

    Example usage:
      unique_tokens = make_unique_token_extractor(rasp.tokens)
      unique_tokens("banana")
      >> ['b', 'a', 'n', None, None, None]

    Args:
      sop: SOp representing the sequence to process.

    Returns:
      A SOp that maps an input sequence to another sequence containing only 
      the first occurrence of each unique token, with the rest as None.
    """
    is_first_occurrence = rasp.Aggregate(
        rasp.Select(rasp.indices, rasp.indices, rasp.Comparison.EQ),
        sop, default=None).named("is_first_occurrence")
    return is_first_occurrence

unique_token_extractor = make_unique_token_extractor(rasp.tokens)

def make_token_sorting_by_length(sop: rasp.SOp) -> rasp.SOp:
    """
    Sorts tokens in a sequence by their length.

    Example usage:
      token_sort_len = make_token_sorting_by_length(rasp.tokens)
      token_sort_len(["word", "a", "is", "sequence"])
      >> ["a", "is", "word", "sequence"]
    """
    token_length = rasp.Map(lambda x: len(x), sop).named("token_length")
    sorted_tokens = make_sort(sop, token_length, max_seq_len=10, min_key=1)
    return sorted_tokens

token_sorting_by_length = make_token_sorting_by_length(rasp.tokens)

def make_token_pairing(sop: rasp.SOp) -> rasp.SOp:
    """
    Pairs adjacent tokens in a sequence.

    Example usage:
      token_pair = make_token_pairing(rasp.tokens)
      token_pair(["a", "b", "c", "d"])
      >> [("a", "b"), ("b", "c"), ("c", "d"), None]
    """
    shifted_sop = shift_by(1, sop)
    token_pair = rasp.SequenceMap(lambda x, y: (x, y) if y is not None else None, sop, shifted_sop)
    return token_pair

token_pairing = make_token_pairing(rasp.tokens)


def make_leading_token_identification(sop: rasp.SOp) -> rasp.SOp:
    """
    Identifies the first occurrence of each token in a sequence.

    Example usage:
      leading_token_id = make_leading_token_identification(rasp.tokens)
      leading_token_id(["x", "y", "x", "z", "y"])
      >> [True, True, False, True, False]
    """
    first_occurrence = rasp.Aggregate(
        rasp.Select(rasp.indices, rasp.indices, rasp.Comparison.EQ),
        sop, default=None).named("first_occurrence")
    return first_occurrence

leading_token_identification = make_leading_token_identification(rasp.tokens)

def make_token_frequency_normalization(sop: rasp.SOp) -> rasp.SOp:
    """
    Normalizes token frequencies in a sequence to a range between 0 and 1.

    Example usage:
      token_freq_norm = make_token_frequency_normalization(rasp.tokens)
      token_freq_norm(["a", "a", "b", "c", "c", "c"])
      >> [0.33, 0.33, 0.16, 0.5, 0.5, 0.5]
    """
    hist = make_hist()
    normalized_freq = rasp.Map(lambda x: x / length, hist)
    return normalized_freq

token_frequency_normalization = make_token_frequency_normalization(rasp.tokens)

def make_token_cascade(sop: rasp.SOp) -> rasp.SOp:
    """
    Creates a cascading effect by repeating each token in sequence incrementally.

    Example usage:
      token_cascade = make_token_cascade(rasp.tokens)
      token_cascade(["a", "b", "c"])
      >> ["a", "bb", "ccc"]
    """
    cascade_sop = rasp.SequenceMap(lambda x, i: x * (i + 1), sop, rasp.indices)
    return cascade_sop

token_cascade = make_token_cascade(rasp.tokens)

def make_token_sandwich(sop: rasp.SOp, filler: rasp.Value) -> rasp.SOp:
    """
    Places a filler token between each pair of tokens in the sequence.

    Example usage:
      token_sandwich = make_token_sandwich(rasp.tokens, "-")
      token_sandwich(["a", "b", "c"])
      >> ["a", "-", "b", "-", "c"]
    """
    filler_sop = rasp.Full(filler)
    alternate_sop = rasp.SequenceMap(lambda x, y: (x, filler) if y is not None else x, sop, filler_sop)
    return alternate_sop

token_sandwich = make_token_sandwich(rasp.tokens, "-")

def make_token_mirroring(sop: rasp.SOp) -> rasp.SOp:
    """
    Mirrors each token in the sequence around its central axis.

    Example usage:
      token_mirror = make_token_mirroring(rasp.tokens)
      token_mirror(["abc", "def", "ghi"])
      >> ["cba", "fed", "ihg"]
    """
    mirrored_sop = rasp.Map(lambda x: x[::-1] if x is not None else None, sop)
    return mirrored_sop

token_mirroring = make_token_mirroring(rasp.tokens)

def make_token_abbreviation(sop: rasp.SOp) -> rasp.SOp:
    """
    Creates abbreviations for each token in the sequence.

    Example usage:
      token_abbreviation = make_token_abbreviation(rasp.tokens)
      token_abbreviation(["international", "business", "machines"])
      >> ["int", "bus", "mac"]
    """
    abbreviation = rasp.Map(lambda x: x[:3] if len(x) > 3 else x, sop)
    return abbreviation

token_abbreviation = make_token_abbreviation(rasp.tokens)

def make_numeric_range_tagging(sop: rasp.SOp, lower_bound: int, upper_bound: int) -> rasp.SOp:
    """
    Tags numeric tokens in a sequence based on whether they fall within a given range.

    Example usage:
      range_tagging = make_numeric_range_tagging(rasp.tokens, 10, 20)
      range_tagging(["5", "15", "25", "20"])
      >> [False, True, False, True]
    """
    range_tagging = rasp.Map(
        lambda x: lower_bound <= int(x) <= upper_bound if x.isdigit() else False, sop)
    return range_tagging

numeric_range_tagging = make_numeric_range_tagging(rasp.tokens, 10, 20)

def make_token_anagram_identifier(sop: rasp.SOp, target: str) -> rasp.SOp:
    """
    Identifies if tokens in the sequence are anagrams of a given target word.

    Example usage:
      anagram_identifier = make_token_anagram_identifier(rasp.tokens, "listen")
      anagram_identifier(["enlist", "google", "inlets", "banana"])
      >> [True, False, True, False]
    """
    sorted_target = sorted(target)
    anagram_identifier = rasp.Map(
        lambda x: sorted(x) == sorted_target, sop)
    return anagram_identifier

token_anagram_identifier = make_token_anagram_identifier(rasp.tokens, "listen")

def make_token_boundary_detector(sop: rasp.SOp) -> rasp.SOp:
    """
    Detects the boundaries between different types of tokens in a sequence.

    Example usage:
      token_boundary = make_token_boundary_detector(rasp.tokens)
      token_boundary(["apple", "banana", "apple", "orange"])
      >> [False, True, False, True]
    """
    previous_token = shift_by(1, sop)
    boundary_detector = rasp.SequenceMap(
        lambda x, y: x != y, sop, previous_token)
    return boundary_detector

token_boundary_detector = make_token_boundary_detector(rasp.tokens)

def make_token_length_parity_checker(sop: rasp.SOp) -> rasp.SOp:
    """
    Checks if each token's length is odd or even.

    Example usage:
      length_parity = make_token_length_parity_checker(rasp.tokens)
      length_parity(["hello", "worlds", "!", "2022"])
      >> [False, True, False, True]
    """
    length_parity_checker = rasp.Map(lambda x: len(x) % 2 == 0, sop)
    return length_parity_checker

token_length_parity_checker = make_token_length_parity_checker(rasp.tokens)

def make_vowel_consonant_ratio(sop: rasp.SOp) -> rasp.SOp:
    """
    Calculates the ratio of vowels to consonants in each token. Deal with 0 denominator by 
    returning infinity.

    Example usage:
      vowel_consonant_ratio = make_vowel_consonant_ratio(rasp.tokens)
      vowel_consonant_ratio(["apple", "sky", "aeiou"])
      >> [2/3, 0/3, inf]
    """
    def calc_ratio(word):
        vowels = sum(c in 'aeiou' for c in word.lower())
        consonants = len(word) - vowels
        return vowels / consonants if consonants != 0 else float('inf')

    ratio_calculator = rasp.Map(calc_ratio, sop)
    return ratio_calculator

vowel_consonant_ratio = make_vowel_consonant_ratio(rasp.tokens)

def make_token_capitalization_alternator(sop: rasp.SOp) -> rasp.SOp:
    """
    Alternates capitalization of each character in tokens.

    Example usage:
      capitalization_alternator = make_token_capitalization_alternator(rasp.tokens)
      capitalization_alternator(["hello", "world"])
      >> ["HeLlO", "WoRlD"]
    """
    def alternate_capitalization(word):
        return ''.join(c.upper() if i % 2 == 0 else c.lower() for i, c in enumerate(word))

    alternator = rasp.Map(alternate_capitalization, sop)
    return alternator

token_capitalization_alternator = make_token_capitalization_alternator(rasp.tokens)

def make_numeric_token_range_filter(sop: rasp.SOp, min_val: int, max_val: int) -> rasp.SOp:
    """
    Filters numeric tokens in a sequence based on a specified range.

    Example usage:
      range_filter = make_numeric_token_range_filter(rasp.tokens, 10, 50)
      range_filter(["5", "20", "60", "30"])
      >> [None, "20", None, "30"]
    """
    def in_range(token):
        return token if token.isdigit() and min_val <= int(token) <= max_val else None

    range_filter = rasp.Map(in_range, sop)
    return range_filter

numeric_token_range_filter = make_numeric_token_range_filter(rasp.tokens, 10, 50)

def make_token_reversal_with_exclusion(sop: rasp.SOp, exclude: str) -> rasp.SOp:
    """
    Reverses each token in the sequence except for specified exclusions.

    Example usage:
      token_reversal = make_token_reversal_with_exclusion(rasp.tokens, "nochange")
      token_reversal(["reverse", "this", "nochange"])
      >> ["esrever", "siht", "nochange"]
    """
    reversal = rasp.Map(lambda x: x[::-1] if x != exclude else x, sop)
    return reversal

token_reversal_with_exclusion = make_token_reversal_with_exclusion(rasp.tokens, "nochange")

def make_token_frequency_deviation(sop: rasp.SOp) -> rasp.SOp:
    """
    Calculates the deviation of each token's frequency from the average frequency in the sequence.

    Example usage:
      frequency_deviation = make_token_frequency_deviation(rasp.tokens)
      frequency_deviation(["a", "b", "a", "c", "a", "b"])
      >> [0.33, -0.33, 0.33, -0.66, 0.33, -0.33]
    """
    hist = make_hist()
    average_freq = rasp.Aggregate(
        rasp.Select(rasp.indices, rasp.indices, rasp.Comparison.TRUE),
        rasp.numerical(hist), default=0) / length
    freq_deviation = rasp.Map(lambda x: x - average_freq, hist)
    return freq_deviation

token_frequency_deviation = make_token_frequency_deviation(rasp.tokens)


def make_sequential_token_distance_measurement(sop: rasp.SOp) -> rasp.SOp:
    """
    Measures the distance between sequential tokens in terms of the number of tokens in between.

    Example usage:
      token_distance = make_sequential_token_distance_measurement(rasp.tokens)
      token_distance(["a", "b", "c", "a", "d"])
      >> [3, 3, 3, 0, 3]
    """
    prev_indices = shift_by(1, rasp.indices)
    token_distance = rasp.SequenceMap(lambda x, y: abs(x - y) if None not in [x, y] else None, rasp.indices, prev_indices)
    return token_distance

sequential_token_distance_measurement = make_sequential_token_distance_measurement(rasp.tokens)

def make_emoji_sentiment_classifier(sop: rasp.SOp) -> rasp.SOp:
    """
    Classifies each token as 'positive', 'negative', or 'neutral' based on emojis.

    Example usage:
      emoji_sentiment = make_emoji_sentiment_classifier(rasp.tokens)
      emoji_sentiment(["😊", "😢", "📘"])
      >> ["positive", "negative", "neutral"]
    """
    # Define mapping for emoji sentiment classification
    emoji_sentiments = {"😊": "positive", "😢": "negative", "📘": "neutral"}
    classify_sentiment = rasp.Map(lambda x: emoji_sentiments.get(x, "neutral"), sop)
    return classify_sentiment

emoji_sentiment_classifier = make_emoji_sentiment_classifier(rasp.tokens)

def make_palindrome_word_spotter(sop: rasp.SOp) -> rasp.SOp:
    """
    Spots palindrome words in a sequence.

    Example usage:
      palindrome_spotter = make_palindrome_word_spotter(rasp.tokens)
      palindrome_spotter(["racecar", "hello", "noon"])
      >> ["racecar", None, "noon"]
    """
    is_palindrome = rasp.Map(lambda x: x if x == x[::-1] else None, sop)
    return is_palindrome

palindrome_word_spotter = make_palindrome_word_spotter(rasp.tokens)

def make_spam_message_detector(sop: rasp.SOp) -> rasp.SOp:
    """
    Detects spam messages based on keyword frequency.

    Example usage:
      spam_detector = make_spam_message_detector(rasp.tokens)
      spam_detector(["free", "offer", "click", "now"])
      >> "spam"
    """
    spam_keywords = {"free", "offer", "click", "now"}
    keyword_count = rasp.Map(lambda x: sum(x == keyword for keyword in spam_keywords), sop)
    is_spam = rasp.Map(lambda x: "spam" if x > 0 else "not spam", keyword_count)
    return is_spam

spam_message_detector = make_spam_message_detector(rasp.tokens)

def make_secret_code_decoder(sop: rasp.SOp) -> rasp.SOp:
    """
    Decodes a secret code by shifting each character a certain number of places in the alphabet.

    Example usage:
      code_decoder = make_secret_code_decoder(rasp.tokens)
      code_decoder(["uryyb", "jbeyq"], -13)  # Rot13 cipher
      >> ["hello", "world"]
    """
    def shift_char(c, shift):
        if c.isalpha():
            shifted = ord(c) + shift
            if c.islower():
                return chr((shifted - ord('a')) % 26 + ord('a'))
            else:
                return chr((shifted - ord('A')) % 26 + ord('A'))
        return c

    def decode(token, shift):
        return ''.join(shift_char(c, shift) for c in token)

    shift_value = rasp.Full(-13)  # Example: Rot13 cipher
    decoded_message = rasp.SequenceMap(decode, sop, shift_value)
    return decoded_message

secret_code_decoder = make_secret_code_decoder(rasp.tokens)

def make_lexical_density_calculator(sop: rasp.SOp) -> rasp.SOp:
    """
    Calculates the lexical density of a text (unique words to total words ratio).

    Example usage:
      lexical_density = make_lexical_density_calculator(rasp.tokens)
      lexical_density(["the", "quick", "brown", "fox"])
      >> 0.75
    """
    unique_words = make_unique_token_extractor(sop)
    total_words = rasp.LengthType()
    unique_word_count = rasp.SelectorWidth(rasp.Select(unique_words, unique_words, rasp.Comparison.TRUE))
    # note map only works for one input, so we have to use Select if we want the lambda x,y
    temp = rasp.SequenceMap(lambda x, y: x / y, unique_word_count, total_words)
    lexical_density = rasp.Map(lambda x: x if x is not None else 0, temp)

    return lexical_density

lexical_density_calculator = make_lexical_density_calculator(rasp.tokens)

def make_word_count_by_length(sop: rasp.SOp) -> rasp.SOp:
    """
    Counts the number of words in a sequence based on their length.

    Example usage:
      word_count = make_word_count_by_length(rasp.tokens)
      word_count(["apple", "pear", "banana"])
      >> {5: 2, 4: 1}
    """
    word_length = rasp.Map(lambda x: len(x), sop)
    length_selector = rasp.Select(word_length, word_length, rasp.Comparison.EQ)
    word_count = rasp.Aggregate(length_selector, word_length, default=None)
    return word_count

word_count_by_length = make_word_count_by_length(rasp.tokens)

def make_token_symmetry_checker(sop: rasp.SOp) -> rasp.SOp:
    """
    Checks if each token is symmetric around its center.

    Example usage:
      symmetry_checker = make_token_symmetry_checker(rasp.tokens)
      symmetry_checker(["radar", "apple", "rotor", "data"])
      >> [True, False, True, False]
    """
    half_length = rasp.Map(lambda x: len(x) // 2, sop)
    first_half = shift_by(half_length, sop)
    second_half = rasp.SequenceMap(lambda x, y: x[:y] == x[:-y-1:-1], sop, half_length)
    symmetry_checker = rasp.SequenceMap(lambda x, y: x if y else None, sop, second_half)
    return symmetry_checker

token_symmetry_checker = make_token_symmetry_checker(rasp.tokens)

def make_sequential_gap_filler(sop: rasp.SOp, filler: str) -> rasp.SOp:
    """
    Fills gaps between tokens with a specified filler.

    Example usage:
      gap_filler = make_sequential_gap_filler(rasp.tokens, "-")
      gap_filler(["word1", None, "word3"])
      >> ["word1", "-", "word3"]
    """
    next_token = shift_by(-1, sop)
    gap_filler = rasp.SequenceMap(lambda x, y: filler if x is None and y is not None else x, sop, next_token)
    return gap_filler

sequential_gap_filler = make_sequential_gap_filler(rasp.tokens, "-")

def make_token_oscillation_detector(sop: rasp.SOp) -> rasp.SOp:
    """
    Detects oscillation patterns in a numeric sequence.

    Example usage:
      oscillation_detector = make_token_oscillation_detector(rasp.tokens)
      oscillation_detector([1, 3, 1, 3, 1])
      >> [True, True, True, True, True]
    """
    prev_token = shift_by(1, sop)
    next_token = shift_by(-1, sop)
    oscillation_detector = rasp.SequenceMap(lambda x, y: y > x, prev_token, sop)
    oscillation_detector = rasp.SequenceMap(lambda x, y: y > x, sop, next_token)
    oscillation_detector = rasp.SequenceMap(lambda x, y: x != y, oscillation_detector, oscillation_detector)
    return oscillation_detector

token_oscillation_detector = make_token_oscillation_detector(rasp.tokens)

def make_token_rotation_identifier(sop: rasp.SOp, rotation: int) -> rasp.SOp:
    """
    Identifies if tokens are rotations of each other by a specified number.

    Example usage:
      rotation_identifier = make_token_rotation_identifier(rasp.tokens, 2)
      rotation_identifier(["hello", "llohe", "lohel"])
      >> [True, True, True]
    """
    rotated_token = shift_by(rotation, sop)
    rotation_identifier = rasp.SequenceMap(lambda x, y: x == y, sop, rotated_token)
    return rotation_identifier

token_rotation_identifier = make_token_rotation_identifier(rasp.tokens, 2)

def make_token_alternation_checker(sop: rasp.SOp) -> rasp.SOp:
    """
    Checks if tokens alternate between two types.

    Example usage:
      alternation_checker = make_token_alternation_checker(rasp.tokens)
      alternation_checker(["cat", "dog", "cat", "dog"])
      >> [True, True, True, True]
    """
    prev_token = shift_by(1, sop)
    next_token = shift_by(-1, sop)

    alternation_checker = rasp.SequenceMap(lambda x, y: x != y, prev_token, sop)
    alternation_checker = rasp.SequenceMap(lambda x, y: x != y, sop, next_token)
    alternation_checker = rasp.SequenceMap(lambda x, y: x == y, alternation_checker, alternation_checker)

    return alternation_checker

token_alternation_checker = make_token_alternation_checker(rasp.tokens)

def make_token_trend_analysis(sop: rasp.SOp) -> rasp.SOp:
    """
    Analyzes the trend (increasing, decreasing, constant) of numeric tokens.

    Example usage:
      trend_analysis = make_token_trend_analysis(rasp.tokens)
      trend_analysis([1, 2, 3, 3, 2, 1])
      >> ["increasing", "increasing", "constant", "decreasing", "decreasing"]
    """
    prev_token = shift_by(1, sop)
    next_token = shift_by(-1, sop)
    first_part = rasp.SequenceMap(lambda x, y: "increasing" if y > x else ("decreasing" if y < x else "constant"), prev_token, sop)
    second_part = rasp.SequenceMap(lambda x, y: "increasing" if y < x else ("decreasing" if y > x else "constant"), sop, next_token)
    trend_analysis = rasp.SequenceMap(lambda x, y: x if y == "constant" else y, first_part, second_part)

    return trend_analysis

token_trend_analysis = make_token_trend_analysis(rasp.tokens)

def make_token_frequency_classifier(sop: rasp.SOp) -> rasp.SOp:
    """
    Classifies each token based on its frequency as 'rare', 'common', or 'frequent'.

    Example usage:
      frequency_classifier = make_token_frequency_classifier(rasp.tokens)
      frequency_classifier(["a", "b", "a", "c", "a", "b"])
      >> ["frequent", "common", "frequent", "rare", "frequent", "common"]
    """
    frequency = make_hist()
    total_tokens = rasp.LengthType()
    frequency_classification = rasp.SequenceMap(
        lambda freq, total: "frequent" if freq > total / 2 else ("common" if freq > total / 4 else "rare"),
        frequency, total_tokens)
    return frequency_classification

token_frequency_classifier = make_token_frequency_classifier(rasp.tokens)

def make_token_positional_balance_analyzer(sop: rasp.SOp) -> rasp.SOp:
    """
    Analyzes whether tokens are more towards the start ('front'), end ('rear'), or balanced ('center').

    Example usage:
      balance_analyzer = make_token_positional_balance_analyzer(rasp.tokens)
      balance_analyzer(["a", "b", "c", "d", "e"])
      >> ["front", "front", "center", "rear", "rear"]
    """
    position = rasp.indices
    total_length = rasp.LengthType()
    balance = rasp.SequenceMap(
        lambda pos, length: "front" if pos < length / 3 else ("rear" if pos > 2 * length / 3 else "center"),
        position, total_length)
    return balance

token_positional_balance_analyzer = make_token_positional_balance_analyzer(rasp.tokens)  



# CAN ONLY USE BINARY NUMBERS, SO THESE DON'T WORK # 

# def make_cumulative_sum(sop: rasp.SOp) -> rasp.SOp:
#     """
#     Calculates the cumulative sum of numeric tokens in the sequence.

#     Example usage:
#       cum_sum = make_cumulative_sum(rasp.tokens)
#       cum_sum([1, 2, 3, 4])
#       >> [1, 3, 6, 10]

#     Args:
#       sop: A numeric SOp.

#     Returns:
#       A SOp that maps an input sequence of numbers to a sequence of numbers, 
#       where each number is the cumulative sum at that position.
#     """
#     # Convert the sop to a numerical form
#     sop = rasp.numerical(sop)

#     # Selector to select all previous elements including the current one
#     up_to_current_selector = rasp.Select(
#         rasp.indices, rasp.indices,
#         lambda key, query: key <= query
#     ).named("up_to_current_selector")

#     # Cumulative sum using the aggregate function
#     cumulative_sum = rasp.numerical(rasp.Aggregate(
#         up_to_current_selector, sop, default=0
#     )).named("cumulative_sum")

#     return cumulative_sum

# cumulative_sum = make_cumulative_sum(rasp.tokens)

# def make_cumulative_product(sop: rasp.SOp) -> rasp.SOp:
#     """
#     Calculates the cumulative product of numeric tokens in the sequence.

#     Example usage:
#       cum_prod = make_cumulative_product(rasp.tokens)
#       cum_prod([1, 2, 3, 4])
#       >> [1, 2, 6, 24]

#     Args:
#       sop: A numeric SOp.

#     Returns:
#       A SOp that maps an input sequence of numbers to a sequence of numbers, 
#       where each number is the cumulative product at that position.
#     """
#     sop = rasp.numerical(sop)
#     up_to_current_selector = rasp.Select(
#         rasp.indices, rasp.indices,
#         lambda key, query: key <= query
#     ).named("up_to_current_selector")

#     # Initialize the product as 1 (since the product of no numbers is 1)
#     cumulative_product = rasp.numerical(rasp.Aggregate(
#         up_to_current_selector, rasp.Map(lambda x: x if x is not None else 1, sop),
#         default=1
#     )).named("cumulative_product")

#     return cumulative_product

# cumulative_product = make_cumulative_product(rasp.tokens)

# def make_moving_average(sop: rasp.SOp, window_size: int) -> rasp.SOp:
#     """
#     Applies a moving average filter to a sequence of numbers.

#     Example usage:
#       moving_avg = make_moving_average(rasp.tokens, 3)
#       moving_avg([1, 2, 3, 4, 5])
#       >> [1, 1.5, 2, 3, 4]

#     Args:
#       sop: A numeric SOp.
#       window_size: Size of the moving window.

#     Returns:
#       A SOp that maps an input sequence of numbers to another sequence where 
#       each element is the average of its window.
#     """
#     # Ensure the window size is valid
#     if window_size < 1:
#         raise ValueError("Window size must be at least 1")

#     # Define a selector that selects the values in the moving window
#     within_window_selector = rasp.Select(
#         rasp.indices,  # Keys: indices of the input sequence
#         rasp.indices,  # Queries: indices of the input sequence
#         lambda key, query: (query <= key) & (key < query + window_size)
#     ).named("within_window_selector")

#     # Define the moving average operation using an aggregate function
#     moving_average = rasp.numerical(rasp.Aggregate(
#         within_window_selector,  # The selector defined above
#         sop,                     # The SOp whose moving average is to be computed
#         default=None             # Default value outside the moving window
#     )).named("moving_average")

#     return moving_average

# moving_average_3 = make_moving_average(rasp.tokens, 3)

# def make_moving_max(sop: rasp.SOp, window_size: int) -> rasp.SOp:
#     """
#     Applies a moving max filter to a sequence of numbers.

#     Example usage:
#       moving_max = make_moving_max(rasp.tokens, 3)
#       moving_max([1, 2, 3, 4, 5])
#       >> [1, 2, 3, 4, 5]

#     Args:
#       sop: A numeric SOp.
#       window_size: Size of the moving window.

#     Returns:
#       A SOp that maps an input sequence of numbers to another sequence where 
#       each element is the maximum of its window.
#     """
#     # Ensure the window size is valid
#     if window_size < 1:
#         raise ValueError("Window size must be at least 1")

#     # Define a selector that selects the values in the moving window
#     within_window_selector = rasp.Select(
#         rasp.indices,  # Keys: indices of the input sequence
#         rasp.indices,  # Queries: indices of the input sequence
#         lambda key, query: (query <= key) & (key < query + window_size)
#     ).named("within_window_selector")

#     # Define the moving max operation using an aggregate function
#     moving_max = rasp.numerical(rasp.Aggregate(
#         within_window_selector,  # The selector defined above
#         sop,                     # The SOp whose moving max is to be computed
#         default=None             # Default value outside the moving window
#     )).named("moving_max")

#     return moving_max

# moving_max_3 = make_moving_max(rasp.tokens, 3)