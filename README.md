# Smart_Guiding - AI Assistant for Visually Impaired Users
An intelligent assistant that guides visually impaired users through their environment using computer vision and voice synthesis.

## Description
This project is an AI-powered voice assistant designed to help visually impaired users navigate safely. 
It uses computer vision to detect obstacles, vehicles, crosswalks, and indoor objects in video streams 
and generates real-time voice instructions to guide the user.

## Features
- Real-time object detection with YOLOv8
- Custom dataset combining COCO classes and a Roboflow dataset
- Indoor/outdoor environment detection
- Dynamic distance and direction estimation
- Voice instructions for safe navigation
- Tracking moving objects and alert prioritization
- Crosswalk safety evaluation
- Works with video input (camera or pre-recorded)

## Installation
1. Clone the repository:
   ```bash
   git clone https://github.com/amina-2003/smart-guiding.git
   cd smart-guiding
