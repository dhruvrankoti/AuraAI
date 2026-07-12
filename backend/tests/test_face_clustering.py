import numpy as np
from sklearn.cluster import DBSCAN
import pytest

def test_dbscan_clustering_accuracy():
    # Set seed for reproducibility
    np.random.seed(42)
    
    # Create two centroids in 512-dimensional space
    centroid_a = np.zeros(512)
    centroid_a[0] = 1.0
    
    centroid_b = np.zeros(512)
    centroid_b[1] = 1.0
    
    # Generate 5 faces for Person A (small perturbations)
    person_a_faces = [centroid_a + np.random.normal(0, 0.05, 512) for _ in range(5)]
    # L2 normalize them (since face embeddings are L2 normalized)
    person_a_faces = [v / np.linalg.norm(v) for v in person_a_faces]
    
    # Generate 5 faces for Person B (small perturbations)
    person_b_faces = [centroid_b + np.random.normal(0, 0.05, 512) for _ in range(5)]
    person_b_faces = [v / np.linalg.norm(v) for v in person_b_faces]
    
    # Generate 1 noise face (far away from both)
    noise_face = np.zeros(512)
    noise_face[250] = 1.0
    noise_face = noise_face / np.linalg.norm(noise_face)
    
    # Combine into a dataset
    dataset = person_a_faces + person_b_faces + [noise_face]
    X = np.array(dataset)
    
    # Run DBSCAN (eps=0.55, identical to what is in tasks.py)
    dbscan = DBSCAN(eps=0.55, min_samples=2, metric="euclidean")
    labels = dbscan.fit_predict(X)
    
    # We expect Person A (indices 0-4) to be cluster 0
    # We expect Person B (indices 5-9) to be cluster 1
    # We expect noise (index 10) to be -1
    
    cluster_a = labels[0:5]
    cluster_b = labels[5:10]
    noise_label = labels[10]
    
    # Assert all elements of Person A share the same positive label
    assert len(set(cluster_a)) == 1
    assert cluster_a[0] != -1
    
    # Assert all elements of Person B share the same positive label
    assert len(set(cluster_b)) == 1
    assert cluster_b[0] != -1
    
    # Assert they are clustered into different groups
    assert cluster_a[0] != cluster_b[0]
    
    # Assert the noise face is labeled -1 (unclassified)
    assert noise_label == -1
