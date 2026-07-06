# Duck Egg Candling Dataset Collector

## Overview
This repository contains a custom Python-based graphical user interface designed for the precise hardware-level control of UVC camera modules (specifically tested with the IMX179 8MP sensor). 

This application was developed to facilitate high-fidelity, standardized data collection for thesis research on duck egg candling. Because candling requires analyzing internal egg structures (such as blood vessels and embryo development) via transmitted light, standard auto-exposure and auto-focus algorithms often fail. This tool bypasses automated camera processing, granting the researcher absolute manual control over the sensor's physical properties to ensure every captured image in the dataset is perfectly exposed, sharply focused, and consistent.

## Key Features

### Hardware Control
- DirectShow (Windows) backend integration for low-level UVC hardware access.
- Manual tuning sliders for Focus, Exposure (Shutter), Brightness, Contrast, Gain, and Sharpness.
- White Balance color temperature control (2800K - 6500K).
- Hardware mode switches to toggle Auto Focus, Auto Exposure, and Auto White Balance.
- Native driver dialog integration for accessing advanced, camera-specific firmware settings.

### Performance and Architecture
- Threaded background video loop to prevent GUI freezing during high-resolution capture.
- Thread-safe property queueing to prevent OpenCV crashes when rapidly adjusting hardware sliders.
- Optimized preview rendering using OpenCV's C++ backend for real-time scaling without aspect ratio distortion.

### Dataset Management
- Automated directory structuring based on class labels.
- Metadata tagging: Images are saved with Batch IDs, timestamps, and sequential counters.
- Class definitions tailored for candling: Fertile, Infertile, and Abnormal.
- Lossless image saving (100% JPEG quality) to preserve internal structural details for machine learning pipelines.

## Pre-trained Model Weights

The pre-trained YOLOv8 weights used for inference in this research are not included in this repository to maintain a lightweight codebase. 

You can download the trained model weights here:
- [Download YOLOv8 Candling Model (best.pt)](LINK_TO_YOUR_RELEASE_OR_DRIVE)

To run inference using the downloaded weights:
```python
from ultralytics import YOLO
model = YOLO("path/to/downloaded/best.pt")
results = model.predict(source="candling_dataset/infertile/")
