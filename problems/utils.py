import re
from difflib import SequenceMatcher
from django.utils.text import slugify
from .models import Problem

def normalize_title(title):
    """
    Normalizes a problem title: lowercase and remove symbols.
    """
    if not title:
        return ""
    # Remove all non-alphanumeric characters, keep spaces
    normalized = re.sub(r'[^a-zA-Z0-9\s]', '', title.lower())
    # Replace multiple spaces with one
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    return normalized

def find_canonical_problem(title, difficulty=None):
    """
    Fuzzy matching logic to map a platform problem to a canonical one.
    """
    norm_title = normalize_title(title)
    
    # Try exact slug match first
    slug = slugify(title)
    canonical = Problem.objects.filter(slug=slug).first()
    if canonical:
        return canonical, False

    # Try exact match on canonical_name (case-insensitive) after normalization
    # This is expensive if there are many problems, but good for accuracy
    # For now, let's use a simple similarity check against existing problems
    
    best_match = None
    best_score = 0.0
    
    # Limit search to similar difficulties if provided to narrow down
    queryset = Problem.objects.all()
    if difficulty:
        queryset = queryset.filter(difficulty=difficulty)
        
    for p in queryset.iterator():
        p_norm = normalize_title(p.canonical_name)
        score = SequenceMatcher(None, norm_title, p_norm).ratio()
        if score > 0.85 and score > best_score:
            best_score = score
            best_match = p
            
    if best_match:
        return best_match, False
    
    # If no match found, create a new canonical problem
    new_canonical = Problem.objects.create(
        canonical_name=title,
        difficulty=difficulty or None # Should be handled by caller
    )
    return new_canonical, True
