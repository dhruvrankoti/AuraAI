import os
import tempfile
from PIL import Image, ImageEnhance
import pytest
from services.ai_pipeline import AIService

def create_dummy_image(color=(255, 0, 0), size=(200, 200)):
    return Image.new('RGB', size, color=color)

def test_sha256_exact_duplicate():
    # Setup temp files
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f1, \
         tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f2:
        
        img = create_dummy_image()
        img.save(f1.name)
        img.save(f2.name)
        
        path1 = f1.name
        path2 = f2.name
        
    try:
        hash1 = AIService.compute_sha256(path1)
        hash2 = AIService.compute_sha256(path2)
        
        assert hash1 == hash2
        assert len(hash1) == 64
    finally:
        os.remove(path1)
        os.remove(path2)

def test_phash_near_duplicate():
    img1 = create_dummy_image(color=(100, 150, 200))
    
    # 1. Resize duplicate
    img2 = img1.resize((100, 100))
    
    # 2. Brightness modified duplicate
    enhancer = ImageEnhance.Brightness(img1)
    img3 = enhancer.enhance(1.2) # Make 20% brighter
    
    # 3. Wholly different image
    img_diff = create_dummy_image(color=(200, 50, 50))
    
    hash1 = int(AIService.compute_phash(img1), 16)
    hash2 = int(AIService.compute_phash(img2), 16)
    hash3 = int(AIService.compute_phash(img3), 16)
    hash_diff = int(AIService.compute_phash(img_diff), 16)
    
    # Helper to count matching bits
    def get_hamming(h1, h2):
        return bin(h1 ^ h2).count('1')
        
    # Near duplicates should have extremely small Hamming distances
    assert get_hamming(hash1, hash2) <= 2
    assert get_hamming(hash1, hash3) <= 4
    
    # Different images should have larger Hamming distances
    assert get_hamming(hash1, hash_diff) > 10
