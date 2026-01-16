import time
# ============ CATEGORIES DÉTAILLÉES ============
CATEGORIES = {
    # Véhicules motorisés (danger élevé, mouvement rapide)
    "car": {"type": "A", "mobile": True, "vitesse_type": "rapide", "danger_base": 0.95},
    "bus": {"type": "A", "mobile": True, "vitesse_type": "rapide", "danger_base": 0.95},
    "truck": {"type": "A", "mobile": True, "vitesse_type": "rapide", "danger_base": 0.95},
    "motorcycle": {"type": "A", "mobile": True, "vitesse_type": "rapide", "danger_base": 0.90},

    # Véhicules non motorisés (danger moyen, mouvement modéré)
    "bicycle": {"type": "B", "mobile": True, "vitesse_type": "modere", "danger_base": 0.70},
    "tricycle": {"type": "B", "mobile": True, "vitesse_type": "lent", "danger_base": 0.60},

    # Obstacles fixes sur la voie (danger collision)
    "pole": {"type": "C", "mobile": False, "contournable": "oui", "danger_base": 0.75},
    "tree": {"type": "C", "mobile": False, "contournable": "oui", "danger_base": 0.75},
    "fire_hydrant": {"type": "C", "mobile": False, "contournable": "oui", "danger_base": 0.70},
    "warning_column": {"type": "C", "mobile": False, "contournable": "oui", "danger_base": 0.70},
    "roadblock": {"type": "C", "mobile": False, "contournable": "oui", "danger_base": 0.80},
    "ashcan": {"type": "C", "mobile": False, "contournable": "oui", "danger_base": 0.65},
    "reflective_cone": {"type": "C", "mobile": False, "contournable": "oui", "danger_base": 0.60},

    # Éléments de navigation (information importante)
    "crosswalk": {"type": "D", "mobile": False, "navigation": True, "danger_base": 0.30},
    "blind_road": {"type": "D", "mobile": False, "navigation": True, "danger_base": 0.20},
    "sign": {"type": "D", "mobile": False, "navigation": True, "danger_base": 0.25},
    "red_light": {"type": "D", "mobile": False, "navigation": True, "danger_base": 0.90},
    "green_light": {"type": "D", "mobile": False, "navigation": True, "danger_base": 0.20},

    # Êtres vivants (comportement imprévisible - UNIVERSEL : intérieur ET extérieur)
    "person": {"type": "E", "mobile": True, "vitesse_type": "lent", "danger_base": 0.60, "universel": True},
    "dog": {"type": "E", "mobile": True, "vitesse_type": "modere", "danger_base": 0.50, "universel": True},

    # Mobilier urbain extérieur
    "chair": {"type": "F", "mobile": False, "contournable": "oui", "danger_base": 0.50},
    "bench": {"type": "F", "mobile": False, "contournable": "oui", "danger_base": 0.65},
    
    # ===== OBJETS D'INTÉRIEUR =====
    # Mobilier (obstacles de taille moyenne à grande)
    "couch": {"type": "G", "mobile": False, "interieur": True, "taille": "grand", "danger_base": 0.70},
    "bed": {"type": "G", "mobile": False, "interieur": True, "taille": "grand", "danger_base": 0.65},
    "dining table": {"type": "G", "mobile": False, "interieur": True, "taille": "moyen", "danger_base": 0.60},
    "toilet": {"type": "G", "mobile": False, "interieur": True, "taille": "moyen", "danger_base": 0.60},
    
    # Plantes et décoration (obstacles moyens)
    "potted plant": {"type": "H", "mobile": False, "interieur": True, "taille": "petit", "danger_base": 0.55},
    "vase": {"type": "H", "mobile": False, "interieur": True, "taille": "petit", "danger_base": 0.45, "fragile": True},
    
    # Électroménager (repères utiles en cuisine)
    "microwave": {"type": "I", "mobile": False, "interieur": True, "piece": "cuisine", "danger_base": 0.30},
    "oven": {"type": "I", "mobile": False, "interieur": True, "piece": "cuisine", "danger_base": 0.40},
    "toaster": {"type": "I", "mobile": False, "interieur": True, "piece": "cuisine", "danger_base": 0.25},
    "sink": {"type": "I", "mobile": False, "interieur": True, "piece": "cuisine/sdb", "danger_base": 0.35},
    "refrigerator": {"type": "I", "mobile": False, "interieur": True, "taille": "grand", "piece": "cuisine", "danger_base": 0.75},
    
    # Électronique (repères utiles)
    "tv": {"type": "J", "mobile": False, "interieur": True, "piece": "salon", "danger_base": 0.20},
    "laptop": {"type": "J", "mobile": True, "interieur": True, "taille": "petit", "danger_base": 0.15},
    
    # Petits objets (peu dangereux mais utiles comme repères)
    "book": {"type": "K", "mobile": True, "interieur": True, "taille": "petit", "danger_base": 0.10},
    "clock": {"type": "K", "mobile": False, "interieur": True, "taille": "petit", "danger_base": 0.10},
}

# ============ MODE ENVIRONNEMENT ============
MODE_EXTERIEUR = ["A", "B", "C", "D", "E", "F"]  # Types pertinents dehors
MODE_INTERIEUR = ["G", "H", "I", "J", "K"]       # Types pertinents dedans

def detecter_mode_environnement(detections):
    """Détecte si on est à l'intérieur ou à l'extérieur"""
    score_exterieur = 0
    score_interieur = 0
    
    for det in detections:
        class_name = det['class_name']
        info = CATEGORIES.get(class_name, {})
        type_obj = info.get('type', '')
        
        # Ignorer les objets universels (personnes, animaux)
        if info.get('universel', False):
            continue
        
        if type_obj in MODE_EXTERIEUR:
            score_exterieur += 1
        if type_obj in MODE_INTERIEUR:
            score_interieur += 1
    
    # Si beaucoup d'objets d'intérieur, on est dedans
    if score_interieur >= 2:
        return "interieur"
    elif score_exterieur >= 2:
        return "exterieur"
    else:
        return "mixte"  # Près d'une porte, terrasse, etc.

# ============ CONFIGURATION ============
CONFIDENCE_THRESHOLD = 0.65
CAMERA_HEIGHT = 1.5
CAMERA_FOV = 60

def distance_en_pas(distance_m):
    """
    ❌ CORRIGÉ : Arrondi au lieu de int() pour éviter sous-estimation
    """
    return max(1, round(distance_m / 0.7))

# ============ DIRECTION ============
def analyser_direction_detaillee(bbox, frame_width):
    x1, _, x2, _ = bbox
    centre_x = (x1 + x2)/2
    position = centre_x / frame_width
    if position < 0.25: return "très à gauche", "gauche", 2
    elif position < 0.40: return "à gauche", "gauche", 1
    elif position < 0.60: return "devant vous", "devant", 0
    elif position < 0.75: return "à droite", "droite", 1
    else: return "très à droite", "droite", 2
