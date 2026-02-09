
import json
import os
import math
import time
from colorama import Fore
from . import config

# Simple, lightweight Vector Store using Cosine Similarity
# We avoid heavy deps like chromadb/faiss for now to ensure compatibility.
# If config.ACTIVE_MODE is True, we use Ollama embeddings.
# Fallback: TF-IDF or Keyword overlap (for now, simple word vector stub)

class VectorMemory:
    def __init__(self, storage_file="memory_store.json"):
        self.storage_file = storage_file
        self.data = [] # List of {text, vector, metadata}
        self.load()
        
    def load(self):
        if os.path.exists(self.storage_file):
            try:
                with open(self.storage_file, 'r', encoding='utf-8') as f:
                    self.data = json.load(f)
                print(f"{Fore.CYAN}[*] Loaded {len(self.data)} memories from {self.storage_file}")
            except Exception as e:
                print(f"{Fore.RED}[!] Failed to load memory: {e}")
                self.data = []

    def save(self):
        try:
            with open(self.storage_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f)
        except Exception as e:
            print(f"{Fore.RED}[!] Failed to save memory: {e}")

    def get_embedding(self, text):
        """
        Get vector embedding.
        Priority:
        1. Ollama (nomic-embed-text or mxbai-embed-large) if ACTIVE_MODE
        2. Simple conceptual hash (Fallback)
        """
        if config.ACTIVE_MODE:
            try:
                import ollama
                # Use a small embedding model. 
                # User needs to pull it: ollama pull nomic-embed-text
                response = ollama.embeddings(model="nomic-embed-text", prompt=text)
                return response['embedding']
            except Exception:
                pass # Fallback
        
        # Fallback: Simple Bag-of-Words Hash (Not true semantic, but better than nothing for exact matches)
        # In a real "Project Ultra", we'd bundle FastEmbed.
        # For now, let's just return a placeholder or warning if no Ollama.
        return None # meaningful fallback TODO

    def add(self, text, metadata=None):
        vector = self.get_embedding(text)
        if not vector and config.ACTIVE_MODE:
             print(f"{Fore.YELLOW}[!] Warning: Could not generate embedding. Is Ollama running?")
             return False
             
        entry = {
            "text": text,
            "vector": vector,
            "metadata": metadata or {},
            "timestamp": time.time()
        }
        self.data.append(entry)
        self.save()
        return True

    def search(self, query, k=3):
        """
        Find top-k similar items.
        """
        query_vec = self.get_embedding(query)
        if not query_vec: return [] # Cannot search without embedding
        
        results = []
        for item in self.data:
            if not item.get('vector'): continue
            score = self.cosine_similarity(query_vec, item['vector'])
            results.append((score, item))
            
        results.sort(key=lambda x: x[0], reverse=True)
        return [r[1] for r in results[:k]]

    def cosine_similarity(self, v1, v2):
        dot_product = sum(a*b for a,b in zip(v1, v2))
        norm_a = math.sqrt(sum(a*a for a in v1))
        norm_b = math.sqrt(sum(b*b for b in v2))
        return dot_product / (norm_a * norm_b) if norm_a and norm_b else 0.0
