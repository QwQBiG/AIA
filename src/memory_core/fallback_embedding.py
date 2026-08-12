"""
Fallback embedding system for offline use.
"""

import numpy as np
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class SimpleFallbackEmbedding:
    """Simple fallback embedding that works offline."""
    
    def __init__(self):
        self.dimension = 384  # Match all-MiniLM-L6-v2 dimension
        logger.info("Using simple fallback embedding (offline mode)")
    
    def encode(self, text, **kwargs):
        """Generate a simple hash-based embedding."""
        # Simple hash-based embedding for offline use
        text_hash = hash(text) % (2**31)  # Ensure positive
        
        # Create a deterministic but varied embedding
        np.random.seed(text_hash)
        embedding = np.random.normal(0, 1, self.dimension)
        
        # Normalize the embedding
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm
        
        return embedding.astype(np.float32)

def get_fallback_model():
    """Get the fallback embedding model."""
    return SimpleFallbackEmbedding()
