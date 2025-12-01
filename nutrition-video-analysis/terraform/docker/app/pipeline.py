"""
Main Video Processing Pipeline
Orchestrates Florence-2, SAM2, Metric3D, and RAG for nutrition analysis
"""
import cv2
import torch
import numpy as np
from pathlib import Path
from PIL import Image
from typing import Dict, List, Tuple, Optional
import logging
import json
from datetime import datetime

logger = logging.getLogger(__name__)


class NutritionVideoPipeline:
    """
    Complete pipeline for video-based nutrition analysis
    """
    
    def __init__(self, model_manager, config):
        """
        Initialize pipeline with models and configuration
        
        Args:
            model_manager: ModelManager instance with loaded models
            config: Settings instance with configuration
        """
        self.models = model_manager
        self.config = config
        self.device = config.DEVICE
        
        # Task prompts for Florence-2
        self.TASK_PROMPTS = {
            "caption": "<CAPTION>",
            "detailed_caption": "<DETAILED_CAPTION>",
            "more_detailed_caption": "<MORE_DETAILED_CAPTION>"
        }
        
        # Calibration state
        self.calibration = {
            'pixels_per_cm': None,
            'calibrated': False
        }
    
    def process_video(self, video_path: Path, job_id: str) -> Dict:
        """
        Main entry point - process entire video
        
        Args:
            video_path: Path to input video
            job_id: Unique job identifier
            
        Returns:
            Complete results dictionary with tracking, volumes, and nutrition
        """
        logger.info(f"[{job_id}] Starting video processing: {video_path.name}")
        
        try:
            # Step 1: Load and prepare frames
            frames = self._load_frames(video_path)
            if not frames:
                raise ValueError("No frames loaded from video")
            
            logger.info(f"[{job_id}] Loaded {len(frames)} frames")
            
            # Step 2: Run tracking pipeline with depth
            tracking_results = self._run_tracking_pipeline(frames, job_id)
            
            # Step 3: Analyze nutrition
            nutrition_results = self._analyze_nutrition(tracking_results, job_id)
            
            # Step 4: Compile complete results
            final_results = {
                'job_id': job_id,
                'video_name': video_path.name,
                'timestamp': datetime.utcnow().isoformat(),
                'num_frames_processed': len(frames),
                'calibration': self.calibration,
                'tracking': tracking_results,
                'nutrition': nutrition_results,
                'status': 'completed'
            }
            
            logger.info(f"[{job_id}] ✓ Processing completed successfully")
            return final_results
            
        except Exception as e:
            logger.error(f"[{job_id}] Pipeline failed: {e}", exc_info=True)
            raise
    
    def _load_frames(self, video_path: Path) -> List[np.ndarray]:
        """Load and subsample frames from video"""
        cap = cv2.VideoCapture(str(video_path))
        
        if not cap.isOpened():
            raise ValueError(f"Could not open video: {video_path}")
        
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        logger.info(f"Video: {fps:.1f}fps, {total_frames} total frames")
        logger.info(f"Processing every {self.config.FRAME_SKIP} frames")
        
        frames = []
        frame_idx = 0
        frames_loaded = 0
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            if frame_idx % self.config.FRAME_SKIP == 0:
                # Resize frame
                aspect_ratio = frame.shape[0] / frame.shape[1]
                new_height = int(self.config.RESIZE_WIDTH * aspect_ratio)
                frame_resized = cv2.resize(frame, (self.config.RESIZE_WIDTH, new_height))
                frames.append(cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB))
                frames_loaded += 1
                
                # Check max_frames limit
                if self.config.MAX_FRAMES and frames_loaded >= self.config.MAX_FRAMES:
                    break
            
            frame_idx += 1
        
        cap.release()
        return frames
    
    def _run_tracking_pipeline(self, frames: List[np.ndarray], job_id: str) -> Dict:
        """
        Run complete tracking pipeline with depth estimation
        
        Returns:
            Dict with tracked objects and volume measurements
        """
        logger.info(f"[{job_id}] Running tracking pipeline...")
        
        # Get models
        florence_processor, florence_model = self.models.florence2
        video_predictor = self.models.sam2
        metric3d_model = self.models.metric3d
        
        # Prepare frame directory for SAM2
        frame_dir = self.config.OUTPUT_DIR / job_id / "frames_temp"
        frame_dir.mkdir(parents=True, exist_ok=True)
        
        # Save frames
        for idx, frame in enumerate(frames):
            frame_path = frame_dir / f"{idx:05d}.jpg"
            Image.fromarray(frame).save(frame_path)
        
        # Initialize SAM2 inference state
        inference_state = video_predictor.init_state(video_path=str(frame_dir))
        
        # Tracking state
        tracked_objects = {}
        next_object_id = 1
        colors = {}
        volume_history = {}
        current_window_start = 0
        
        # Process frames
        for frame_idx, frame in enumerate(frames):
            logger.debug(f"[{job_id}] Processing frame {frame_idx+1}/{len(frames)}")
            
            frame_pil = Image.fromarray(frame)
            
            # Periodic re-detection
            if frame_idx % self.config.DETECTION_INTERVAL == 0:
                logger.info(f"[{job_id}] Frame {frame_idx}: Re-detecting objects...")
                
                # Detect objects
                boxes, labels, caption = self._detect_objects_florence(
                    frame_pil, florence_processor, florence_model
                )
                
                if len(boxes) > 0:
                    # Match to existing objects
                    matched_mapping, unmatched_new = self._match_objects(
                        boxes, labels, tracked_objects
                    )
                    
                    # Reset SAM2 state
                    inference_state = video_predictor.init_state(video_path=str(frame_dir))
                    current_window_start = frame_idx
                    
                    # Update tracked objects
                    new_tracked_objects = {}
                    boxes_to_add = []
                    ids_to_add = []
                    
                    # Matched objects (keep old IDs)
                    for old_id, new_idx in matched_mapping.items():
                        tracked_objects[old_id]['box'] = boxes[new_idx]
                        tracked_objects[old_id]['label'] = labels[new_idx]
                        new_tracked_objects[old_id] = tracked_objects[old_id]
                        boxes_to_add.append(boxes[new_idx])
                        ids_to_add.append(old_id)
                    
                    # New objects (assign new IDs)
                    for new_idx in unmatched_new:
                        obj_id = next_object_id
                        next_object_id += 1
                        
                        color = np.random.randint(0, 255, size=3, dtype=np.uint8)
                        colors[obj_id] = color
                        
                        new_tracked_objects[obj_id] = {
                            'box': boxes[new_idx],
                            'label': labels[new_idx],
                            'color': color
                        }
                        
                        boxes_to_add.append(boxes[new_idx])
                        ids_to_add.append(obj_id)
                    
                    tracked_objects = new_tracked_objects
                    
                    # Add objects to SAM2
                    for i, obj_id in enumerate(ids_to_add):
                        box_sam = np.array([boxes_to_add[i]])
                        try:
                            video_predictor.add_new_points_or_box(
                                inference_state=inference_state,
                                frame_idx=frame_idx - current_window_start,
                                obj_id=obj_id,
                                box=box_sam,
                            )
                        except Exception as e:
                            logger.warning(f"Could not add object ID{obj_id}: {e}")
            
            # Propagate SAM2 masks
            if tracked_objects:
                video_segments = {}
                for out_frame_idx, out_obj_ids, out_mask_logits in video_predictor.propagate_in_video(inference_state):
                    video_segments[out_frame_idx] = {
                        out_obj_id: (out_mask_logits[i] > 0.0).cpu().numpy()
                        for i, out_obj_id in enumerate(out_obj_ids)
                    }
                
                # Get current frame's masks
                relative_idx = frame_idx - current_window_start
                if relative_idx in video_segments:
                    # Estimate depth
                    depth_map_meters = self._estimate_depth_metric3d(frame, metric3d_model)
                    
                    # Calculate volumes
                    for obj_id in video_segments[relative_idx]:
                        if obj_id in tracked_objects:
                            mask = video_segments[relative_idx][obj_id][0]
                            box = tracked_objects[obj_id]['box']
                            label = tracked_objects[obj_id]['label']
                            
                            # Calibrate if this is a plate
                            if not self.calibration['calibrated'] and 'plate' in label.lower():
                                self.calibration['pixels_per_cm'], _ = self._calibrate_from_plate(
                                    box, depth_map_meters, frame.shape[1]
                                )
                                self.calibration['calibrated'] = True
                            
                            # Calculate volume
                            volume_metrics = self._calculate_volume_metric3d(
                                mask, depth_map_meters, box, label
                            )
                            
                            # Store in history
                            if obj_id not in volume_history:
                                volume_history[obj_id] = []
                            
                            volume_history[obj_id].append({
                                'frame': frame_idx,
                                'volume_ml': volume_metrics['volume_ml'],
                                'height_cm': volume_metrics['avg_height_cm'],
                                'area_cm2': volume_metrics['surface_area_cm2']
                            })
                            
                            # Update tracked object box with SAM2's refined box
                            mask_coords = np.argwhere(mask)
                            if len(mask_coords) > 0:
                                y_min, x_min = mask_coords.min(axis=0)
                                y_max, x_max = mask_coords.max(axis=0)
                                tracked_objects[obj_id]['box'] = [x_min, y_min, x_max, y_max]
        
        # Compile results
        results = {
            'objects': {},
            'total_objects': len(tracked_objects)
        }
        
        for obj_id, obj_data in tracked_objects.items():
            if obj_id in volume_history and len(volume_history[obj_id]) > 0:
                history = volume_history[obj_id]
                volumes = [h['volume_ml'] for h in history]
                heights = [h['height_cm'] for h in history]
                areas = [h['area_cm2'] for h in history]
                
                results['objects'][f"ID{obj_id}_{obj_data['label']}"] = {
                    'label': obj_data['label'],
                    'statistics': {
                        'max_volume_ml': float(max(volumes)),
                        'median_volume_ml': float(np.median(volumes)),
                        'mean_volume_ml': float(np.mean(volumes)),
                        'max_height_cm': float(max(heights)),
                        'max_area_cm2': float(max(areas)),
                        'num_frames': len(history)
                    }
                }
        
        logger.info(f"[{job_id}] Tracked {len(tracked_objects)} objects")
        return results
    
    def _detect_objects_florence(self, image_pil, processor, model):
        """Detect objects using Florence-2"""
        # Generate caption
        caption_task = self.TASK_PROMPTS[self.config.caption_type]
        caption_results = self._run_florence2(caption_task, None, image_pil, processor, model)
        caption = caption_results[caption_task]
        
        # Phrase grounding
        grounding_results = self._run_florence2(
            '<CAPTION_TO_PHRASE_GROUNDING>', caption, image_pil, processor, model
        )
        grounding_data = grounding_results['<CAPTION_TO_PHRASE_GROUNDING>']
        
        boxes = np.array(grounding_data.get("bboxes", []))
        labels = grounding_data.get("labels", [])
        
        # Filter generic objects
        filtered_boxes = []
        filtered_labels = []
        for box, label in zip(boxes, labels):
            if label.lower() not in self.config.GENERIC_OBJECTS:
                box_area = (box[2] - box[0]) * (box[3] - box[1])
                if box_area >= self.config.MIN_BOX_AREA:
                    filtered_boxes.append(box)
                    filtered_labels.append(label)
        
        return np.array(filtered_boxes), filtered_labels, caption
    
    def _run_florence2(self, task_prompt, text_input, image, processor, model):
        """Run Florence-2 inference"""
        prompt = task_prompt if text_input is None else task_prompt + text_input
        inputs = processor(text=prompt, images=image, return_tensors="pt").to(self.device)
        
        with torch.no_grad():
            generated_ids = model.generate(
                input_ids=inputs["input_ids"],
                pixel_values=inputs["pixel_values"],
                max_new_tokens=1024,
                early_stopping=False,
                do_sample=False,
                num_beams=1,
                use_cache=False
            )
        
        generated_text = processor.batch_decode(generated_ids, skip_special_tokens=False)[0]
        parsed_answer = processor.post_process_generation(
            generated_text, task=task_prompt, image_size=(image.width, image.height)
        )
        return parsed_answer
    
    def _match_objects(self, new_boxes, new_labels, tracked_objects):
        """Match new detections to existing tracked objects"""
        matched_mapping = {}
        unmatched_new = list(range(len(new_boxes)))
        
        if not tracked_objects:
            return matched_mapping, unmatched_new
        
        # Simple IoU matching
        for new_idx, new_box in enumerate(new_boxes):
            best_iou = 0
            best_id = None
            
            for obj_id, obj_data in tracked_objects.items():
                old_box = obj_data['box']
                iou = self._compute_iou(new_box, old_box)
                
                if iou > best_iou and iou >= self.config.IOU_MATCH_THRESHOLD:
                    best_iou = iou
                    best_id = obj_id
            
            if best_id is not None:
                matched_mapping[best_id] = new_idx
                unmatched_new.remove(new_idx)
        
        return matched_mapping, unmatched_new
    
    def _compute_iou(self, box1, box2):
        """Compute Intersection over Union"""
        x1 = max(box1[0], box2[0])
        y1 = max(box1[1], box2[1])
        x2 = min(box1[2], box2[2])
        y2 = min(box1[3], box2[3])
        
        intersection = max(0, x2 - x1) * max(0, y2 - y1)
        area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
        area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
        union = area1 + area2 - intersection
        
        return intersection / union if union > 0 else 0
    
    def _estimate_depth_metric3d(self, frame_np, model):
        """Estimate depth using Metric3D (returns meters)"""
        rgb_input = torch.from_numpy(frame_np).permute(2, 0, 1).unsqueeze(0).float().to(self.device)
        
        with torch.no_grad():
            pred_depth, confidence, output_dict = model.inference({'input': rgb_input})
        
        depth_map_meters = pred_depth.squeeze().cpu().numpy()
        
        # Resize if needed
        if depth_map_meters.shape != frame_np.shape[:2]:
            depth_map_meters = cv2.resize(
                depth_map_meters, (frame_np.shape[1], frame_np.shape[0]),
                interpolation=cv2.INTER_LINEAR
            )
        
        return depth_map_meters
    
    def _calibrate_from_plate(self, plate_box, depth_map_meters, frame_width):
        """Calibrate pixel scale using plate"""
        x1, y1, x2, y2 = [int(v) for v in plate_box]
        plate_width_px = x2 - x1
        pixels_per_cm = plate_width_px / self.config.REFERENCE_PLATE_DIAMETER_CM
        
        plate_region = depth_map_meters[y1:y2, x1:x2]
        avg_plate_depth_m = np.median(plate_region[plate_region > 0])
        
        logger.info(f"Calibrated: {pixels_per_cm:.2f} px/cm, plate depth: {avg_plate_depth_m:.2f}m")
        return pixels_per_cm, avg_plate_depth_m
    
    def _calculate_volume_metric3d(self, mask, depth_map_meters, box, label):
        """Calculate volume using metric depth (implementation from test_tracking_metric3d.py)"""
        # This is a simplified version - full implementation in the original file
        mask_bool = mask.astype(bool)
        depth_values_m = depth_map_meters[mask_bool]
        
        if len(depth_values_m) == 0 or not self.calibration['calibrated']:
            return {'volume_ml': 0.0, 'avg_height_cm': 0.0, 'surface_area_cm2': 0.0}
        
        pixel_count = mask_bool.sum()
        pixels_per_cm = self.calibration['pixels_per_cm']
        surface_area_cm2 = pixel_count / (pixels_per_cm ** 2)
        
        valid_depths = depth_values_m[depth_values_m > 0]
        if len(valid_depths) == 0:
            return {'volume_ml': 0.0, 'avg_height_cm': 0.0, 'surface_area_cm2': surface_area_cm2}
        
        # Height calculation (simplified - see original for full logic)
        base_depth_m = np.percentile(valid_depths, 75)
        top_depth_m = np.percentile(valid_depths, 15)
        height_cm = max(0, (base_depth_m - top_depth_m) * 100)
        
        # Object-specific constraints (simplified)
        label_lower = label.lower()
        if 'plate' in label_lower:
            height_cm = min(height_cm, 2.5) if height_cm > 5 else max(height_cm, 1.5)
        elif any(word in label_lower for word in ['glass', 'cup']):
            height_cm = max(height_cm, 8) if height_cm < 3 else min(height_cm, 15)
        
        volume_ml = surface_area_cm2 * height_cm
        
        return {
            'volume_ml': float(volume_ml),
            'avg_height_cm': float(height_cm),
            'surface_area_cm2': float(surface_area_cm2)
        }
    
    def _analyze_nutrition(self, tracking_results, job_id):
        """Run nutrition analysis using RAG system"""
        logger.info(f"[{job_id}] Running nutrition analysis...")
        
        rag = self.models.rag
        
        skip_keywords = ['plate', 'fork', 'knife', 'spoon', 'glass', 'cup', 'table', 'bowl', 'water', 'sprinkle']
        
        nutrition_items = []
        total_food_volume = 0
        total_mass = 0
        total_calories = 0
        
        for item_key, item_data in tracking_results['objects'].items():
            label = item_data['label']
            max_volume = item_data['statistics']['max_volume_ml']
            
            # Skip non-food items
            if any(keyword in label.lower() for keyword in skip_keywords):
                continue
            
            if max_volume < 10:  # Skip tiny items
                continue
            
            # Get nutrition info
            nutrition = rag.get_nutrition_for_food(label, max_volume)
            nutrition_items.append(nutrition)
            
            total_food_volume += max_volume
            total_mass += nutrition['mass_g']
            total_calories += nutrition['total_calories']
        
        return {
            'items': nutrition_items,
            'summary': {
                'total_food_volume_ml': total_food_volume,
                'total_mass_g': total_mass,
                'total_calories_kcal': total_calories,
                'num_food_items': len(nutrition_items)
            }
        }

