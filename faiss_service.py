# faiss_service.py
"""
Py-Match FAISS Knowledge Service (UPDATED for single combined index)

Now uses single combined index from all 6 books:
- book_index.json (metadata)
- vector_index.json (vector metadata)
- vector_index.pkl (embeddings + documents)

No more separate sources - one unified index.
"""

import os
import json
import pickle
import numpy as np
from typing import Any, Dict, List, Optional, Tuple
import re
from collections import defaultdict
from config import BASE_DIR
import random

# ----------------------------
# Optional dependencies
# ----------------------------
try:
    import faiss  # type: ignore
    HAS_FAISS = True
except Exception as e:
    print("[FAISS] faiss import failed:", e)
    HAS_FAISS = False
    faiss = None  # type: ignore

try:
    from sentence_transformers import SentenceTransformer  # type: ignore
    HAS_EMBEDDER = True
except Exception as e:
    print("[FAISS] sentence-transformers import failed:", e)
    HAS_EMBEDDER = False
    SentenceTransformer = None  # type: ignore

# ----------------------------
# NEW: Single combined index paths
# ----------------------------
COMBINED_INDEX_PATH = os.path.join(BASE_DIR, "vector_index.pkl")
COMBINED_META_PATH = os.path.join(BASE_DIR, "vector_index.json")
BOOK_INDEX_PATH = os.path.join(BASE_DIR, "book_index.json")

# ----------------------------
# Cleaning helpers
# ----------------------------
_NOISE_PATTERNS = [
    "margin-left", "margin-right", "font-size", "@media", "text-indent",
    "border-collapse", "position:", "display:", "visibility:", "table {",
    "ul.", "li.", ".td", "{", "}", "<div", "<p", "<style", "</style>", "<svg"
]

def _looks_like_noise(t: str) -> bool:
    low = (t or "").lower()
    return any(p in low for p in _NOISE_PATTERNS)

def _clean_text(t: str) -> str:
    if not t:
        return ""

    # Remove soft hyphen / odd breaks
    t = t.replace("¬", "")
    t = t.replace("\x00", " ")

    # Collapse spaces
    t = re.sub(r"\s+", " ", t).strip()

    # Skip html/css-like garbage
    if _looks_like_noise(t):
        return ""

    return t

# ----------------------------
# Single Combined Index Loader
# ----------------------------
class CombinedIndexLoader:
    def __init__(self):
        self.index = None
        self.documents = []
        self.embeddings = None
        self.model_name = "all-MiniLM-L6-v2"
        self.loaded = False
        self.embedder = None
    
    def load(self) -> bool:
        """Load the single combined index from your new files"""
        if not HAS_FAISS:
            print("[FAISS] FAISS not available")
            return False
        
        if not os.path.exists(COMBINED_INDEX_PATH):
            print(f"[FAISS] Combined index not found: {COMBINED_INDEX_PATH}")
            # Try loading from JSON instead
            return self._load_from_json()
        
        try:
            print(f"[FAISS] Loading single combined index from: {COMBINED_INDEX_PATH}")
            
            # Load pickle file (contains embeddings + documents)
            with open(COMBINED_INDEX_PATH, 'rb') as f:
                index_data = pickle.load(f)
            
            # Extract data from pickle
            self.documents = index_data.get("documents", [])
            self.embeddings = np.array(index_data.get("embeddings", []))
            self.model_name = index_data.get("model", "all-MiniLM-L6-v2")
            
            # Create FAISS index from embeddings
            if self.embeddings is not None and len(self.embeddings) > 0:
                dimension = self.embeddings.shape[1]
                self.index = faiss.IndexFlatL2(dimension)
                self.index.add(self.embeddings.astype('float32'))
            
            # Load embedder
            if HAS_EMBEDDER:
                try:
                    self.embedder = SentenceTransformer(self.model_name)
                except Exception as e:
                    print(f"[FAISS] Failed to load embedder: {e}")
                    self.embedder = None
            
            self.loaded = True
            print(f"[FAISS] Loaded {len(self.documents)} documents from combined index")
            print(f"[FAISS] Embedding dimension: {self.embeddings.shape[1] if self.embeddings is not None else 0}")
            
            return True
            
        except Exception as e:
            print(f"[FAISS] Failed to load combined index: {e}")
            return self._load_from_json()
    
    def _load_from_json(self) -> bool:
        """Fallback: Load from JSON metadata and create index"""
        if not os.path.exists(BOOK_INDEX_PATH):
            print(f"[FAISS] Book index not found: {BOOK_INDEX_PATH}")
            return False
        
        try:
            print(f"[FAISS] Loading from book_index.json: {BOOK_INDEX_PATH}")
            
            with open(BOOK_INDEX_PATH, 'r', encoding='utf-8') as f:
                book_index = json.load(f)
            
            self.documents = book_index.get("documents", [])
            
            # Create embeddings if we have embedder
            if HAS_EMBEDDER and SentenceTransformer:
                try:
                    self.embedder = SentenceTransformer("all-MiniLM-L6-v2")
                    
                    # Create embeddings for all documents
                    texts = [doc.get("content", "") for doc in self.documents]
                    print(f"[FAISS] Creating embeddings for {len(texts)} documents...")
                    self.embeddings = self.embedder.encode(
                        texts, 
                        show_progress_bar=True,
                        normalize_embeddings=True
                    )
                    
                    # Create FAISS index
                    dimension = self.embeddings.shape[1]
                    self.index = faiss.IndexFlatL2(dimension)
                    self.index.add(self.embeddings.astype('float32'))
                    
                    self.loaded = True
                    self.model_name = "all-MiniLM-L6-v2"
                    
                    print(f"[FAISS] Created embeddings and index with {len(self.documents)} documents")
                    return True
                    
                except Exception as e:
                    print(f"[FAISS] Failed to create embeddings: {e}")
                    return False
            
            return False
            
        except Exception as e:
            print(f"[FAISS] Failed to load from JSON: {e}")
            return False
    
    def is_ready(self) -> bool:
        return self.loaded and self.index is not None and len(self.documents) > 0
    
    def _encode(self, query: str):
        """Encode query using the embedder"""
        if not self.embedder or not query:
            return None
        return self.embedder.encode([query]).astype("float32")
    
    def search(
        self,
        query: str,
        topk: int = 5,
        concept_type: Optional[str] = None,
        book_filter: Optional[str] = None,
        max_chars: int = 900
    ) -> List[Dict[str, Any]]:
        """Search the combined index"""
        if not self.is_ready():
            return []
        
        qvec = self._encode(query)
        if qvec is None:
            return []
        
        try:
            # Search FAISS index
            D, I = self.index.search(qvec, topk * 3)
            
            results = []
            for d, idx in zip(D[0], I[0]):
                if idx < 0 or idx >= len(self.documents):
                    continue
                
                doc = self.documents[idx]
                
                # Apply filters
                if concept_type is not None:
                    if doc.get("concept_type") != concept_type:
                        continue
                
                if book_filter is not None:
                    book_name = doc.get("book", "").lower()
                    if book_filter.lower() not in book_name:
                        continue
                
                # Clean text
                content = doc.get("content", "")
                clean_content = _clean_text(content)
                if not clean_content:
                    continue
                
                if max_chars and len(clean_content) > max_chars:
                    clean_content = clean_content[:max_chars]
                
                # Build result
                result = {
                    "text": clean_content,
                    "source": "Combined Books Index",
                    "book_name": doc.get("book", "Unknown Book"),
                    "book_id": doc.get("book_id", ""),
                    "concept_type": doc.get("concept_type"),
                    "chunk_index": doc.get("chunk_index", 0),
                    "score": float(d),
                    "raw_score": float(d),
                }
                results.append(result)
            
            # Sort by score (distance)
            results.sort(key=lambda x: x["score"])
            return results[:topk]
            
        except Exception as e:
            print(f"[FAISS] Search failed: {e}")
            return []
    
    def search_color_personality(
        self,
        color: str,
        behavior_type: str = "personality",
        topk: int = 3
    ) -> List[Dict[str, Any]]:
        """Specifically search for color personality behaviors"""
        if not self.is_ready():
            return []
        
        # Different search queries for different color aspects
        color_queries = {
            "red": [
                f"{color} personality assertive dominant competitive decisive",
                f"{color} behavior leadership direct action-oriented",
                f"{color} traits ambitious results-driven"
            ],
            "blue": [
                f"{color} personality analytical detail-oriented systematic",
                f"{color} behavior perfectionist logical precise",
                f"{color} traits organized methodical"
            ],
            "green": [
                f"{color} personality patient cooperative supportive",
                f"{color} behavior peaceful reliable team-oriented",
                f"{color} traits empathetic calm"
            ],
            "yellow": [
                f"{color} personality optimistic creative enthusiastic",
                f"{color} behavior social energetic inspiring",
                f"{color} traits spontaneous expressive"
            ]
        }
        
        all_results = []
        
        for query in color_queries.get(color, [f"{color} personality behavior"]):
            results = self.search(
                query=query,
                topk=topk,
                max_chars=150
            )
            
            for result in results:
                # Check if it contains behavioral content
                text = result.get("text", "").lower()
                if self._is_behavioral_text(text, color):
                    # Add color context
                    if color not in text:
                        result["text"] = f"{color.capitalize()}: {result['text']}"
                    
                    result["color"] = color
                    all_results.append(result)
        
        # Remove duplicates
        seen_texts = set()
        unique_results = []
        for result in all_results:
            text = result.get("text", "")
            if text and text not in seen_texts:
                seen_texts.add(text)
                unique_results.append(result)
        
        return unique_results[:topk]
    
    def _is_behavioral_text(self, text: str, color: str) -> bool:
        """Check if text contains behavioral/personality content"""
        if not text or len(text) < 20:
            return False
        
        text_lower = text.lower()
        
        # Behavioral indicators
        behavioral_indicators = [
            "tends to", "typically", "usually", "often",
            "behaves", "acts", "prefers", "likes",
            "characteristic", "trait", "personality",
            "behavior", "approach", "style", "way"
        ]
        
        # Check for behavioral language
        has_behavioral = any(indicator in text_lower for indicator in behavioral_indicators)
        
        # Color-specific traits
        color_traits = {
            "red": ["assertive", "dominant", "competitive", "decisive", "leader"],
            "blue": ["analytical", "detailed", "perfectionist", "systematic", "logical"],
            "green": ["patient", "cooperative", "supportive", "peaceful", "team"],
            "yellow": ["optimistic", "creative", "social", "enthusiastic", "energetic"]
        }
        
        has_color_trait = any(trait in text_lower for trait in color_traits.get(color, []))
        
        return has_behavioral or has_color_trait

# ----------------------------
# Main knowledge API (Simplified)
# ----------------------------
class KnowledgeSource:
    def __init__(self):
        self.loader = CombinedIndexLoader()
        self.loader.load()
    
    def is_ready(self) -> bool:
        return self.loader.is_ready()
    
    def search(
        self,
        query: str,
        topk: int = 5,
        concept_type: Optional[str] = None,
        source_names: Optional[List[str]] = None,  # Kept for compatibility
        max_chars: int = 900
    ) -> List[Dict[str, Any]]:
        """Search the combined index"""
        return self.loader.search(
            query=query,
            topk=topk,
            concept_type=concept_type,
            max_chars=max_chars
        )
    
    def search_color_personality(
        self,
        color: str,
        behavior_type: str = "personality",
        topk: int = 3
    ) -> List[Dict[str, Any]]:
        """Search for color personality behaviors"""
        return self.loader.search_color_personality(
            color=color,
            behavior_type=behavior_type,
            topk=topk
        )

# ----------------------------
# Globals for compatibility
# ----------------------------
knowledge = KnowledgeSource()

FAISS_INDEX = knowledge.loader.index if knowledge.loader else None
TEXT_CHUNKS = [doc.get("content", "") for doc in knowledge.loader.documents] if knowledge.loader else []
COLOR_EXAMPLES = None

# ----------------------------
# Compatibility functions
# ----------------------------
def get_faiss_context(k: int = 3) -> str:
    """Get random context from combined index"""
    if not TEXT_CHUNKS:
        return ""
    
    import random
    clean_chunks = [t for t in TEXT_CHUNKS if t and not _looks_like_noise(t)]
    if not clean_chunks:
        clean_chunks = TEXT_CHUNKS
    
    selected = random.sample(clean_chunks, min(k, len(clean_chunks)))
    return "\n".join(selected)

def get_nearest_context(query_vector: Optional[List[float]] = None, k: int = 5) -> str:
    """Legacy function - kept for compatibility"""
    if not HAS_FAISS or FAISS_INDEX is None or query_vector is None:
        return ""
    
    try:
        import numpy as np
        arr = np.array([query_vector], dtype="float32")
        D, I = FAISS_INDEX.search(arr, k)
        texts: List[str] = []
        for idx in I[0].tolist():
            if 0 <= idx < len(TEXT_CHUNKS):
                texts.append(TEXT_CHUNKS[idx])
        return "\n\n".join(texts)
    except Exception as e:
        print("[FAISS] get_nearest_context failed:", e)
        return ""

def search_pymatch_knowledge(
    query: str,
    concept_type: Optional[str] = None,
    topk: int = 5,
    top_k: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Compatibility wrapper"""
    if top_k is not None:
        topk = top_k
    
    if not knowledge or not knowledge.is_ready():
        return []
    
    return knowledge.search(
        query=query,
        topk=topk,
        concept_type=concept_type
    )

# Print status
print(f"[FAISS] Single combined index service initialized")
print(f"[FAISS] Ready: {knowledge.is_ready()}")
print(f"[FAISS] Documents: {len(TEXT_CHUNKS)}")