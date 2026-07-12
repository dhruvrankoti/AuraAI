import re
from typing import List, Optional
from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from datetime import datetime
from config import settings

class SearchPlan(BaseModel):
    semantic_query: Optional[str] = Field(None, description="Query to be used for CLIP image vector search")
    categories: Optional[List[str]] = Field(None, description="Categories to filter by. Choose from: 'document', 'receipt', 'prescription', 'travel', 'pets', 'people', 'other'")
    ocr_query: Optional[str] = Field(None, description="Keyword to search in extracted OCR text (for documents, receipts, prescriptions)")
    date_start: Optional[str] = Field(None, description="ISO 8601 format date-time string representing the start of a time range")
    date_end: Optional[str] = Field(None, description="ISO 8601 format date-time string representing the end of a time range")
    person_names: Optional[List[str]] = Field(None, description="Names of specific people mentioned in the query")
    location: Optional[str] = Field(None, description="Specific location mentioned in the query (e.g., 'Goa', 'Paris')")

class SearchPlanner:
    @classmethod
    def plan_search(cls, query: str) -> SearchPlan:
        # Get Gemini Client
        if settings.GEMINI_API_KEY:
            try:
                client = genai.Client(api_key=settings.GEMINI_API_KEY)
                current_time = datetime.now().isoformat()
                
                prompt = f"""
                Analyze the user query: "{query}"
                Current system time is: {current_time}
                
                Translate this query into a structured search plan.
                - Extract categories if explicitly mentioned or strongly implied (e.g., "receipt" -> category receipt, "dog" -> category pets, "scenery" -> category travel).
                - For dates, convert relative descriptions like "last year", "last month", "July 2025" to precise ISO 8601 ranges (date_start and date_end).
                - For person names, extract any proper names of people (e.g., "Rahul", "Sarah").
                - For locations, extract place names.
                - The semantic_query should be the core concept to look up in the CLIP embedding space.
                
                Return the response matching the schema.
                """
                
                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=SearchPlan
                    )
                )
                
                # Parse JSON and load into model
                import json
                data = json.loads(response.text)
                return SearchPlan(**data)
            except Exception as e:
                print(f"Error calling Gemini search planner: {e}. Falling back to local parser.")
        
        # Local fallback parsing
        return cls._local_parse(query)

    @classmethod
    def _local_parse(cls, query: str) -> SearchPlan:
        query_lower = query.lower()
        
        # Categorization detection
        categories = []
        if any(w in query_lower for w in ["receipt", "bill", "invoice", "payment"]):
            categories.append("receipt")
        if any(w in query_lower for w in ["prescription", "doctor note", "medicine", "medical"]):
            categories.append("prescription")
        if any(w in query_lower for w in ["document", "pdf", "cv", "resume", "passport", "id card"]):
            categories.append("document")
        if any(w in query_lower for w in ["travel", "trip", "vacation", "holiday", "scenery", "beach", "mountain"]):
            categories.append("travel")
        if any(w in query_lower for w in ["pet", "dog", "cat", "animal", "puppy", "kitten"]):
            categories.append("pets")
        if any(w in query_lower for w in ["person", "people", "friend", "selfie", "crowd"]):
            categories.append("people")
            
        # OCR query extraction
        ocr_query = None
        # If the user asks for a specific text in quotes
        quotes_match = re.findall(r'"([^"]*)"', query)
        if quotes_match:
            ocr_query = quotes_match[0]
        elif any(c in categories for c in ["receipt", "prescription", "document"]):
            # Use query terms minus category words as OCR query
            cleaned_words = [w for w in query.split() if w.lower() not in ["receipt", "bill", "invoice", "prescription", "document", "show", "me", "find", "photos", "of", "from"]]
            if cleaned_words:
                ocr_query = " ".join(cleaned_words)
                
        # Basic date extraction (e.g., year like 2025, 2026)
        year_match = re.search(r'\b(20\d{2})\b', query)
        date_start = None
        date_end = None
        if year_match:
            year = year_match.group(1)
            date_start = f"{year}-01-01T00:00:00"
            date_end = f"{year}-12-31T23:59:59"
            
        # Extract proper names (capitalized words that are not start of sentence, or after trigger words)
        person_names = []
        words = query.split()
        for idx, word in enumerate(words):
            # Simple heuristic: capitalized word, not the first word, or preceded by 'with', 'and', 'of'
            if idx > 0 and word[0].isupper() and word.lower() not in ["show", "find", "my", "me", "trip", "goa", "delhi", "mumbai"]:
                cleaned_name = re.sub(r'[^\w]', '', word)
                if cleaned_name:
                    person_names.append(cleaned_name)
                    
        # Deduce location if mentioned after "in", "at", "to"
        location = None
        loc_match = re.search(r'\b(?:in|at|to|from)\s+([A-Z][a-zA-Z]+)', query)
        if loc_match:
            location = loc_match.group(1)
            
        # Semantic query is the search phrase itself
        semantic_query = query
        
        return SearchPlan(
            semantic_query=semantic_query,
            categories=categories if categories else None,
            ocr_query=ocr_query,
            date_start=date_start,
            date_end=date_end,
            person_names=person_names if person_names else None,
            location=location
        )
