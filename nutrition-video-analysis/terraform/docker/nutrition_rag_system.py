"""
Nutrition RAG System using FAISS
Combines volume estimates with density and calorie databases to predict nutritional content
"""

import json
import numpy as np
import pandas as pd
from pathlib import Path
import faiss
from sentence_transformers import SentenceTransformer
import PyPDF2
import re
import os

class NutritionRAG:
    def __init__(self, pdf_path, fndds_path, cofid_path):
        """
        Initialize RAG system with nutrition databases
        
        Args:
            pdf_path: Path to density database PDF
            fndds_path: Path to FNDDS calorie Excel
            cofid_path: Path to CoFID calorie Excel
        """
        self.pdf_path = Path(pdf_path)
        self.fndds_path = Path(fndds_path)
        self.cofid_path = Path(cofid_path)
        
        # Load sentence transformer for semantic search
        print("Loading sentence transformer model...")
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        
        # Storage for databases
        self.density_db = []
        self.calorie_db = []
        self.combined_texts = []
        
        # FAISS index
        self.index = None

        # Gemini setup (optional)
        self.gemini_api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        self.gemini_available = False
        self._gemini_model = None
        if self.gemini_api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.gemini_api_key)
                # Use a fast and available model; adjust if needed
                self._gemini_model = genai.GenerativeModel("gemini-2.5-flash")
                self.gemini_available = True
                print("Gemini fallback enabled (API key detected).")
            except Exception as e:
                print(f"Gemini init failed: {e}")
                self.gemini_available = False

    def _refine_food_label(self, label: str) -> str:
        """
        Heuristically refine generic labels into more specific cooked items for nutrition.
        """
        s = (label or "").lower().strip()
        # Map common generic terms to likely cooked counterparts
        if any(k in s for k in ["meat", "beef"]):
            return "cooked ground beef"
        if any(k in s for k in ["chicken"]):
            return "cooked chicken breast"
        if any(k in s for k in ["fish", "salmon", "tuna"]):
            return "cooked salmon"
        if any(k in s for k in ["spaghetti", "pasta", "noodles"]):
            return "cooked spaghetti pasta"
        if any(k in s for k in ["rice"]):
            return "cooked white rice"
        if any(k in s for k in ["salad", "lettuce", "greens"]):
            return "mixed salad greens"
        return f"cooked {label}".strip()
        
    def extract_density_from_pdf(self):
        """Extract food density information from PDF"""
        print(f"\nExtracting density data from {self.pdf_path.name}...")
        
        densities = []
        
        try:
            with open(self.pdf_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                
                for page_num, page in enumerate(reader.pages):
                    text = page.extract_text()
                    
                    # Look for patterns like "Spaghetti 1.05 g/cm³" or "Meat, ground beef: 0.95"
                    # This is a generic parser - may need adjustment based on actual PDF format
                    lines = text.split('\n')
                    
                    for line in lines:
                        # Try to extract food name and density
                        # Common patterns: "Food Name    Density" or "Food Name: density g/cm3"
                        match = re.search(r'([A-Za-z\s,]+?)\s*[:\-]?\s*(\d+\.?\d*)\s*(?:g/cm|g/ml|kg/L)?', line)
                        if match:
                            food_name = match.group(1).strip()
                            density_str = match.group(2)
                            
                            try:
                                density = float(density_str)
                                if 0.1 < density < 3.0:  # Reasonable density range for food
                                    densities.append({
                                        'food': food_name,
                                        'density_g_per_ml': density,
                                        'source': 'PDF',
                                        'page': page_num + 1
                                    })
                            except ValueError:
                                continue
                
                print(f"  Extracted {len(densities)} density entries from PDF")
                
        except Exception as e:
            print(f"  Error reading PDF: {e}")
            print(f"  Using fallback densities...")
            # Fallback common food densities
            densities = self._get_fallback_densities()
        
        self.density_db = densities
        return densities
    
    def _get_fallback_densities(self):
        """Fallback food densities if PDF parsing fails"""
        return [
            {'food': 'spaghetti pasta noodles', 'density_g_per_ml': 0.95, 'source': 'fallback'},
            {'food': 'meat beef ground', 'density_g_per_ml': 1.05, 'source': 'fallback'},
            {'food': 'salad lettuce greens vegetables', 'density_g_per_ml': 0.35, 'source': 'fallback'},
            {'food': 'rice cooked', 'density_g_per_ml': 0.85, 'source': 'fallback'},
            {'food': 'bread', 'density_g_per_ml': 0.25, 'source': 'fallback'},
            {'food': 'chicken meat', 'density_g_per_ml': 1.0, 'source': 'fallback'},
            {'food': 'fish', 'density_g_per_ml': 1.05, 'source': 'fallback'},
            {'food': 'potato', 'density_g_per_ml': 0.75, 'source': 'fallback'},
            {'food': 'water liquid beverage', 'density_g_per_ml': 1.0, 'source': 'fallback'},
            {'food': 'soup broth', 'density_g_per_ml': 1.0, 'source': 'fallback'},
        ]
    
    def load_calorie_databases(self):
        """Load calorie information from Excel files"""
        print(f"\nLoading calorie databases...")
        
        calories = []
        
        # Load FNDDS
        try:
            print(f"  Reading {self.fndds_path.name}...")
            df_fndds = pd.read_excel(self.fndds_path)
            
            # Try to identify relevant columns (common names)
            food_col = None
            cal_col = None
            
            for col in df_fndds.columns:
                col_lower = str(col).lower()
                if 'food' in col_lower or 'description' in col_lower or 'name' in col_lower:
                    food_col = col
                if 'calor' in col_lower or 'energy' in col_lower or 'kcal' in col_lower:
                    cal_col = col
            
            if food_col and cal_col:
                for _, row in df_fndds.iterrows():
                    food_name = str(row[food_col])
                    cal_value = row[cal_col]
                    
                    if pd.notna(food_name) and pd.notna(cal_value):
                        try:
                            calories.append({
                                'food': food_name.lower(),
                                'calories_per_100g': float(cal_value),
                                'source': 'FNDDS'
                            })
                        except:
                            continue
                
                print(f"    Loaded {len(calories)} entries from FNDDS")
            else:
                print(f"    Could not identify food/calorie columns in FNDDS")
                print(f"    Columns: {list(df_fndds.columns[:10])}")
        
        except Exception as e:
            print(f"    Error loading FNDDS: {e}")
        
        # Load CoFID
        try:
            print(f"  Reading {self.cofid_path.name}...")
            df_cofid = pd.read_excel(self.cofid_path)
            
            food_col = None
            cal_col = None
            
            for col in df_cofid.columns:
                col_lower = str(col).lower()
                if 'food' in col_lower or 'description' in col_lower or 'name' in col_lower:
                    food_col = col
                if 'calor' in col_lower or 'energy' in col_lower or 'kcal' in col_lower:
                    cal_col = col
            
            initial_count = len(calories)
            
            if food_col and cal_col:
                for _, row in df_cofid.iterrows():
                    food_name = str(row[food_col])
                    cal_value = row[cal_col]
                    
                    if pd.notna(food_name) and pd.notna(cal_value):
                        try:
                            calories.append({
                                'food': food_name.lower(),
                                'calories_per_100g': float(cal_value),
                                'source': 'CoFID'
                            })
                        except:
                            continue
                
                print(f"    Loaded {len(calories) - initial_count} entries from CoFID")
            else:
                print(f"    Could not identify food/calorie columns in CoFID")
                print(f"    Columns: {list(df_cofid.columns[:10])}")
        
        except Exception as e:
            print(f"    Error loading CoFID: {e}")
        
        # Fallback if databases fail to load
        if len(calories) == 0:
            print("  Using fallback calorie database...")
            calories = self._get_fallback_calories()
        
        self.calorie_db = calories
        print(f"\n  Total calorie entries: {len(self.calorie_db)}")
        return calories
    
    def _get_fallback_calories(self):
        """Fallback calorie data"""
        return [
            {'food': 'spaghetti pasta cooked', 'calories_per_100g': 131, 'source': 'fallback'},
            {'food': 'ground beef cooked', 'calories_per_100g': 250, 'source': 'fallback'},
            {'food': 'salad mixed greens', 'calories_per_100g': 15, 'source': 'fallback'},
            {'food': 'lettuce', 'calories_per_100g': 15, 'source': 'fallback'},
            {'food': 'rice white cooked', 'calories_per_100g': 130, 'source': 'fallback'},
            {'food': 'chicken breast cooked', 'calories_per_100g': 165, 'source': 'fallback'},
            {'food': 'bread white', 'calories_per_100g': 265, 'source': 'fallback'},
            {'food': 'potato cooked', 'calories_per_100g': 77, 'source': 'fallback'},
        ]
    
    def build_faiss_index(self):
        """Build FAISS index for semantic search"""
        print("\nBuilding FAISS index...")
        
        # Combine all food descriptions
        self.combined_texts = []
        self.combined_data = []
        
        # Add density entries
        for entry in self.density_db:
            self.combined_texts.append(entry['food'])
            self.combined_data.append({
                'type': 'density',
                'data': entry
            })
        
        # Add calorie entries
        for entry in self.calorie_db:
            self.combined_texts.append(entry['food'])
            self.combined_data.append({
                'type': 'calorie',
                'data': entry
            })
        
        # Encode texts
        print(f"  Encoding {len(self.combined_texts)} food descriptions...")
        embeddings = self.model.encode(self.combined_texts, show_progress_bar=True)
        embeddings = np.array(embeddings).astype('float32')
        
        # Normalize for cosine similarity
        faiss.normalize_L2(embeddings)
        
        # Build index
        dimension = embeddings.shape[1]
        self.index = faiss.IndexFlatIP(dimension)  # Inner product = cosine similarity
        self.index.add(embeddings)
        
        print(f"  FAISS index built with {self.index.ntotal} entries")
        
    def search(self, query, k=5):
        """Search for matching food items"""
        # Encode query
        query_embedding = self.model.encode([query])
        query_embedding = np.array(query_embedding).astype('float32')
        faiss.normalize_L2(query_embedding)
        
        # Search
        distances, indices = self.index.search(query_embedding, k)
        
        results = []
        for dist, idx in zip(distances[0], indices[0]):
            results.append({
                'text': self.combined_texts[idx],
                'similarity': float(dist),
                'data': self.combined_data[idx]
            })
        
        return results
    
    def get_nutrition_for_food(self, food_name, volume_ml):
        """
        Get complete nutrition information for a food item
        
        Args:
            food_name: Name of the food (e.g., "spaghetti")
            volume_ml: Volume in milliliters
            
        Returns:
            dict with mass, calories, density, sources
        """
        print(f"\n  Looking up nutrition for: {food_name} ({volume_ml:.1f}ml)")
        
        # Search for density
        density_results = self.search(food_name, k=3)
        density_matches = [r for r in density_results if r['data']['type'] == 'density']
        
        if density_matches:
            best_density = density_matches[0]['data']['data']
            density = best_density['density_g_per_ml']
            density_source = best_density.get('source', 'unknown')
            density_similarity = density_matches[0]['similarity']
        else:
            # Default density for unmatched foods
            density = 1.0
            density_source = 'default'
            density_similarity = 0.0
        
        # Calculate mass
        mass_g = volume_ml * density
        
        # Search for calories
        calorie_results = self.search(food_name, k=3)
        calorie_matches = [r for r in calorie_results if r['data']['type'] == 'calorie']
        
        calories_per_100g = None
        calorie_source = 'unknown'
        calorie_similarity = 0.0
        matched_food_name = 'unknown'

        if calorie_matches:
            best_calorie = calorie_matches[0]['data']['data']
            calories_per_100g = float(best_calorie['calories_per_100g'])
            calorie_source = best_calorie.get('source', 'unknown')
            calorie_similarity = float(calorie_matches[0]['similarity'])
            matched_food_name = str(best_calorie['food'])

        # If no calorie match or low-confidence, try Gemini total kcal fallback
        low_confidence = (not calorie_matches) or (calorie_similarity <= 0.5) or (matched_food_name == 'unknown')
        if (calories_per_100g is None or low_confidence) and self.gemini_available and mass_g > 0:
            try:
                print(f"    Attempting Gemini fallback for calories (food='{food_name}', mass={mass_g:.1f} g, match_conf={calorie_similarity:.2f})...")
                est_total_kcal = self._estimate_calories_with_gemini(food_name, mass_g, volume_ml, matched_food_name)
                if est_total_kcal is not None and est_total_kcal > 0:
                    calories_per_100g = (est_total_kcal / mass_g) * 100.0
                    calorie_source = 'gemini'
                    calorie_similarity = 1.0  # treat as authoritative for this fallback
                    matched_food_name = f"gemini:{food_name}"
                    print(f"    Gemini fallback used: ~{est_total_kcal:.0f} kcal for {mass_g:.1f} g → {calories_per_100g:.0f} kcal/100g")
                else:
                    print("    Gemini fallback returned no usable numeric value; retaining database/default calories.")
            except Exception as e:
                print(f"    Gemini fallback failed: {e}")

        # Final safety default if still missing
        if calories_per_100g is None:
            calories_per_100g = 150.0
            calorie_source = 'default'
            calorie_similarity = 0.0
            matched_food_name = 'unknown'
        
        # Calculate total calories
        total_calories = (mass_g / 100) * calories_per_100g
        
        return {
            'food_name': food_name,
            'volume_ml': volume_ml,
            'density_g_per_ml': density,
            'density_source': density_source,
            'density_similarity': density_similarity,
            'mass_g': mass_g,
            'calories_per_100g': calories_per_100g,
            'total_calories': total_calories,
            'calorie_source': calorie_source,
            'calorie_similarity': calorie_similarity,
            'matched_food': matched_food_name
        }

    def _estimate_calories_with_gemini(self, food_name: str, mass_g: float, volume_ml: float | None = None, matched_food: str | None = None) -> float | None:
        """
        Ask Gemini to estimate total calories for the given food and mass.
        Returns total kcal (float) or None.
        """
        if not self.gemini_available or self._gemini_model is None:
            return None
        # Build a concise, structured prompt
        qty_str = f"{mass_g:.0f} grams"
        if volume_ml and volume_ml > 0:
            qty_str += f" (~{volume_ml:.0f} ml)"
        # Heuristic: prefer cooked context
        base_name = matched_food if (matched_food and matched_food != 'unknown') else food_name
        refined = self._refine_food_label(base_name)

        def _attempt(prompt: str) -> float | None:
            try:
                resp = self._gemini_model.generate_content(prompt)
                text = (resp.text or "").strip()
                import re as _re
                m = _re.search(r"[-+]?[0-9]*\.?[0-9]+", text)
                if not m:
                    return None
                return float(m.group(0))
            except Exception:
                return None

        prompt1 = (
            "You are a nutrition assistant. Estimate the total calories (in kcal) for the given cooked food quantity.\n"
            "Respond with ONLY a number (no units, no text).\n\n"
            f"Food: {refined}\n"
            f"Quantity: {qty_str}\n"
            "If uncertain, provide your best typical-cooked-food estimate."
        )
        est = _attempt(prompt1)
        if est is not None and est > 0:
            return est
        # Retry with a more constrained prompt
        prompt2 = (
            "Return ONLY a numeric value (no units).\n"
            f"Total calories for {qty_str} of {refined}."
        )
        return _attempt(prompt2)
        try:
            resp = self._gemini_model.generate_content(prompt)
            text = (resp.text or "").strip()
            # Extract first number in response
            import re as _re
            m = _re.search(r"[-+]?[0-9]*\.?[0-9]+", text)
            if not m:
                return None
            return float(m.group(0))
        except Exception:
            return None


def analyze_meal_nutrition(volume_json_path, output_path=None):
    """
    Analyze nutrition from volume estimation results
    
    Args:
        volume_json_path: Path to volume estimation JSON
        output_path: Optional path to save results
    """
    print("="*80)
    print("NUTRITION ANALYSIS WITH RAG")
    print("="*80)
    
    # Initialize RAG system
    rag_dir = Path("D:/Nutrition5k/Grounded-SAM-2/rag")
    rag = NutritionRAG(
        pdf_path=rag_dir / "ap815e.pdf",
        fndds_path=rag_dir / "FNDDS.xlsx",
        cofid_path=rag_dir / "CoFID.xlsx"
    )
    
    # Load databases
    rag.extract_density_from_pdf()
    rag.load_calorie_databases()
    rag.build_faiss_index()
    
    # Load volume data
    print(f"\nLoading volume estimates from {volume_json_path}...")
    with open(volume_json_path, 'r') as f:
        volume_data = json.load(f)
    
    # Process each food item
    nutrition_results = {
        'meal_summary': {},
        'items': []
    }
    
    total_volume = 0
    total_mass = 0
    total_calories = 0
    
    print("\n" + "="*80)
    print("NUTRITIONAL ANALYSIS")
    print("="*80)
    
    objects = volume_data.get('objects', volume_data)  # Handle different JSON structures
    
    for item_key, item_data in objects.items():
        # Extract label and volume
        if isinstance(item_data, dict):
            label = item_data.get('label', item_key)
            stats = item_data.get('statistics', {})
            max_volume = stats.get('max_volume_ml', 0)
        else:
            continue
        
        # Skip non-food/ambiguous items
        skip_keywords = ['plate', 'fork', 'knife', 'spoon', 'glass', 'cup', 'table', 'bowl', 'sprinkle', 'water', 'other plates']
        if any(keyword in label.lower() for keyword in skip_keywords):
            print(f"\n  Skipping non-food item: {label}")
            continue
        
        if max_volume < 5:  # Skip very small items
            print(f"\n  Skipping tiny item: {label} ({max_volume:.1f}ml)")
            continue
        
        # Get nutrition info
        nutrition = rag.get_nutrition_for_food(label, max_volume)
        nutrition_results['items'].append(nutrition)
        
        total_volume += max_volume
        total_mass += nutrition['mass_g']
        total_calories += nutrition['total_calories']
        
        # Print results
        print(f"\n  {label.upper()}")
        print(f"    Volume: {max_volume:.1f} ml")
        print(f"    Density: {nutrition['density_g_per_ml']:.2f} g/ml (from {nutrition['density_source']}, similarity: {nutrition['density_similarity']:.2f})")
        print(f"    Mass: {nutrition['mass_g']:.1f} g")
        print(f"    Matched to: '{nutrition['matched_food']}' (similarity: {nutrition['calorie_similarity']:.2f})")
        print(f"    Calories/100g: {nutrition['calories_per_100g']:.0f} kcal")
        print(f"    Total Calories: {nutrition['total_calories']:.0f} kcal")
    
    # Summary
    nutrition_results['meal_summary'] = {
        'total_volume_ml': total_volume,
        'total_mass_g': total_mass,
        'total_calories_kcal': total_calories,
        'num_items': len(nutrition_results['items'])
    }
    
    print("\n" + "="*80)
    print("MEAL SUMMARY")
    print("="*80)
    print(f"  Total Food Volume: {total_volume:.1f} ml")
    print(f"  Total Food Mass: {total_mass:.1f} g ({total_mass/1000:.2f} kg)")
    print(f"  Total Calories: {total_calories:.0f} kcal")
    print(f"  Number of Food Items: {len(nutrition_results['items'])}")
    print("="*80)
    
    # Save results
    if output_path is None:
        output_path = Path(volume_json_path).parent / f"nutrition_{Path(volume_json_path).stem}.json"
    
    with open(output_path, 'w') as f:
        json.dump(nutrition_results, f, indent=2)
    
    print(f"\nNutrition results saved to: {output_path}")
    
    return nutrition_results


if __name__ == "__main__":
    # Run on our Metric3D results
    volume_json = "D:/Nutrition5k/data/metric3d_results/volume_data_metric3d_WhatsApp Video 2025-09-10 at 05.16.56_9874c762.json"
    
    results = analyze_meal_nutrition(volume_json)

