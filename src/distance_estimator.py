# ============ DISTANCE ============
def estimer_distance_reelle(bbox, frame_height, mode_environnement="exterieur"):
    x1, y1, x2, y2 = bbox
    bottom_y = y2
    normalized_y = bottom_y / frame_height
    if mode_environnement == "interieur":
        # 🌟 Estimation pour intérieur (pièces, mobilier)
        if normalized_y > 0.85: 
            return 0.5   # très proche
        elif normalized_y > 0.70: 
            return 1.0
        elif normalized_y > 0.55: 
            return 3.0
        elif normalized_y > 0.40: 
            return 4.0
        else: 
            return 5.0   # loin mais dans la pièce
    else:
        # 🌟 Estimation pour extérieur (rue, trottoir)
        if normalized_y > 0.85: 
            return 1.0
        elif normalized_y > 0.70: 
            return 2.0
        elif normalized_y > 0.55: 
            return 3.5
        elif normalized_y > 0.40: 
            return 6.0
        else: 
            return 10.0