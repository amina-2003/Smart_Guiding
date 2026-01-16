import time
import threading
from queue import Queue

from utils import CATEGORIES
# Détection environnement Colab
try:
    from google.colab.patches import cv2_imshow
    IN_COLAB = True
except ImportError:
    IN_COLAB = False
# ============ VOIX ENGINE ============
class VoiceEngine:
    def __init__(self, activer=True, vitesse=180, volume=1.0):
        self.activer = activer and not IN_COLAB
        self.message_queue = Queue()
        self.engine = None
        self.thread = None
        
        if not self.activer:
            return
            
        try:
            import pyttsx3
            self.engine = pyttsx3.init()
            self.engine.setProperty('rate', vitesse)
            self.engine.setProperty('volume', volume)
            voices = self.engine.getProperty('voices')
            for voice in voices:
                if 'french' in voice.name.lower() or 'fr' in voice.id.lower():
                    self.engine.setProperty('voice', voice.id)
                    break
            self.thread = threading.Thread(target=self._worker, daemon=True)
            self.thread.start()
            print("🔊 Moteur vocal activé")
        except Exception as e:
            print(f"⚠️ Synthèse vocale désactivée: {e}")
            self.activer = False

    def _worker(self):
        while True:
            message = self.message_queue.get()
            if message is None:
                break
            try:
                self.engine.stop()
                self.engine.say(message)
                self.engine.runAndWait()
            except:
                pass
            finally:
                self.message_queue.task_done()

    def parler(self, message, priorite='moyenne'):
        if not self.activer: 
            return
        if priorite in ['critique', 'haute']:
            while not self.message_queue.empty():
                try: 
                    self.message_queue.get_nowait()
                    self.message_queue.task_done()
                except: 
                    break
        if self.message_queue.qsize() < 3:
            self.message_queue.put(message)

    def stop(self):
        if self.activer and self.thread:
            self.message_queue.put(None)
            self.thread.join(timeout=2)

# ============ ASSISTANT ============
class VoiceAssistant:
    def __init__(self):
        self.cooldown = {}
        self.frame_counter = 0
        self.last_crosswalk_time = 0
        self.last_crosswalk_state = None
        self.crosswalk_cooldown = 3.0
        self.mode_environnement = "exterieur"
        self.last_object_state = {}  # Mémoriser l'état de chaque objet

    def generer_instruction(self, analyse, obj_id, instructions=None, mode="exterieur"):
        """
        ❌ CORRIGÉ : instructions=[] → instructions=None (évite bug mutable)
        """
        if instructions is None:
            instructions = []
        
        current_time = time.time()
        self.frame_counter += 1
        
        obj = analyse['objet']
        pas = analyse['pas']
        direction_text = analyse['direction_text']
        direction_simple = analyse['direction_simple']
        pas_evitement = analyse['pas_evitement']
        evitement = analyse['direction_evitement']
        
        info = CATEGORIES.get(obj, {})
        
        # Cooldown adaptatif selon priorité
        cooldown_secondes = {
            'critique': 0.5,
            'haute': 1.5,
            'moyenne': 3.0,
            'info': 5.0
        }
        
        key = f"{obj_id}_{obj}"
        
        # Détection de changement d'état
        current_state = {
            'distance': pas,
            'direction': direction_simple,
            'sur_trajectoire': analyse.get('sur_trajectoire', False),
            'vitesse': analyse.get('vitesse', 'immobile')
        }
        
        state_changed = False
        if key in self.last_object_state:
            old_state = self.last_object_state[key]
            # Changement significatif de distance
            if abs(old_state['distance'] - current_state['distance']) >= 2:
                state_changed = True
            # Changement de direction
            if old_state['direction'] != current_state['direction']:
                state_changed = True
            # Changement sur trajectoire
            if old_state['sur_trajectoire'] != current_state['sur_trajectoire']:
                state_changed = True
            # Changement de vitesse
            if old_state['vitesse'] != current_state['vitesse']:
                state_changed = True
        else:
            state_changed = True  # Premier passage
        
        # Vérifier cooldown seulement si pas de changement d'état
        if key in self.cooldown:
            elapsed = current_time - self.cooldown[key]
            
            # Déterminer la priorité pour le cooldown
            if state_changed:
                # Si état a changé, utiliser un cooldown minimum de 1 sec quand même
                required_cooldown = 1.0
            else:
                # Sinon, utiliser le cooldown complet selon la priorité
                priorite_estimee = 'haute' if pas < 3 else 'moyenne'
                required_cooldown = cooldown_secondes.get(priorite_estimee, 5.0)
            
            if elapsed < required_cooldown:
                return None
        
        # Mettre à jour l'état SEULEMENT si on va générer un message
        self.last_object_state[key] = current_state
        
        priorite = 'moyenne'
        message = ""
        
        # === OBJETS D'INTÉRIEUR ===
        if info.get('interieur', False):
            result = self._traiter_objet_interieur(obj, info, analyse)
            if result is None:
                return None
            message, priorite = result
        
        # === CROSSWALK ===
        elif obj == 'crosswalk':
            # ⚠️ NOTE : La sécurité sera réévaluée après toutes les détections
            # On génère un message par défaut ici
            safe = evaluer_securite_passage_pieton(analyse, instructions)
            crosswalk_state_changed = (safe != self.last_crosswalk_state)
            
            if not crosswalk_state_changed and (current_time - self.last_crosswalk_time < self.crosswalk_cooldown):
                return None
            
            self.last_crosswalk_state = safe
            self.last_crosswalk_time = current_time
            
            if safe:
                message = f"Passage piéton {direction_text} à {pas} pas. Route dégagée. Vous pouvez traverser."
                priorite = 'haute'
            else:
                message = f"Attention ! Passage piéton {direction_text} à {pas} pas. Traversée dangereuse. Attendez."
                priorite = 'critique'
        
        # === FEUX ===
        elif obj == 'green_light':
            if pas < 100:
                message = f"STOP ! Feu vert pour voiture. N'avancez pas."
                priorite = 'critique'
            else:
                return None
        
        elif obj == 'red_light':
            if pas < 100:
                message = f"Feu rouge pour voiture devant vous. Les voitures sont en stop, vous pouvez traverser prudemment."
                priorite = 'haute'
            else:
                return None
        
        # === VÉHICULES ===
        elif info.get('type') == 'A':
            if analyse['sur_trajectoire']:
                if analyse['vitesse'] == 'rapide':
                    message = f"DANGER ! {obj.title()} {direction_text} à {pas} pas. Se rapproche rapidement. STOP !"
                    priorite = 'critique'
                elif analyse['vitesse'] in ['modere', 'lent']:
                    message = f"Attention, {obj} {direction_text} à {pas} pas. Il se déplace. Attendez."
                    priorite = 'haute'
                else:
                    message = f"Attention, {obj} {direction_text} à {pas} pas. Attendez."
                    priorite = 'haute'
            else:
                if pas < 5:
                    message = f"{obj.title()} {direction_text} à {pas} pas."
                    priorite = 'moyenne'
                else:
                    return None
        
        # === OBSTACLES FIXES ===
        elif info.get('type') == 'C':
            if pas < 4:
                message = f"{obj.replace('_', ' ').title()} devant à {pas} pas ! Contournez par la {evitement.upper()}, {pas_evitement} pas."
                priorite = 'haute'
            elif pas < 6:
                message = f"{obj.replace('_', ' ').title()} {direction_text} à {pas} pas."
                priorite = 'moyenne'
            else:
                return None
        
        # === PERSONNES ===
        elif obj == 'person':
            # Seulement alerter si vraiment sur le chemin ou très proche
            if direction_simple == 'devant' and analyse['sur_trajectoire'] and pas < 3:
                message = f"Personne devant vous à {pas} pas. Ralentissez."
                priorite = 'haute'
            elif direction_simple == 'devant' and pas < 2:
                message = f"Personne devant vous à {pas} pas."
                priorite = 'haute'
            elif pas < 1:
                # Seulement si VRAIMENT très proche (< 1m)
                message = f"Personne très proche {direction_text}."
                priorite = 'haute'
            elif direction_simple != 'devant' and pas < 3:
                # Personnes sur les côtés = priorité basse
                message = f"Personne {direction_text} à {pas} pas."
                priorite = 'info'
            else:
                return None
        
        # === ANIMAUX ===
        elif obj == 'dog':
            if pas < 4:
                message = f"Chien {direction_text} à {pas} pas. Soyez prudent."
                priorite = 'haute'
            elif pas < 6:
                message = f"Chien {direction_text} à {pas} pas."
                priorite = 'moyenne'
            else:
                return None
        
        # === VÉLOS ===
        elif obj == 'bicycle':
            if analyse['sur_trajectoire'] and analyse['vitesse'] != 'immobile':
                message = f"Vélo {direction_text} à {pas} pas. Il se déplace. Attendez."
                priorite = 'haute'
            elif pas < 4:
                message = f"Vélo {direction_text} à {pas} pas."
                priorite = 'moyenne'
            else:
                return None
        
        # === DÉFAUT ===
        else:
            if pas < 3:
                message = f"Obstacle {direction_text} à {pas} pas."
                priorite = 'moyenne'
            else:
                return None

        if message:
            self.cooldown[key] = current_time
            return {'message': message, 'priorite': priorite, 'doit_parler': True, 'priorite_initiale': priorite}
        return None
    
    def _traiter_objet_interieur(self, obj, info, analyse):
        """Traitement spécifique pour les objets d'intérieur"""
        pas = analyse['pas']
        direction_text = analyse['direction_text']
        evitement = analyse['direction_evitement']
        pas_evitement = analyse['pas_evitement']
        
        type_obj = info.get('type', '')
        
        # === GROS MOBILIER (Type G) ===
        if type_obj == 'G':
            if pas < 2:
                nom_objet = obj.replace('_', ' ').title()
                message = f"{nom_objet} devant à {pas} pas ! Contournez par la {evitement}, {pas_evitement} pas."
                priorite = 'haute'
            elif pas < 5:
                message = f"{obj.replace('_', ' ').title()} {direction_text} à {pas} pas."
                priorite = 'moyenne'
            else:
                return None, None
        
        # === PLANTES ET DÉCORATION (Type H) ===
        elif type_obj == 'H':
            if info.get('fragile', False) and pas < 2:
                message = f"Attention ! {obj.replace('_', ' ').title()} fragile {direction_text} à {pas} pas."
                priorite = 'haute'
            elif pas < 3:
                message = f"{obj.replace('_', ' ').title()} {direction_text} à {pas} pas."
                priorite = 'moyenne'
            else:
                return None, None
        
        # === ÉLECTROMÉNAGER - REPÈRES CUISINE (Type I) ===
        elif type_obj == 'I':
            piece = info.get('piece', 'cuisine')
            surface_ratio = analyse.get('surface_ratio', 0)
            if info.get('taille') == 'grand' and surface_ratio > 0.05:
                message = f"{obj.replace('_', ' ').title()} très proche {direction_text}. Attention."
                priorite = 'moyenne'
            if pas < 2:
                message = f"{obj.replace('_', ' ').title()} très proche {direction_text}. Vous êtes dans la {piece}."
                priorite = 'moyenne'
            elif pas < 4:
                message = f"{obj.replace('_', ' ').title()} {direction_text} à {pas} pas."
                priorite = 'info'
            
            else:
                return None, None
        
        # === ÉLECTRONIQUE - REPÈRES (Type J) ===
        elif type_obj == 'J':
            if pas < 3:
                piece = info.get('piece', 'pièce')
                message = f"{obj.replace('_', ' ').title()} {direction_text}. Vous êtes près du {piece}."
                priorite = 'info'
            else:
                return None, None
        
        # === PETITS OBJETS (Type K) ===
        elif type_obj == 'K':
            # Pas d'alerte pour petits objets sauf si très proche
            if pas < 1:
                message = f"{obj.replace('_', ' ').title()} très proche {direction_text}."
                priorite = 'info'
            else:
                return None, None
        
        else:
            return None, None
        
        return message, priorite
# ============ SÉCURITÉ CROSSWALK ============
def evaluer_securite_passage_pieton(crosswalk_analyse, all_instructions):
    """
    ⚠️ CORRIGÉ : Évalue si c'est sûr de traverser au passage piéton
    Vérifie TOUS les objets dans la scène, pas seulement instructions
    """
    crosswalk_distance = crosswalk_analyse.get('distance_m', 0)
    
    for inst in all_instructions:
        if inst['objet'] == crosswalk_analyse['objet']:
            continue  # Ignorer le crosswalk lui-même
        
        obj = inst['objet']
        info = CATEGORIES.get(obj, {})
        
        # Véhicule proche (dans les 15m) et se déplaçant
        if info.get('type') == 'A':
            if inst['distance_m'] <= 15:
                # Si le véhicule est en mouvement ou sur trajectoire
                if inst.get('vitesse', 'immobile') != 'immobile' or inst.get('sur_trajectoire', False):
                    return False
        
        # Feu rouge très proche (< 10m du crosswalk)
        if obj == 'red_light' and inst['distance_m'] <= 10:
            return False
    
    return True
