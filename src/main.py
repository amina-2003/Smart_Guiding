from datetime import datetime
import os

from detection import traiter_video
# Détection environnement Colab
try:
    from google.colab.patches import cv2_imshow  # noqa: F401
    IN_COLAB = True
except ImportError:
    IN_COLAB = False
# ============ MAIN ============
if __name__ == "__main__":
    import os

    VIDEO_PATH = "../vieos/video15.mp4" 
    MODEL_PATH = "../models/assistive_yolo_best.pt"
    OUTPUT_PATH = "../videos/resultat_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".mp4"

    ACTIVER_VOIX = False
    VITESSE_VOIX = 180

    print("="*60)
    print("🦯 ASSISTANT VOCAL POUR NON-VOYANT")
    print("="*60)
    print(f"🔊 Synthèse vocale : {'ACTIVÉE' if ACTIVER_VOIX else 'DÉSACTIVÉE'}")
    print(f"⚡ Vitesse de parole : {VITESSE_VOIX}")
    print(f"📱 Environnement : {'Google Colab' if IN_COLAB else 'Local'}")
    print("="*60 + "\n")

    if not os.path.exists(VIDEO_PATH):
        print(f"❌ Vidéo introuvable : {VIDEO_PATH}")
        exit(1)

    if not os.path.exists(MODEL_PATH):
        print(f"❌ Modèle introuvable : {MODEL_PATH}")
        exit(1)

    traiter_video(VIDEO_PATH, MODEL_PATH, OUTPUT_PATH, afficher=True, vocal=ACTIVER_VOIX, vitesse_voix=VITESSE_VOIX)

