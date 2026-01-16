import math
import cv2
from ultralytics import YOLO

from utils import (
    CATEGORIES,
    CONFIDENCE_THRESHOLD,
    detecter_mode_environnement,
    analyser_direction_detaillee,
    distance_en_pas,
)
from distance_estimator import estimer_distance_reelle
from voice_assistance import evaluer_securite_passage_pieton , VoiceAssistant, VoiceEngine ,IN_COLAB
# ============ TRACKER ============
class ObjectTracker:
    def __init__(self, max_age=10):
        self.tracked_objects = {}
        self.next_id = 0
        self.max_age = max_age

    def update(self, detections):
        current_frame_ids = set()
        for det in detections:
            bbox = det['bbox']
            class_name = det['class_name']
            matched_id = self._find_match(bbox, class_name)
            if matched_id is not None:
                self.tracked_objects[matched_id]['positions'].append(bbox)
                self.tracked_objects[matched_id]['age'] = 0
                self.tracked_objects[matched_id]['last_seen'] = det
                current_frame_ids.add(matched_id)
            else:
                self.tracked_objects[self.next_id] = {
                    'class_name': class_name,
                    'positions': [bbox],
                    'age': 0,
                    'last_seen': det
                }
                current_frame_ids.add(self.next_id)
                self.next_id += 1

        # Vieillir objets non vus
        for obj_id in list(self.tracked_objects.keys()):
            if obj_id not in current_frame_ids:
                self.tracked_objects[obj_id]['age'] += 1
                if self.tracked_objects[obj_id]['age'] > self.max_age:
                    del self.tracked_objects[obj_id]

    def _find_match(self, bbox, class_name):
        x1, y1, x2, y2 = bbox
        center = ((x1 + x2) / 2, (y1 + y2) / 2)
        best_match = None
        min_distance = float('inf')
        for obj_id, obj in self.tracked_objects.items():
            if obj['class_name'] != class_name:
                continue
            last_bbox = obj['positions'][-1]
            lx1, ly1, lx2, ly2 = last_bbox
            last_center = ((lx1 + lx2) / 2, (ly1 + ly2) / 2)
            distance = math.sqrt((center[0]-last_center[0])**2 + (center[1]-last_center[1])**2)
            if distance < min_distance and distance < 100:
                min_distance = distance
                best_match = obj_id
        return best_match

    def get_velocity(self, obj_id):
        if obj_id not in self.tracked_objects:
            return 0, 0
        positions = self.tracked_objects[obj_id]['positions']
        if len(positions) < 2:
            return 0, 0
        recent = positions[-5:]
        x1_start, y1_start, x2_start, y2_start = recent[0]
        x1_end, y1_end, x2_end, y2_end = recent[-1]
        center_start = ((x1_start + x2_start)/2, (y1_start+y2_start)/2)
        center_end = ((x1_end + x2_end)/2, (y1_end+y2_end)/2)
        vx = (center_end[0]-center_start[0])/len(recent)
        vy = (center_end[1]-center_start[1])/len(recent)
        return vx, vy
# ============ ANALYSE SCENE ============
def analyser_scene_complete(detections, tracker, frame_width, frame_height, voice_assistant):
    instructions = []
    tracker.update(detections)
    
    # Détecter le mode environnement (intérieur/extérieur)
    mode = detecter_mode_environnement(detections)
    voice_assistant.mode_environnement = mode
    
    for det in detections:
        bbox = det['bbox']
        # 🔹 Taille visuelle de l'objet dans l'image
        box_area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
        frame_area = frame_width * frame_height
        surface_ratio = box_area / frame_area
        class_name = det['class_name']
        conf = det['confidence']
        info = CATEGORIES.get(class_name, {})

        distance_m = estimer_distance_reelle(bbox, frame_height,mode_environnement=mode)
        pas = distance_en_pas(distance_m)
        direction_text, direction_simple, pas_evitement = analyser_direction_detaillee(bbox, frame_width)

        # Trouver l'ID de tracking
        # ❌ CORRIGÉ : Ne pas comparer bbox directement (instable)
        obj_id = None
        min_dist = float('inf')
        for tid, tobj in tracker.tracked_objects.items():
            if tobj['class_name'] != class_name:
                continue
            last_bbox = tobj['last_seen']['bbox']
            # Calculer distance entre centres
            lx1, ly1, lx2, ly2 = last_bbox
            last_center = ((lx1 + lx2) / 2, (ly1 + ly2) / 2)
            cx, cy = (bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2
            dist = math.sqrt((cx - last_center[0])**2 + (cy - last_center[1])**2)
            if dist < min_dist and dist < 50:  # Seuil de matching
                min_dist = dist
                obj_id = tid

        # Vitesse
        vx, vy = 0, 0
        vitesse_categorie = 'immobile'
        sur_trajectoire = False
        
        if info.get('mobile', False) and obj_id is not None:
            vx, vy = tracker.get_velocity(obj_id)
            vitesse_mag = math.sqrt(vx**2 + vy**2)
            
            # ❌ CORRIGÉ : Vitesse basée sur magnitude, pas vy seul
            if vitesse_mag > 15: 
                vitesse_categorie = 'rapide'
            elif vitesse_mag > 5: 
                vitesse_categorie = 'modere'
            elif vitesse_mag > 1: 
                vitesse_categorie = 'lent'
            
            # ⚠️ CORRIGÉ : sur_trajectoire basé sur direction + vitesse
            # Un objet est sur trajectoire s'il est devant ET se déplace vers nous (vy > 0)
            if direction_simple == 'devant' and vy > 3 and vitesse_mag > 2:
                sur_trajectoire = True

        # ⚠️ CORRIGÉ : Direction d'évitement intelligente
        if direction_simple == 'gauche':
            direction_evitement = 'droite'
        elif direction_simple == 'droite':
            direction_evitement = 'gauche'
        else:  # devant
            # Choisir le côté le plus dégagé (pour l'instant, par défaut droite)
            direction_evitement = 'droite'

        analyse = {
            'objet': class_name,
            'confidence': conf,
            'bbox': bbox,
            'distance_m': distance_m,
            'pas': pas,
            'direction_text': direction_text,
            'direction_simple': direction_simple,
            'direction_evitement': direction_evitement,
            'pas_evitement': pas_evitement,
            'vitesse': vitesse_categorie,
            'sur_trajectoire': sur_trajectoire,
            'mobile': info.get('mobile', False),
            'surface_ratio': surface_ratio,
            'priorite': 'moyenne'
        }

        instruction = voice_assistant.generer_instruction(analyse, obj_id or hash(str(bbox)), instructions, mode)
        if instruction:
            analyse.update(instruction)
            instructions.append(analyse)

    # ⚠️ CORRIGÉ : Évaluer sécurité crosswalk APRÈS avoir toutes les détections
    # Re-parcourir les crosswalks pour mettre à jour leur statut
    for inst in instructions:
        if inst['objet'] == 'crosswalk':
            safe = evaluer_securite_passage_pieton(inst, instructions)
            # Mettre à jour le message selon la sécurité
            if safe:
                inst['message'] = f"Passage piéton {inst['direction_text']} à {inst['pas']} pas. Route dégagée. Vous pouvez traverser."
                inst['priorite'] = 'haute'
            else:
                inst['message'] = f"Attention ! Passage piéton {inst['direction_text']} à {inst['pas']} pas. Traversée dangereuse. Attendez."
                inst['priorite'] = 'critique'

    # Garder seulement le crosswalk le plus proche
    crosswalks = [inst for inst in instructions if inst['objet'] == 'crosswalk']
    if len(crosswalks) > 1:
        closest = min(crosswalks, key=lambda x: x['distance_m'])
        instructions = [inst for inst in instructions if inst['objet'] != 'crosswalk']
        instructions.append(closest)

    # Trier par priorité puis distance
    priority_order = {'critique': 0, 'haute': 1, 'moyenne': 2, 'info': 3}
    
    # Filtrer les messages 'info' s'il y a des messages plus importants
    has_important = any(inst['priorite'] in ['critique', 'haute', 'moyenne'] for inst in instructions)
    if has_important:
        instructions = [inst for inst in instructions if not inst['priorite'] == 'info']
    instructions.sort(key=lambda x: (priority_order.get(x['priorite'], 4), x['pas']))

    return instructions, mode

# ============ TRAITEMENT VIDÉO ============
def traiter_video(video_path, model_path, output_path, afficher=True, vocal=False, vitesse_voix=180):
    print("🔄 Initialisation...")
    yolo_model = YOLO(model_path)
    tracker = ObjectTracker(max_age=15)
    voice_assistant = VoiceAssistant()
    voice_engine = VoiceEngine(activer=vocal, vitesse=vitesse_voix)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"❌ Impossible d'ouvrir : {video_path}")
        return

    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = int(cap.get(cv2.CAP_PROP_FPS))

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps, (frame_width, frame_height))

    COLORS = {
        'critique': (0, 0, 255),
        'haute': (0, 140, 255),
        'moyenne': (0, 255, 255),
        'info': (255, 255, 255)
    }

    frame_count = 0
    print("🚀 Traitement en cours...\n")

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        frame_count += 1

        # Détection YOLO
        results = yolo_model(frame, verbose=False, conf=CONFIDENCE_THRESHOLD)

        # Préparer détections
        detections = []
        for result in results:
            for box in result.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                conf = float(box.conf[0])
                cls = int(box.cls[0])
                class_name = yolo_model.names[cls]

                if class_name in CATEGORIES:
                    detections.append({
                        'bbox': (x1, y1, x2, y2),
                        'confidence': conf,
                        'class_name': class_name
                    })

        # Analyse complète
        instructions, mode = analyser_scene_complete(detections, tracker, frame_width, frame_height, voice_assistant)
        
        

        # Affichage (max 5 messages, mais prioriser critique/haute)
        y_offset = 30
        messages_prononces = 0
        messages_affiches = 0
        
        # ⚠️ CORRIGÉ : Éviter flood vocal - un seul message vocal par frame
        # Séparer par priorité
        critiques_hautes = [inst for inst in instructions if inst.get('priorite') in ['critique', 'haute']]
        autres = [inst for inst in instructions if inst.get('priorite') not in ['critique', 'haute']]
        
        # Afficher d'abord les critiques/hautes (max 3), puis les autres (max 2)
        messages_a_afficher = critiques_hautes[:3] + autres[:2]
        
        for inst in messages_a_afficher:
            if inst.get('doit_parler', False) or inst.class_name in ['red_light', 'green_light']:
                color = COLORS.get(inst['priorite'], (255, 255, 255))
                message = inst['message']
                
                # Afficher à l'écran
                cv2.putText(frame, message, (10, y_offset),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
                y_offset += 30
                messages_affiches += 1

                # Bbox
                bbox = inst['bbox']
                cv2.rectangle(frame, (bbox[0], bbox[1]), (bbox[2], bbox[3]), color, 3)

                # ⚠️ CORRIGÉ : UN SEUL message vocal par frame maximum
                # Prononcer SEULEMENT le premier message critique/haute
                if inst['priorite'] in ['critique', 'haute'] and messages_prononces == 0:
                    message_propre = message.replace('⚠️', '').replace('🚦', '').replace('✅', '').strip()
                    voice_engine.parler(message_propre, inst['priorite'])
                    messages_prononces += 1
                    print(f"[Frame {frame_count}] 🔊 {message_propre}")

        out.write(frame)

        # Affichage selon environnement
        if afficher and not IN_COLAB:
            display = cv2.resize(frame, (1280, 720))
            cv2.imshow('Assistant Non-Voyant', display)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        elif IN_COLAB and frame_count % 60 == 0:
            print(f"📍 Frame {frame_count}")
            display = cv2.resize(frame, (960, 540))
            cv2_imshow(display)

    cap.release()
    out.release()
    if not IN_COLAB:
        cv2.destroyAllWindows()
    voice_engine.stop()

    print(f"\n✅ Terminé ! Vidéo : {output_path}")
    
    if IN_COLAB:
        print(f"\n💾 Pour télécharger :")
        print(f"   from google.colab import files")
        print(f"   files.download('{output_path}')")
