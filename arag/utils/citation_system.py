import re
import ssl
import string

import nltk
from nltk.corpus import stopwords
from nltk.stem import PorterStemmer
from nltk.tokenize import sent_tokenize, word_tokenize
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

nltk.download("stopwords")
nltk.download("punkt_tab")


class CitationSystem:
    def __init__(self):
        self.stemmer = PorterStemmer()
        self.stop_words = set(stopwords.words("english"))
        self.vectorizer = TfidfVectorizer(min_df=1, stop_words="english")

    def parse_chunks_with_position(self, chunks_text):
        """
        Parse chunks from text with page markers like {123}-----
        This version preserves the position information of each segment
        relative to page markers for more precise citation
        """
        # First, prepare a structure that keeps track of page boundaries
        page_pattern = r"\{(\d+)\}-+"
        page_matches = list(re.finditer(page_pattern, chunks_text))

        if not page_matches:
            return []

        page_boundaries = []
        for i, match in enumerate(page_matches):
            # Convert to int, add 1, then back to string to adjust for 0-based indexing
            page_number = str(int(match.group(1)) + 1)
            start_pos = match.end()

            # End position is the start of next page marker or end of text
            end_pos = len(chunks_text)
            if i < len(page_matches) - 1:
                end_pos = page_matches[i + 1].start()

            page_boundaries.append(
                {
                    "page_number": page_number,
                    "start_pos": start_pos,
                    "end_pos": end_pos,
                    "content": chunks_text[start_pos:end_pos].strip(),
                }
            )

        return page_boundaries

    def extract_segments_with_position(self, page_boundaries):
        """
        Extract segments from content while keeping track of their position
        and the page they belong to
        """
        all_segments = []

        for page in page_boundaries:
            content = page["content"]
            page_number = page["page_number"]

            # Track position offsets for each segment
            current_pos = 0

            # Extract numbered items
            numbered_pattern = r"\d+\.\s+[^\.]+\.?"
            for match in re.finditer(numbered_pattern, content):
                segment = match.group(0)
                position = match.start() + page["start_pos"]

                all_segments.append(
                    {
                        "original": segment,
                        "cleaned": self.clean_text(segment),
                        "page_number": page_number,
                        "position": position,
                    }
                )

            # Extract bullet points
            bullet_pattern = r"[-•]\s+[^\.]+\.?"
            for match in re.finditer(bullet_pattern, content):
                segment = match.group(0)
                position = match.start() + page["start_pos"]

                all_segments.append(
                    {
                        "original": segment,
                        "cleaned": self.clean_text(segment),
                        "page_number": page_number,
                        "position": position,
                    }
                )

            # Extract sentences (trickier with positions)
            # Create a version of content without bullets and numbered items
            temp_content = content
            for pattern in [numbered_pattern, bullet_pattern]:
                temp_content = re.sub(pattern, "", temp_content)

            sentences = sent_tokenize(temp_content)

            # For sentences, we estimate positions
            curr_pos = 0
            for sentence in sentences:
                if len(sentence.strip()) < 10:  # Skip very short sentences
                    continue

                # Find position in original content
                sent_pos = content.find(sentence, curr_pos)
                if sent_pos != -1:
                    curr_pos = sent_pos + len(sentence)
                    position = sent_pos + page["start_pos"]

                    all_segments.append(
                        {
                            "original": sentence,
                            "cleaned": self.clean_text(sentence),
                            "page_number": page_number,
                            "position": position,
                        }
                    )

        # Filter out segments that are too short after cleaning
        filtered_segments = [s for s in all_segments if len(s["cleaned"].split()) >= 3]

        # Sort by position (important for finding first occurrences)
        return sorted(filtered_segments, key=lambda x: x["position"])

    def clean_text(self, text):
        """Clean text by removing markup, punctuation, etc."""
        # Remove bold/italic markers and references
        text = re.sub(r"\*\*|\*", "", text)
        text = re.sub(r"\(\d+\)", "", text)

        # Remove leading bullets/numbers/headings
        text = re.sub(r"^[-•#\d\s\.]+", "", text)

        # Normalize whitespace
        text = re.sub(r"\s+", " ", text)

        return text.strip()

    def preprocess_for_matching(self, text):
        """Preprocess text for semantic matching"""
        # Tokenize and convert to lowercase
        words = word_tokenize(text.lower())

        # Remove stopwords and punctuation
        filtered_words = [word for word in words if word not in self.stop_words and word not in string.punctuation]

        # Stem words
        stemmed_words = [self.stemmer.stem(word) for word in filtered_words]

        return " ".join(stemmed_words)

    def calculate_similarity(self, text1, text2):
        """Calculate semantic similarity between two texts"""
        # For very short texts, fall back to word overlap
        if len(text1.split()) < 3 or len(text2.split()) < 3:
            words1 = set(text1.split())
            words2 = set(text2.split())
            if not words1 or not words2:
                return 0
            return len(words1.intersection(words2)) / max(len(words1), len(words2))

        # For longer texts, use TF-IDF and cosine similarity
        try:
            tfidf_matrix = self.vectorizer.fit_transform([text1, text2])
            return cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
        except:
            # Fallback if vectorizer fails
            words1 = set(text1.split())
            words2 = set(text2.split())
            if not words1 or not words2:
                return 0
            return len(words1.intersection(words2)) / max(len(words1), len(words2))

    def find_matches(self, answer, segments, threshold=0.3):
        """Find matching segments between answer and segments"""
        all_matches = []

        # Custom tokenization for enumerated lists
        # This will identify sentences while preserving enumeration
        answer_parts = self.custom_tokenize(answer)
        preprocessed_parts = [self.preprocess_for_matching(p["text"]) for p in answer_parts]

        # Process each segment
        for segment in segments:
            preprocessed_segment = self.preprocess_for_matching(segment["cleaned"])

            # Check for matches with each part of the answer
            for i, part in enumerate(answer_parts):
                # Skip if this is an enumeration marker
                if part["is_enumeration"]:
                    continue

                similarity = self.calculate_similarity(preprocessed_segment, preprocessed_parts[i])

                if similarity > threshold:
                    # Check if this segment already exists in all_matches
                    match_exists = False
                    for match in all_matches:
                        if match["page_number"] == segment["page_number"] and match["content"] == segment["original"]:
                            if i not in match["part_indices"]:
                                match["part_indices"].append(i)
                            match_exists = True
                            break

                    if not match_exists:
                        all_matches.append(
                            {
                                "page_number": segment["page_number"],
                                "content": segment["original"],
                                "cleaned_content": segment["cleaned"],
                                "match_score": similarity,
                                "position": segment["position"],
                                "part_indices": [i],
                            }
                        )

        # Sort by position (earliest first)
        return sorted(all_matches, key=lambda x: x["position"])

    def custom_tokenize(self, text):
        """
        Custom tokenizer that respects enumeration markers
        Returns a list of dictionaries with:
        - text: The text content
        - is_enumeration: Boolean indicating if this is an enumeration marker
        """
        # First, identify enumeration markers
        enum_pattern = r"(?:^|\n|\. )(\d+\.\s+)"

        # Split by enumeration markers and track their positions
        parts = []
        last_end = 0

        for match in re.finditer(enum_pattern, text):
            enum_start = match.start(1)  # Start of the enumeration marker
            enum_end = match.end(1)  # End of the enumeration marker

            # Add text before the enumeration marker
            if enum_start > last_end:
                prev_text = text[last_end:enum_start].strip()
                if prev_text:
                    parts.append({"text": prev_text, "is_enumeration": False})

            # Add the enumeration marker
            parts.append({"text": text[enum_start:enum_end], "is_enumeration": True})

            last_end = enum_end

        # Add any remaining text
        if last_end < len(text):
            parts.append({"text": text[last_end:], "is_enumeration": False})

        # If no enumerations were found, fall back to sentence tokenization
        if not parts or (len(parts) == 1 and not parts[0]["is_enumeration"]):
            sentences = sent_tokenize(text)
            parts = [{"text": s, "is_enumeration": False} for s in sentences]

        return parts

    def assign_citation_numbers(self, matches):
        """Assign unique citation numbers to each page (one citation per page)"""
        page_to_citation = {}
        next_citation = 1

        # Process matches in order of position (crucial for first occurrence)
        sorted_matches = sorted(matches, key=lambda x: x["position"])

        for match in sorted_matches:
            page_number = match["page_number"]
            if page_number not in page_to_citation:
                page_to_citation[page_number] = next_citation
                next_citation += 1

        return page_to_citation

    def add_citations(self, answer, matches, citation_map):
        """
        Add citations to the answer, respecting enumeration markers and placing
        citations only at the end of paragraphs or sentences, not after commas.
        """
        # First, identify paragraph boundaries
        paragraphs = re.split(r"\n\s*\n", answer)

        # Process each paragraph separately
        cited_paragraphs = []

        for paragraph in paragraphs:
            # Use custom tokenization for this paragraph
            paragraph_parts = self.custom_tokenize(paragraph)

            # Track which parts are enumeration markers
            enumeration_indices = [i for i, part in enumerate(paragraph_parts) if part["is_enumeration"]]

            # Find sentence boundaries within non-enumeration parts
            sentence_boundaries = []
            for i, part in enumerate(paragraph_parts):
                if part["is_enumeration"]:
                    continue

                # Find sentence endings in this part (periods, exclamation marks, question marks)
                text = part["text"]
                for match in re.finditer(r"[.!?](?=\s|$)", text):
                    sentence_boundaries.append((i, match.end()))

            # Find page numbers for this paragraph
            paragraph_page_numbers = set()
            for match in matches:
                for part_idx in match["part_indices"]:
                    if part_idx < len(paragraph_parts):
                        paragraph_page_numbers.add(match["page_number"])

            # If no matches for this paragraph, keep it unchanged
            if not paragraph_page_numbers:
                cited_paragraphs.append(paragraph)
                continue

            # Choose the earliest page number for this paragraph
            sorted_matches_for_paragraph = sorted(
                [m for m in matches if m["page_number"] in paragraph_page_numbers], key=lambda x: x["position"]
            )
            if not sorted_matches_for_paragraph:
                cited_paragraphs.append(paragraph)
                continue

            earliest_match = sorted_matches_for_paragraph[0]
            page_number = earliest_match["page_number"]
            citation_number = citation_map[page_number]

            # Add citation at the end of the paragraph
            citation_text = f" [{citation_number}]({page_number})"

            # Check if paragraph already has a citation
            if re.search(r"\[\d+\]\(\d+\)$", paragraph.strip()):
                cited_paragraphs.append(paragraph)
            else:
                cited_paragraphs.append(paragraph + citation_text)

        # Join paragraphs back together
        result = "\n\n".join(cited_paragraphs)

        return result

    def process_citations(self, answer, chunks_text, threshold=0.5):
        """Main function to process citations"""
        # Parse chunks with position info
        page_boundaries = self.parse_chunks_with_position(chunks_text)

        # Extract segments with position info
        segments = self.extract_segments_with_position(page_boundaries)

        # Find matches
        matches = self.find_matches(answer, segments, threshold)

        # Assign citation numbers
        citation_map = self.assign_citation_numbers(matches)

        # Add citations
        return self.add_citations(answer, matches, citation_map)