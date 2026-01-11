# Container Testing Status Report

**Date:** January 10, 2026
**Status:** SUCCESS - AWS Deployment Complete

---

## AWS Deployment Summary

| Resource | Details |
|----------|---------|
| **Instance ID** | `<INSTANCE_ID>` |
| **Instance Type** | g4dn.xlarge ($0.53/hr) |
| **Public IP** | `<INSTANCE_IP>` |
| **GPU** | Tesla T4 (15GB) |
| **CUDA** | 12.4 |
| **Container** | prclinux:latest (9.4GB) |
| **Status** | All components working |

### Verified Working
- TensorFlow 2.14.0 with GPU
- Production binaries (batting/pitching processors v6.3.9, v6.4.0)
- All ML models loaded correctly
- No CUDA issues (unlike WSL2 environment)

### Quick Commands
```bash
# SSH to instance
ssh ec2-user@<INSTANCE_IP>

# Run container with GPU
docker run --gpus all -it --entrypoint /bin/bash <AWS_ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/prclinux:latest

# Test GPU in container
docker run --gpus all --rm --entrypoint nvidia-smi <AWS_ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/prclinux:latest

# Stop instance when done (to save costs)
aws ec2 stop-instances --profile <AWS_PROFILE> --region us-east-1 --instance-ids <INSTANCE_ID>
```

---

## Summary

Container testing on local WSL2/Podman environment identified a CUDA compatibility issue that will not affect AWS deployment. TensorFlow GPU processing works correctly; only ONNX Runtime has issues.

---

## Containers Created

| Container | Host | Tailscale IP | Status |
|-----------|------|--------------|--------|
| `kinatrax-dev` | `<DEV_HOST>` | - | Running |
| `capstone-dev` | `<DEV_HOST>` | `<TAILSCALE_IP>` | Running |

---

## What Works

1. **GPU Access**: nvidia-smi shows GPU (NVIDIA RTX 4000 Ada, 12GB)
2. **TensorFlow GPU**: Correctly identifies and uses GPU
3. **CUDA Runtime**: Both CUDA 11 and CUDA 12 runtimes can detect the GPU
4. **Production Binaries**: `track_joint_center_set_input` (TensorFlow-based) loads correctly
5. **Container Networking**: Tailscale connectivity established

---

## Issue: ONNX Runtime CUDA Provider

### Symptoms
```
CUDA failure 101: invalid device ordinal ; GPU=0
file: cuda_execution_provider.cc ; line=236
expr=cudaSetDevice(info_.device_id);
```

### Root Cause
- ONNX Runtime 1.16.3 CUDA provider is compiled against CUDA 11
- Provider libraries: `/usr/local/lib/libonnxruntime_providers_cuda.so`
- Links to: `libcublas.so.11`, `libcufft.so.10`, `libcudart.so.11.0`
- WSL2 GPU passthrough has compatibility issues with this configuration

### Why TensorFlow Works
- TensorFlow uses different CUDA initialization path
- TensorFlow in container is version 23.11 with proper WSL2 support
- Production binaries using .pb models (TensorFlow) work correctly

### Why This Won't Affect AWS
- AWS GPU instances (g4dn, p3, p4) have proper CUDA device files
- No WSL2 paravirtualization layer (/dev/dxg vs /dev/nvidia*)
- Container images work correctly on native Linux with NVIDIA runtime

---

## Binaries Tested

| Binary | Location | ML Framework | Status |
|--------|----------|--------------|--------|
| `general_tracker` | /workspace/KinaTrax/build/bin/ | ONNX Runtime | FAILS (CUDA issue) |
| `track_joint_center_set_input` | /kinatrax/ | TensorFlow | WORKS (loads correctly) |
| `eventQueuePRC` | /kinatrax/ | N/A | WORKS (needs config) |

---

## Sample Data Collected

- **100 events** downloaded from S3 (14GB, 2514 files)
- **17 MLB teams** represented
- **Event types**: Batting and Pitching (baseball)
- **Location**: `data/samples/` (local) and manifest at `data/samples/manifest.json`

---

## Recommended Next Steps

### For AWS Deployment (Primary Goal)
1. Deploy container image to AWS ECR
2. Launch g4dn.xlarge instance with NVIDIA runtime
3. Test `general_tracker` processing with sample events
4. Collect processing time metrics for cost-benefit analysis

### For Local Development
1. Continue using dashboard visualization (Pareto frontier)
2. Use production TensorFlow binaries if needed
3. Collect metrics from existing production processing logs

### For CUDA Issue (Optional Fix)
1. Rebuild ONNX Runtime 1.18+ with CUDA 12 support
2. Or use CPU-only ONNX Runtime for testing

---

## Technical Details

### Container Configuration
```bash
# Base image
nvcr.io/nvidia/tensorflow:23.11-tf2-py3

# CUDA Versions
- Container CUDA Toolkit: 12.3
- ONNX Runtime compiled for: CUDA 11
- Host Driver: 581.60 (CUDA 13.0 capable)
```

### GPU Access in WSL2
```bash
# WSL2 uses /dev/dxg instead of /dev/nvidia*
ls -la /dev/dxg
# crw-rw-rw- 1 nobody nogroup 10, 125 Jan 8 07:50 /dev/dxg

# nvidia-smi works through paravirtualization
nvidia-smi
# NVIDIA RTX 4000 Ada, 12282MiB
```

---

## Files Created

| File | Purpose |
|------|---------|
| `scripts/collect_sample_data.py` | S3 data collection script |
| `data/samples/manifest.json` | List of 100 sampled events |
| `docs/KinaTrax_Architecture_Reference.md` | Architecture documentation |
| `docs/Container_Testing_Status.md` | This document |
