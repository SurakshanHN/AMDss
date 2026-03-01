import logging
from typing import List
from .models import KnowledgeTriplet

logger = logging.getLogger(__name__)

class KnowledgeExtractor:
    def __init__(self, use_mock: bool = True):
        self.use_mock = use_mock
        # Placeholder for vLLM / LangChain setup
    
    def extract_triplets(self, text: str, source_ref: str = None) -> List[KnowledgeTriplet]:
        """
        Extracts entities and relationships from text.
        """
        if self.use_mock:
            # Fallback mock logic...
            logger.info("Extracting triplets dynamically via fallback mock method.")
            words = [w.capitalize() for w in text.replace(".", " ").replace(",", " ").split() if len(w) > 4]
            if len(words) >= 2:
                return [
                    KnowledgeTriplet(subject=words[0], predicate="relates_to", object=words[1], source_reference=source_ref),
                    KnowledgeTriplet(subject=words[1], predicate="influences", object=words[-1], source_reference=source_ref)
                ]
            else:
                return [
                    KnowledgeTriplet(subject="Schrödinger", predicate="developed", object="Wave Equation", source_reference=source_ref)
                ]

        # Genuine AI Extraction via Local Transformers Pipeline
        logger.info(f"Running genuine HuggingFace ML Extraction for {source_ref}...")
        try:
            from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
            if not getattr(self, "nlp_model", None):
                logger.info("Loading LLM into memory (this will take a moment)...")
                self.nlp_tokenizer = AutoTokenizer.from_pretrained("google/flan-t5-small")
                self.nlp_model = AutoModelForSeq2SeqLM.from_pretrained("google/flan-t5-small")
            
            prompt = (
                f"Task: Extract a semantic triplet from the text.\n"
                f"Rule: The predicate MUST be a specific action verb like 'causes', 'enables', 'derives_from', 'acts_on'.\n"
                f"Text: {text}\n"
                f"Output strictly as: Subject | Predicate | Object"
            )
            inputs = self.nlp_tokenizer(prompt, return_tensors="pt", max_length=128, truncation=True)
            outputs = self.nlp_model.generate(**inputs, max_new_tokens=50, temperature=0.1, do_sample=False)
            output_text = self.nlp_tokenizer.decode(outputs[0], skip_special_tokens=True)
            logger.info(f"Raw LLM output: {output_text}")
            
            # More robust parsing:
            import re
            parts = re.split(r'\s*\|\s*', output_text.strip())
            
            # Sometimes T5 returns 'Subject | Predicate | Object' literally, or fails to split
            if len(parts) >= 3 and parts[0].lower() != "subject":
                return [KnowledgeTriplet(subject=parts[0].title(), predicate=parts[1].replace(" ", "_").lower(), object=parts[2].title(), source_reference=source_ref)]
            else:
                logger.warning(f"LLM produced non-standard output format: {output_text}")
                # Fallback to dynamic keyword extraction if the model fails layout
                return self._fallback_extract(text, source_ref)
                
        except Exception as e:
            logger.error(f"Genuine LLM extraction failed: {e}")
            return self._fallback_extract(text, source_ref)
            
    def _fallback_extract(self, text, source_ref):
        """Intelligent semantic fallback using spaCy Dependency Parsing when LLM fails"""
        try:
            import spacy
            if not getattr(self, "spacy_nlp", None):
                self.spacy_nlp = spacy.load("en_core_web_sm")
        except ImportError:
            logger.error("spaCy missing. Falling back to empty tuple generation.")
            return []

        doc = self.spacy_nlp(text)
        triplets = []
        
        for token in doc:
            # Find the main action verb in the sentence chunk
            if token.pos_ == "VERB" and (token.dep_ == "ROOT" or token.dep_ == "advcl" or token.dep_ == "ccomp"):
                subject = None
                obj = None
                
                # Look for syntactic subject and object attached to this verb
                for child in token.children:
                    if child.dep_ in ("nsubj", "nsubjpass"):
                        # Get the entire noun phrase for context, not just the single word
                        subject = " ".join([w.text for w in child.subtree]).strip()
                    if child.dep_ in ("dobj", "pobj", "attr", "acomp"):
                        obj = " ".join([w.text for w in child.subtree]).strip()
                        
                if subject and obj and len(subject) > 2 and len(obj) > 2:
                    # Clean out massive rambling subtrees (limit to 30 chars for UI aesthetics)
                    subject = subject[:30].title()
                    obj = obj[:30].title()
                    predicate = token.lemma_.lower()
                    triplets.append(KnowledgeTriplet(subject=subject, predicate=predicate, object=obj, source_reference=source_ref))
        
        # Deduplicate elements
        unique_triplets = []
        seen = set()
        for t in triplets:
            key = f"{t.subject}-{t.predicate}-{t.object_}"
            if key not in seen:
                seen.add(key)
                unique_triplets.append(t)
                
        return unique_triplets

