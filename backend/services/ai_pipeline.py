import hashlib
import numpy as np
from PIL import Image
import pytesseract
import imagehash
from google import genai
from google.genai import types
from config import settings
import torch

class AIService:
    _clip_model = None
    _text_model = None
    _mtcnn = None
    _facenet = None
    _gemini_client = None
    _description_embeddings = None

    @classmethod
    def get_gemini_client(cls):
        if cls._gemini_client is None and settings.GEMINI_API_KEY:
            cls._gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY)
        return cls._gemini_client

    @classmethod
    def get_clip_model(cls):
        if cls._clip_model is None:
            from sentence_transformers import SentenceTransformer
            # clip-ViT-B-32 provides 768-dimensional multimodal embeddings
            cls._clip_model = SentenceTransformer('clip-ViT-B-32')
        return cls._clip_model

    @classmethod
    def get_text_model(cls):
        if cls._text_model is None:
            from sentence_transformers import SentenceTransformer
            # all-MiniLM-L6-v2 provides 384-dimensional sentence embeddings
            cls._text_model = SentenceTransformer('all-MiniLM-L6-v2')
        return cls._text_model

    @classmethod
    def get_face_models(cls):
        if cls._mtcnn is None or cls._facenet is None:
            from facenet_pytorch import MTCNN, InceptionResnetV1
            # Initialize face detector and face embedding model
            cls._mtcnn = MTCNN(keep_all=True, device='cpu', post_process=False)
            cls._facenet = InceptionResnetV1(pretrained='vggface2').eval()
        return cls._mtcnn, cls._facenet

    @staticmethod
    def compute_sha256(file_path: str) -> str:
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    @staticmethod
    def compute_phash(image: Image.Image) -> str:
        try:
            return str(imagehash.phash(image))
        except Exception as e:
            print(f"Error computing pHash: {e}")
            return ""

    @classmethod
    def get_image_clip_embedding(cls, image: Image.Image) -> list[float]:
        model = cls.get_clip_model()
        embedding = model.encode(image, convert_to_numpy=True)
        return embedding.tolist()

    @classmethod
    def get_text_clip_embedding(cls, text: str) -> list[float]:
        model = cls.get_clip_model()
        embedding = model.encode(text, convert_to_numpy=True)
        return embedding.tolist()

    @classmethod
    def get_ocr_text_embedding(cls, text: str) -> list[float]:
        model = cls.get_text_model()
        embedding = model.encode(text, convert_to_numpy=True)
        return embedding.tolist()

    @classmethod
    def detect_and_embed_faces(cls, image: Image.Image) -> list[dict]:
        mtcnn, facenet = cls.get_face_models()
        
        # Convert PIL to RGB
        img_rgb = image.convert('RGB')
        
        # Detect faces
        boxes, probs = mtcnn.detect(img_rgb)
        
        if boxes is None:
            return []
            
        faces_data = []
        for i, box in enumerate(boxes):
            # MTCNN face boxes might have confidence scores, filter out low confidence detections
            if probs is not None and probs[i] < 0.85:
                continue
                
            x1, y1, x2, y2 = [max(0, int(b)) for b in box]
            
            # Crop face from image
            face_crop = img_rgb.crop((x1, y1, x2, y2))
            # Resize to expected shape for facenet (160x160)
            face_crop = face_crop.resize((160, 160))
            
            # Preprocess for FaceNet
            face_tensor = torch.tensor(np.array(face_crop)).permute(2, 0, 1).float()
            face_tensor = (face_tensor - 127.5) / 128.0  # Normalized as per MTCNN output standard
            
            with torch.no_grad():
                embedding = facenet(face_tensor.unsqueeze(0)).numpy().flatten()
            
            faces_data.append({
                "bounding_box": [x1, y1, x2, y2],
                "embedding": embedding.tolist()
            })
            
        return faces_data

    @classmethod
    def run_local_ocr(cls, image: Image.Image) -> str:
        try:
            return pytesseract.image_to_string(image)
        except Exception as e:
            print(f"Local OCR Error: {e}")
            return ""

    @classmethod
    def get_description_embeddings(cls):
        if cls._description_embeddings is None:
            model = cls.get_clip_model()
            descriptions = [
                "a scanned document or paper text",
                "a cash receipt, invoice, or transaction bill",
                "a medical prescription or pharmacy drug slip",
                "a travel scene, vacation landscape, landmark, or outdoor scenery",
                "a domestic animal, dog, cat, or pet",
                "a portrait of people, face, group of friends, or human beings",
                "a general photograph or object"
            ]
            cls._description_embeddings = model.encode(descriptions, convert_to_numpy=True)
        return cls._description_embeddings

    @classmethod
    def classify_zero_shot(cls, image: Image.Image) -> str:
        categories = ["document", "receipt", "prescription", "travel", "pets", "people", "other"]
        model = cls.get_clip_model()
        
        # Encode image
        img_emb = model.encode(image, convert_to_numpy=True)
        
        # Use cached candidate category embeddings to resolve semantics
        text_embs = cls.get_description_embeddings()
        
        # Compute cosine similarities
        similarities = [
            np.dot(img_emb, t_emb) / (np.linalg.norm(img_emb) * np.linalg.norm(t_emb))
            for t_emb in text_embs
        ]
        
        best_idx = np.argmax(similarities)
        return categories[best_idx]

    @classmethod
    def process_with_gemini(cls, image_path: str) -> dict:
        """
        Uses Gemini 2.5 Flash to extract:
        1. OCR Text
        2. Caption / Description
        3. Category (document, receipt, prescription, travel, pets, people, other)
        4. Rich metadata (location name, objects list)
        """
        client = cls.get_gemini_client()
        if not client:
            return {}
            
        try:
            # Load the image
            img = Image.open(image_path)
            
            prompt = """
            Analyze this image. Provide the output strictly in the following JSON format:
            {
                "caption": "A concise description of the photo",
                "category": "One of the following categories: document, receipt, prescription, travel, pets, people, other",
                "ocr_text": "Extract all readable text in the image. If none, leave empty string",
                "location": "Name of the location if identifiable, otherwise null",
                "objects": ["list", "of", "detected", "objects"]
            }
            Make sure your response is only the valid JSON object and nothing else.
            """
            
            # Using modern Gemini 2.5 Flash
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[img, prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )
            
            import json
            data = json.loads(response.text)
            return data
        except Exception as e:
            print(f"Gemini processing error: {e}")
            return {}
