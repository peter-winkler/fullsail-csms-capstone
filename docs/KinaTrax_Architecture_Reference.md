# KinaTrax Development Repository & Container Processing Architecture

**Generated:** January 2026
**Purpose:** Reference documentation for capstone cloud containerization project

---

## Executive Summary

KinaTrax is a sophisticated biomechanical analysis system for sports performance tracking (primarily baseball). It consists of:

1. **Core System**: A complex C++ application built with Visual Studio (Windows native) that handles motion capture, video processing, and skeletal tracking
2. **Linux Containerization**: Multiple branches for containerized processing using CMake-based builds
3. **Cloud Processing Pipeline**: Event Queue API (Python) that orchestrates distributed processing across multiple cloud containers
4. **Dependencies**: 40+ third-party libraries including OpenCV, TensorFlow, Qt, VTK, PCL, and hardware SDKs

---

## Repository Locations

| Component | Location |
|-----------|----------|
| Main Windows Project | `<WORK_DIR>/KinaTrax/` |
| Main Development Repo | `<WORK_DIR>/KinaTrax_development/` |
| Linux Builds | `<WORK_DIR>/container-processing-branches/` |
| Container Setup | `<WORK_DIR>/containers/` |
| Processing Container | `<WORK_DIR>/processing_container_linux/` |
| Event Queue API | `<WORK_DIR>/Event_Queue_API/` |
| Third-Party Libs | `<WORK_DIR>/ThirdParty/` |
| AWS Config | `<WORK_DIR>/aws/` |

---

## Linux Containerization Branches

Available in `KinaTrax_development` remote branches:

| Branch | Purpose |
|--------|---------|
| `v6.3.9_batting_resampling_cameradisable_linux` | Batting processor v6.3.9 |
| `v6.3.9_pitching_linux` | Pitching processor v6.3.9 |
| `v6.3.9_pitching_resampling_cameradisable_linux` | Pitching with resampling v6.3.9 |
| `v6.4.0_batting_linux` | Batting processor v6.4.0 |
| `v6.4.0_batting_resampling_cameradisable_linux` | Batting with resampling v6.4.0 |
| `v6.4.0_pitching_resampling_cameradisable_linux` | Pitching with resampling v6.4.0 |

Worktrees available at `<WORK_DIR>/container-processing-branches/`:
- `v6.4.0_batting_resampling_cameradisable_linux_merged`
- `v6.4.0_pitching_resampling_cameradisable_linux`

---

## Core Components

### Main KinaTrax Library Modules

| Module | Purpose |
|--------|---------|
| **Acquisition** | Multi-camera video capture (Emergent, MatrixVision, Euresys frame grabbers) |
| **Calibration** | Camera intrinsic/extrinsic calibration, coordinate system alignment |
| **BodyModel** | Hierarchical skeleton definitions, joint centers, sport-specific models |
| **Tracking** | Joint detection, inverse kinematics solvers (8 versions), ICP algorithms |
| **Detection** | YOLOX-based person/ball detection via ONNX Runtime |
| **Classification** | DNN-based classifiers using TensorRT |
| **IO** | C3D/BVH file formats, Dropbox integration, video overlay generation |
| **Scene** | Motion sequences, BVH handling, capture volumes |
| **PostProcessing** | Butterworth filters, motion smoothing |
| **Geometry** | Euler angles, quaternions, geometric calculations |

### Key Executables

| Executable | Purpose |
|------------|---------|
| `track_joint_center_set_v6.X.X_batting` | Main batting event processor |
| `track_joint_center_set_v6.X.X_pitching` | Main pitching event processor |
| `generate_subject_model_v6.X.X_pitching` | Subject-specific model creation |
| `processing_properties_maker` | Generate XML config for processors |

---

## Container Architecture

### Base Image
```
nvcr.io/nvidia/tensorflow:23.11-tf2-py3
```
- NVIDIA TensorFlow container with GPU support
- Timezone: America/New_York
- Additional packages: OpenCV, Assimp, LAPACK, NLOPT

### Container Structure
```
/kinatrax/
├── Processing Executables
│   ├── track_joint_center_set_v6.3.9_batting
│   ├── track_joint_center_set_v6.3.9_pitching
│   ├── track_joint_center_set_v6.4.0_batting
│   ├── track_joint_center_set_v6.4.0_pitching
│   ├── generate_subject_model_v6.3.9_pitching
│   ├── generate_subject_model_v6.4.0_pitching
│   └── processing_properties_maker
├── Event Queue Processor
│   └── eventQueuePRC (Python entry point)
├── Configuration Files
│   ├── eventQueuePRC.json
│   └── Models/ (ML models)
├── Post-Processing
│   ├── Pose_Templates/
│   └── Statcast_Call_Play_Linux_ATH.py
├── Data Directory
│   └── /Data/ (per-team subdirectories)
└── Shared Libraries
    └── libcvsba.so
```

---

## Event Queue Processing Flow

1. Read `eventQueuePRC.json` configuration
2. Connect to Event Queue API
3. Poll for pending events (organization-based filtering)
4. Download event data from cloud storage
5. Run `processing_properties_maker` to generate XML config
6. Execute appropriate processor (batting/pitching, v6.3.9/v6.4.0)
7. Upload results to cloud storage

### Configuration Example (`eventQueuePRC.json`)
```json
{
  "environment": "Prod",
  "api": {
    "urlProd": "<EVENT_QUEUE_API_URL>",
    "organizationId": "<ORG_ID>",
    "apiKey": "<API_KEY>"
  },
  "processingPropertiesMaker": "/kinatrax/processing_properties_maker",
  "cloudBasePath": "/Data",
  "configurations": {
    "cloud": {
      "dataPath": "/kinatrax/Data",
      "eventAPICheckIntervalSeconds": 60,
      "concurrentEvents": 3
    }
  }
}
```

---

## Processing Performance

### Time Estimates (on-premises, 8-core GPU server)
| Event Type | Processing Time |
|------------|-----------------|
| Batting events | 4-6 hours per event |
| Pitching events | 6-8 hours per event |
| Subject model generation | 2-3 hours |

### Data Volumes
| Metric | Size |
|--------|------|
| Raw video per event | 5-15GB (8 cameras × 300+ FPS × 5-10 min) |
| Processing results | 500MB-2GB (C3D + BVH + overlay video) |
| Historical data | 2-3 petabytes (5-6 years MLB) |

### Parallel Processing Configuration
| Environment | Concurrent Events |
|-------------|-------------------|
| Cloud container | 3 |
| Local Linux | 2 |
| Local Windows | 1 |

---

## Third-Party Dependencies

### Key Libraries
| Category | Libraries |
|----------|-----------|
| Graphics & Visualization | Qt 5.12.12, VTK 8.0.1 & 9.2, OpenGL |
| Linear Algebra | Eigen, ALGLIB, CLAPACK, Levmar, NLOPT |
| Image/Video Processing | OpenCV 3.3.0 & 4.5.0, FFMPEG 3.3.3 & 4.0.2 |
| Point Cloud & 3D | PCL 1.8.1, CVSBA 1.0.0, Assimp 3.1.1 & 5.0.1 |
| ML & Inference | TensorFlow, TensorRT 8.6.1.6, ONNX Runtime |
| Utilities | Boost 1.62.0 & 1.82.0, TinyXML2, Curl, OpenSSL |

---

## AWS Deployment Considerations

### Metrics to Measure
1. **Processing Time Comparison**: On-premises vs AWS container variants
2. **Data Transfer Costs**: S3/EBS ingress, results egress
3. **Resource Utilization**: CPU/Memory/GPU per event type
4. **Container Scaling**: Auto-scaling based on event queue depth
5. **Cost Optimization**: Spot instances for non-urgent processing

### Instance Type Considerations
- GPU required (NVIDIA CUDA support)
- Recommended: p3.2xlarge or g4dn.xlarge for cost efficiency
- Storage: High IOPS EBS or local NVMe for video processing

---

## Build Commands

### Linux Container Build
```bash
cd <WORK_DIR>/container-processing-branches/v6.4.0_pitching_resampling_cameradisable_linux
mkdir build && cd build
cmake ..
make -j$(nproc)
```

### Docker Build
```bash
cd <WORK_DIR>/processing_container_linux
docker build -t kinatrax-processor:v6.4.0 .
```

---

## Data Structure

### S3 Bucket Layout
```
{TEAM}/
├── {YEAR}/
│   └── {SESSION_TIMESTAMP}/
│       ├── Batting/
│       │   └── {EVENT_TIMESTAMP}_{TEAM}_{PLAYER}/
│       │       ├── {CAMERA_ID}/{CAMERA_ID}.mp4
│       │       └── {EVENT}.c3d
│       └── Pitching/
│           └── Similar structure
```

### Sample Event (from test data)
- 8 camera MP4 files (~10-13MB each)
- 1 C3D output file (~1.5KB)
- Total per event: ~96MB
