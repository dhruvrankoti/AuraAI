import time
import random

def run_lsh_benchmark_100k():
    print("Generating 100,000 mock image hashes...")
    random.seed(42)
    
    # Generate 100,000 random 64-bit hashes
    photos = []
    hash_ints = {}
    
    for i in range(100000):
        p_id = f"photo_{i}"
        # Generate a random 64-bit integer
        h_val = random.getrandbits(64)
        hash_ints[p_id] = h_val
        photos.append((p_id, h_val))
        
    # Inject 5 near-duplicate pairs (distance <= 4)
    print("Injecting 5 near-duplicate pairs...")
    duplicates_to_find = []
    for pair_idx in range(5):
        base_photo_idx = random.randint(0, 99990)
        base_id = f"photo_{base_photo_idx}"
        base_hash = hash_ints[base_id]
        
        # Flip 3 random bits to make it a near-duplicate
        dup_hash = base_hash
        bits_to_flip = random.sample(range(64), 3)
        for bit in bits_to_flip:
            dup_hash ^= (1 << bit)
            
        dup_id = f"photo_dup_{pair_idx}"
        hash_ints[dup_id] = dup_hash
        duplicates_to_find.append((base_id, dup_id))
        
    print("Starting LSH duplicate detection scan over 100,000 items...")
    start_time = time.time()
    
    # LSH indexing: 4 chunks of 16 bits
    chunks = {0: {}, 1: {}, 2: {}, 3: {}}
    for p_id, h_val in hash_ints.items():
        for i in range(4):
            chunk_val = (h_val >> (i * 16)) & 0xFFFF
            if chunk_val not in chunks[i]:
                chunks[i][chunk_val] = []
            chunks[i][chunk_val].append(p_id)
            
    detected_pairs = set()
    pairs_list = []
    
    # LSH query matching
    for p_id, h_val in hash_ints.items():
        candidates = set()
        for i in range(4):
            chunk_val = (h_val >> (i * 16)) & 0xFFFF
            candidates.update(chunks[i][chunk_val])
            
        candidates.discard(p_id)
        
        for cand_id in candidates:
            pair_key = tuple(sorted([p_id, cand_id]))
            if pair_key in detected_pairs:
                continue
                
            cand_val = hash_ints[cand_id]
            dist = bin(h_val ^ cand_val).count('1')
            
            if dist <= 6:
                detected_pairs.add(pair_key)
                pairs_list.append((p_id, cand_id, dist))
                
    end_time = time.time()
    duration = end_time - start_time
    
    print(f"\n--- Benchmark Results ---")
    print(f"Total Photos Scanned: {len(hash_ints)}")
    print(f"Scan Duration: {duration:.4f} seconds")
    print(f"Duplicate Pairs Found: {len(pairs_list)}")
    
    # Verify we found the injected duplicates
    found_count = 0
    for base_id, dup_id in duplicates_to_find:
        pair_key = tuple(sorted([base_id, dup_id]))
        if pair_key in detected_pairs:
            found_count += 1
            
    print(f"Successfully retrieved {found_count}/5 injected near-duplicates.")
    
    assert duration < 1.0, f"Benchmark took too long: {duration:.2f}s"
    assert found_count == 5, "Failed to find all injected duplicates"
    print("Benchmark PASSED: Scaled scan completed in < 1 second with 100% accuracy!")

if __name__ == "__main__":
    run_lsh_benchmark_100k()
