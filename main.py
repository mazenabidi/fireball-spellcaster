import ctypes
import os
import sys

# Monkey-patch mediapipe's mediapipe_c_bindings to fix the 'free' function issue on Windows
def patch_mediapipe_c_bindings():
    # Find the module path
    import importlib.util
    spec = importlib.util.find_spec('mediapipe.tasks.python.core.mediapipe_c_bindings')
    if spec and spec.origin:
        # Read the original file
        with open(spec.origin, 'r') as f:
            original_code = f.read()
        
        # Replace the problematic part
        patched_code = original_code.replace(
            '  # Register "free()"\n  _shared_lib.free.argtypes = [ctypes.c_void_p]\n  _shared_lib.free.restype = None',
            '''  # Register "free()"
  if os.name == 'nt':
    # On Windows, free is in msvcrt.dll
    msvcrt = ctypes.CDLL('msvcrt.dll')
    _shared_lib.free = msvcrt.free
  _shared_lib.free.argtypes = [ctypes.c_void_p]
  _shared_lib.free.restype = None'''
        )
        
        # Create a temporary module and execute the patched code
        module = sys.modules.setdefault('mediapipe.tasks.python.core.mediapipe_c_bindings', type(sys)('mediapipe.tasks.python.core.mediapipe_c_bindings'))
        exec(patched_code, module.__dict__)

# Apply the patch before importing mediapipe
patch_mediapipe_c_bindings()

import cv2
import mediapipe as mp
import numpy as np
import time
from collections import deque
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

class FireballSpellcaster:
    def __init__(self):
        base_options = python.BaseOptions(model_asset_path='hand_landmarker.task')
        options = vision.HandLandmarkerOptions(
            base_options=base_options,
            num_hands=1,
            min_hand_detection_confidence=0.7,
            min_hand_presence_confidence=0.5,
            min_tracking_confidence=0.5
        )
        self.detector = vision.HandLandmarker.create_from_options(options)
        
        self.cap = cv2.VideoCapture(0)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        self.charging = False
        self.charge_start_time = 0
        self.charge_time = 2.0
        self.fireballs = []
        self.previous_landmarks = None
        self.previous_time = time.time()
        
    def get_finger_state(self, landmarks):
        finger_tips = [8, 12, 16, 20]
        finger_pips = [6, 10, 14, 18]
        
        fingers_up = []
        
        if landmarks[4].x < landmarks[3].x:
            fingers_up.append(1)
        else:
            fingers_up.append(0)
            
        for tip, pip in zip(finger_tips, finger_pips):
            if landmarks[tip].y < landmarks[pip].y:
                fingers_up.append(1)
            else:
                fingers_up.append(0)
                
        return fingers_up
    
    def detect_charging_pose(self, fingers_up):
        return fingers_up == [0, 1, 0, 0, 0]
    
    def detect_open_palm(self, fingers_up):
        return fingers_up == [1, 1, 1, 1, 1]
    
    def calculate_hand_velocity(self, current_landmarks):
        if self.previous_landmarks is None:
            return 0, 0
        
        index_tip_current = current_landmarks[8]
        index_tip_prev = self.previous_landmarks[8]
        
        dx = (index_tip_current.x - index_tip_prev.x) * self.width
        dy = (index_tip_current.y - index_tip_prev.y) * self.height
        dt = time.time() - self.previous_time
        
        if dt == 0:
            return 0, 0
        
        return dx / dt, dy / dt
    
    def draw_fireball_charge(self, frame, center, charge_percent):
        base_radius = 20
        max_radius = 80
        radius = int(base_radius + (max_radius - base_radius) * charge_percent)
        
        for i in range(3, 0, -1):
            alpha = 0.3 + 0.2 * i
            overlay = frame.copy()
            color = (0, 100 + int(50 * i), 200 + int(55 * i))
            cv2.circle(overlay, center, int(radius * (0.5 + 0.2 * i)), color, -1)
            cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
        
        if charge_percent > 0.3:
            spark_count = int(8 * charge_percent)
            for _ in range(spark_count):
                angle = np.random.uniform(0, 2 * np.pi)
                dist = radius + np.random.randint(5, 30)
                sx = int(center[0] + dist * np.cos(angle))
                sy = int(center[1] + dist * np.sin(angle))
                spark_radius = np.random.randint(2, 6)
                cv2.circle(frame, (sx, sy), spark_radius, (0, 200, 255), -1)
    
    def release_fireball(self, center, velocity, charge_percent):
        fireball = {
            'x': center[0],
            'y': center[1],
            'vx': velocity[0] * 0.3,
            'vy': velocity[1] * 0.3,
            'radius': 30 + int(50 * charge_percent),
            'life': 1.0,
            'trail': deque(maxlen=20)
        }
        self.fireballs.append(fireball)
    
    def update_and_draw_fireballs(self, frame):
        fireballs_to_remove = []
        
        for idx, fireball in enumerate(self.fireballs):
            fireball['x'] += fireball['vx']
            fireball['y'] += fireball['vy']
            fireball['life'] -= 0.02
            fireball['trail'].append((int(fireball['x']), int(fireball['y'])))
            
            if fireball['life'] <= 0 or fireball['x'] < -100 or fireball['x'] > self.width + 100 or fireball['y'] < -100 or fireball['y'] > self.height + 100:
                fireballs_to_remove.append(idx)
                continue
            
            for i, (x, y) in enumerate(fireball['trail']):
                trail_alpha = (i / len(fireball['trail'])) * fireball['life']
                trail_radius = int(fireball['radius'] * (i / len(fireball['trail'])) * 0.5)
                if trail_radius > 0:
                    overlay = frame.copy()
                    cv2.circle(overlay, (x, y), trail_radius, (0, 150, 255), -1)
                    cv2.addWeighted(overlay, trail_alpha * 0.5, frame, 1 - trail_alpha * 0.5, 0, frame)
            
            radius = int(fireball['radius'] * fireball['life'])
            for i in range(3, 0, -1):
                alpha = 0.4 * fireball['life']
                overlay = frame.copy()
                color = (0, 100 + int(50 * i), 200 + int(55 * i))
                cv2.circle(overlay, (int(fireball['x']), int(fireball['y'])), int(radius * (0.5 + 0.2 * i)), color, -1)
                cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
        
        for idx in reversed(fireballs_to_remove):
            self.fireballs.pop(idx)
    
    def draw_landmarks(self, frame, landmarks):
        connections = [
            (0, 1), (1, 2), (2, 3), (3, 4),
            (0, 5), (5, 6), (6, 7), (7, 8),
            (5, 9), (9, 10), (10, 11), (11, 12),
            (9, 13), (13, 14), (14, 15), (15, 16),
            (13, 17), (17, 18), (18, 19), (19, 20),
            (0, 17)
        ]
        
        for connection in connections:
            start_idx, end_idx = connection
            start = (int(landmarks[start_idx].x * self.width), int(landmarks[start_idx].y * self.height))
            end = (int(landmarks[end_idx].x * self.width), int(landmarks[end_idx].y * self.height))
            cv2.line(frame, start, end, (255, 0, 0), 2)
        
        for i in range(21):
            x = int(landmarks[i].x * self.width)
            y = int(landmarks[i].y * self.height)
            cv2.circle(frame, (x, y), 5, (0, 255, 0), -1)
    
    def run(self):
        while True:
            ret, frame = self.cap.read()
            if not ret:
                break
            
            frame = cv2.flip(frame, 1)
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
            
            detection_result = self.detector.detect(mp_image)
            
            if detection_result.hand_landmarks:
                for hand_landmarks in detection_result.hand_landmarks:
                    self.draw_landmarks(frame, hand_landmarks)
                    
                    fingers_up = self.get_finger_state(hand_landmarks)
                    
                    index_tip = hand_landmarks[8]
                    x, y = int(index_tip.x * self.width), int(index_tip.y * self.height)
                    
                    if self.detect_charging_pose(fingers_up):
                        if not self.charging:
                            self.charging = True
                            self.charge_start_time = time.time()
                        
                        charge_elapsed = time.time() - self.charge_start_time
                        charge_percent = min(charge_elapsed / self.charge_time, 1.0)
                        
                        self.draw_fireball_charge(frame, (x, y), charge_percent)
                        
                        cv2.putText(frame, f"Charging: {int(charge_percent * 100)}%", (50, 100),
                                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 200, 255), 2)
                    else:
                        if self.charging:
                            charge_elapsed = time.time() - self.charge_start_time
                            charge_percent = min(charge_elapsed / self.charge_time, 1.0)
                            
                            if charge_percent > 0.3:
                                vx, vy = self.calculate_hand_velocity(hand_landmarks)
                                if abs(vx) > 50 or abs(vy) > 50 or self.detect_open_palm(fingers_up):
                                    self.release_fireball((x, y), (vx, vy), charge_percent)
                            
                            self.charging = False
                    
                    self.previous_landmarks = hand_landmarks
                    self.previous_time = time.time()
            
            self.update_and_draw_fireballs(frame)
            
            cv2.imshow('Gesture Spellcasting - Fireball', frame)
            
            if cv2.waitKey(1) & 0xFF == 27:
                break
        
        self.cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    spellcaster = FireballSpellcaster()
    spellcaster.run()
