#!/usr/bin/env python3
"""Make a web-ready, privacy-cloaked copy of a photo for the site.

Run it with bin/cloak_photo.sh, which installs what this script needs into a throwaway Python
environment and deletes everything it downloaded when it finishes:

    bin/cloak_photo.sh PHOTO.HEIC assets/img/profile/prof_pic.webp

What it does:
  1. Reads the photo (HEIC, JPEG, PNG, ...) upright, converts its colors to sRGB, and drops all of
     its metadata (GPS location, capture time, phone and lens model, ...).
  2. Crops a 4:5 portrait around the face (or the box given with --crop).
  3. Adds a cloak: a small adversarial change to the face, computed against four open
     face-recognition models (InsightFace's ArcFace R50 and R100, FaceNet, and OpenCV's SFace),
     that moves the face's features away from the person's identity. This follows LowKey
     (Cherepanova et al., ICLR 2021, https://arxiv.org/abs/2101.07922). While optimizing, the
     photo is also resized, saved as JPEG or WebP, blurred, and re-aligned at random, so the cloak
     survives resaving. Most of the change goes into brightness in textured areas (hair,
     eyebrows, eyes), where it is hardest to see.
  4. Saves a WebP, then tests the saved file with those four models and three that the cloak
     never saw: FaceNet trained on other data, AuraFace, and dlib.

A cloak lowers the match scores of the models it is tested against; it is not a guarantee. Newer
models, or models trained on cloaked photos, can still recognize the face (Radiya-Dixit et al.,
ICLR 2022, https://arxiv.org/abs/2106.14851). It is also visible up close at the strengths that
work. On the 2026 profile photo, the default strength stopped 6 of the 7 test models from
matching but looked odd up close. Versions too faint to notice stopped none, so that photo was
published with --no-cloak.

Requirements (bin/cloak_photo.sh installs them): torch torchvision onnx onnx2torch onnxruntime
opencv-python-headless pillow-heif lpips requests tqdm, facenet-pytorch (with --no-deps), and
optionally dlib. The model weights (about 1.5 GB) download to a temporary folder that is deleted
at the end, unless --model-cache names a folder to keep them in.
"""

import argparse
import bz2
import io
import os
import shutil
import sys
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path

os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

try:
    import numpy as np
    from PIL import Image, ImageCms, ImageOps
except ImportError:  # only --help works without the packages; bin/cloak_photo.sh installs them
    np = Image = ImageCms = ImageOps = None

MODEL_DIR = None  # set in main(): a temporary folder, or --model-cache

# Model files: name -> (folder under MODEL_DIR, download URL). Archives are unpacked.
WEIGHTS = {
    "w600k_r50.onnx": ("insightface", "https://github.com/deepinsight/insightface/releases/download/v0.7/buffalo_l.zip"),
    "glintr100.onnx": ("insightface", "https://github.com/deepinsight/insightface/releases/download/v0.7/antelopev2.zip"),
    "auraface_glintr100.onnx": ("auraface", "https://huggingface.co/fal/AuraFace-v1/resolve/main/glintr100.onnx"),
    "20180402-114759-vggface2.pt": ("torch/checkpoints", "https://github.com/timesler/facenet-pytorch/releases/download/v2.2.9/20180402-114759-vggface2.pt"),
    "20180408-102900-casia-webface.pt": ("torch/checkpoints", "https://github.com/timesler/facenet-pytorch/releases/download/v2.2.9/20180408-102900-casia-webface.pt"),
    "face_detection_yunet_2023mar.onnx": ("opencv", "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"),
    "face_recognition_sface_2021dec.onnx": ("opencv", "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx"),
    "dlib_face_recognition_resnet_model_v1.dat": ("dlib", "http://dlib.net/files/dlib_face_recognition_resnet_model_v1.dat.bz2"),
    "shape_predictor_5_face_landmarks.dat": ("dlib", "http://dlib.net/files/shape_predictor_5_face_landmarks.dat.bz2"),
}

# Cloak strength: the largest brightness change (out of 255) on smooth areas like skin and on
# textured areas like hair and eyebrows, and the weight of the image-quality penalty.
STRENGTHS = {"low": (2, 8, 4.0), "medium": (3, 12, 2.0), "high": (5, 16, 1.0)}
CHROMA = 0.35  # color changes are held to this fraction of the brightness budget
EYES = 0.5  # and changes around the eyes, where people look first, to this fraction
TARGET = 0.0  # stop lowering a model's similarity once it reaches this; spend the rest on looks

# InsightFace's ArcFace alignment: where the eyes, nose tip, and mouth corners go in a 112x112 crop.
# SFace (OpenCV) uses the same one.
ARCFACE_TEMPLATE = [[38.2946, 51.6963], [73.5318, 51.5014], [56.0252, 71.7366], [41.5493, 92.3655], [70.7299, 92.2041]]


def weight(name):
    """Path to a model file, downloading it on first use."""
    folder, url = WEIGHTS[name]
    dest = MODEL_DIR / folder
    for attempt in range(2):
        found = sorted(dest.rglob(name))
        if found:
            return found[0]
        if attempt:
            sys.exit(f"Downloaded {url} but found no {name} in it.")
        dest.mkdir(parents=True, exist_ok=True)
        print(f"Downloading {url.rsplit('/', 1)[1]} ...", flush=True)
        request = urllib.request.Request(url, headers={"User-Agent": "cloak-photo"})
        with urllib.request.urlopen(request) as response, tempfile.TemporaryFile() as tmp:
            shutil.copyfileobj(response, tmp)
            tmp.seek(0)
            if url.endswith(".zip"):
                with zipfile.ZipFile(tmp) as archive:
                    archive.extractall(dest / Path(url).stem)
            elif url.endswith(".bz2"):
                (dest / name).write_bytes(bz2.decompress(tmp.read()))
            else:
                with open(dest / name, "wb") as f:
                    shutil.copyfileobj(tmp, f)


# ---------------------------------------------------------------------------------------------
# Reading, cropping, saving


def load_photo(path):
    """Decode a photo upright and in sRGB. Returns a bare RGB array, so no metadata comes along."""
    import pillow_heif

    pillow_heif.register_heif_opener()
    with Image.open(path) as im:
        if im.format != "HEIF":  # pillow-heif applies a HEIC's rotation itself
            im = ImageOps.exif_transpose(im)
        icc = im.info.get("icc_profile")
        rgb = im.convert("RGB")
        if icc:  # phone photos are usually Display P3; browsers assume sRGB when there's no profile
            rgb = ImageCms.profileToProfile(
                rgb,
                ImageCms.ImageCmsProfile(io.BytesIO(icc)),
                ImageCms.createProfile("sRGB"),
                renderingIntent=ImageCms.Intent.PERCEPTUAL,
                outputMode="RGB",
            )
        return np.array(rgb)


def find_face(rgb):
    """The largest face: MTCNN box (x1, y1, x2, y2) and landmarks (eyes, nose tip, mouth corners)."""
    from facenet_pytorch import MTCNN

    scale = min(1.0, 1600 / max(rgb.shape[:2]))
    small = Image.fromarray(rgb)
    if scale < 1:
        small = small.resize((round(rgb.shape[1] * scale), round(rgb.shape[0] * scale)), Image.LANCZOS)
    boxes, _, points = MTCNN(keep_all=True, device="cpu").detect(small, landmarks=True)
    if boxes is None:
        sys.exit("No face found in the photo.")
    i = int(np.argmax((boxes[:, 2] - boxes[:, 0]) * (boxes[:, 3] - boxes[:, 1])))
    return boxes[i] / scale, points[i] / scale


def portrait_box(shape, box, points, face_fraction):
    """A 4:5 crop with the face box `face_fraction` of its width and the eyes 40% from the top."""
    H, W = shape[:2]
    cw = min((box[2] - box[0]) / face_fraction, W, H * 4 / 5)
    cw = 2 * int(cw / 2)
    ch = 2 * int(cw * 5 / 8)
    cx, eye_y = points[:3, 0].mean(), points[:2, 1].mean()
    left = int(round(min(max(cx - cw / 2, 0), W - cw)))
    top = int(round(min(max(eye_y - 0.4 * ch, 0), H - ch)))
    return left, top, left + cw, top + ch


def encode_webp(rgb, quality):
    buf = io.BytesIO()
    Image.fromarray(rgb).save(buf, "WEBP", quality=quality, method=6)  # no EXIF, XMP, or ICC written
    return buf.getvalue()


def decode(data):
    with Image.open(io.BytesIO(data)) as im:
        return np.array(im.convert("RGB"))


def resized(rgb, width):
    h = round(rgb.shape[0] * width / rgb.shape[1])
    return np.array(Image.fromarray(rgb).resize((width, h), Image.LANCZOS))


def jpeg(rgb, quality):
    buf = io.BytesIO()
    Image.fromarray(rgb).save(buf, "JPEG", quality=quality)
    return decode(buf.getvalue())


# ---------------------------------------------------------------------------------------------
# Geometry


def similarity_transform(src, dst):
    """Least-squares rotation, uniform scale, and shift taking src points to dst (Umeyama); 2x3."""
    src, dst = np.asarray(src, float), np.asarray(dst, float)
    ms, md = src.mean(0), dst.mean(0)
    s, d = src - ms, dst - md
    U, S, Vt = np.linalg.svd(d.T @ s / len(src))
    D = np.diag([1.0, -1.0 if np.linalg.det(U) * np.linalg.det(Vt) < 0 else 1.0])
    R = U @ D @ Vt
    c = np.trace(np.diag(S) @ D) / (s**2).sum(1).mean()
    return np.hstack([c * R, (md - c * R @ ms)[:, None]])


def scale_points(p, s):
    """Pixel coordinates after resizing an image by factor s (pixel centers at integers)."""
    return (np.asarray(p, float) + 0.5) * s - 0.5


def arcface_mats(lm, d, rng, n, jitter):
    """ArcFace alignments; jitter moves the landmarks the way a different face detector would."""
    noise = 0.04 * d if jitter else 0.0
    return [similarity_transform(lm + rng.normal(0, noise, lm.shape), ARCFACE_TEMPLATE) for _ in range(n)]


def facenet_mats(box, rng, n, jitter, size=160):
    """FaceNet crops: the detector's box, stretched to a square, with a random margin and shift."""
    x1, y1, x2, y2 = box
    w, h = x2 - x1, y2 - y1
    mats = []
    for _ in range(n):
        grow = 1 + (rng.uniform(0, 0.25) if jitter else 0)
        cx = (x1 + x2) / 2 + (rng.normal(0, 0.03) * w if jitter else 0)
        cy = (y1 + y2) / 2 + (rng.normal(0, 0.03) * h if jitter else 0)
        sx, sy = size / (w * grow), size / (h * grow)
        left, top = cx - w * grow / 2, cy - h * grow / 2
        mats.append(np.array([[sx, 0, (0.5 - left) * sx - 0.5], [0, sy, (0.5 - top) * sy - 0.5]]))
    return mats


def warp(img, mats, size, antialias):
    """Crop size x size patches from img (1, C, H, W) with pixel affines (image -> patch)."""
    import torch
    import torch.nn.functional as F

    zoom = float(np.sqrt(abs(np.linalg.det(mats[0][:, :2]))))
    if antialias and zoom < 0.9:  # shrink smoothly first, as PIL- and OpenCV-area resizes do
        z = zoom * 1.1
        img = F.interpolate(img, scale_factor=z, mode="bilinear", antialias=True, align_corners=False)
        back = np.array([[1 / z, 0, 0.5 / z - 0.5], [0, 1 / z, 0.5 / z - 0.5], [0, 0, 1]])
        mats = [(np.vstack([M, [0, 0, 1]]) @ back)[:2] for M in mats]
    hi, wi = img.shape[-2:]
    to_px = np.array([[size / 2, 0, (size - 1) / 2], [0, size / 2, (size - 1) / 2], [0, 0, 1]])
    to_norm = np.array([[2 / wi, 0, 1 / wi - 1], [0, 2 / hi, 1 / hi - 1], [0, 0, 1]])
    thetas = np.stack([(to_norm @ np.linalg.inv(np.vstack([M, [0, 0, 1]])) @ to_px)[:2] for M in mats])
    thetas = torch.tensor(thetas, dtype=torch.float32, device=img.device)
    grid = F.affine_grid(thetas, (len(mats), img.shape[1], size, size), align_corners=False)
    return F.grid_sample(img.expand(len(mats), -1, -1, -1), grid, mode="bilinear", padding_mode="zeros", align_corners=False)


# ---------------------------------------------------------------------------------------------
# The cloak


class ArcFaceTorch:
    """An InsightFace ArcFace ONNX model, converted to PyTorch so gradients flow through it."""

    def __init__(self, path, device):
        import onnx2torch

        self.net = onnx2torch.convert(str(path)).eval().to(device).requires_grad_(False)

    def __call__(self, crops):  # 112x112 aligned crops, RGB in [0, 1]
        import torch.nn.functional as F

        return F.normalize(self.net(crops * 2 - 1), dim=1)


class SFaceTorch(ArcFaceTorch):
    def __call__(self, crops):  # OpenCV feeds SFace RGB values from 0 to 255
        import torch.nn.functional as F

        return F.normalize(self.net(crops * 255), dim=1)


class FaceNetTorch:
    def __init__(self, weights, device):
        from facenet_pytorch import InceptionResnetV1

        weight({"vggface2": "20180402-114759-vggface2.pt", "casia-webface": "20180408-102900-casia-webface.pt"}[weights])
        self.net = InceptionResnetV1(pretrained=weights).eval().to(device).requires_grad_(False)

    def __call__(self, crops):  # 160x160 crops, RGB in [0, 1]; the network normalizes its output
        return self.net((crops * 255 - 127.5) / 128)


def gaussian_blur(x, sigma):
    import torch
    import torch.nn.functional as F

    r, c = max(1, int(np.ceil(3 * sigma))), x.shape[1]
    k = torch.exp(-torch.arange(-r, r + 1, device=x.device, dtype=x.dtype) ** 2 / (2 * sigma**2))
    k = k / k.sum()
    x = F.conv2d(F.pad(x, (r, r, 0, 0), mode="reflect"), k.view(1, 1, 1, -1).repeat(c, 1, 1, 1), groups=c)
    return F.conv2d(F.pad(x, (0, 0, r, r), mode="reflect"), k.view(1, 1, -1, 1).repeat(c, 1, 1, 1), groups=c)


def augment(x, rng):
    """Random blur, exposure change, and sensor-like noise."""
    import torch

    if rng.random() < 0.25:
        x = gaussian_blur(x, rng.uniform(0.3, 1.0))
    if rng.random() < 0.3:
        x = (x - 0.5) * rng.uniform(0.93, 1.07) + 0.5 + rng.uniform(-0.03, 0.03)
    if rng.random() < 0.3:
        x = x + torch.randn_like(x) * rng.uniform(0.002, 0.01)
    return x.clamp(0, 1)


def codec_roundtrip(x, rng):
    """x after a real WebP or JPEG save and load, at a random quality."""
    import torch

    arr = (x[0].detach().permute(1, 2, 0).cpu().numpy() * 255).round().clip(0, 255).astype(np.uint8)
    buf = io.BytesIO()
    if rng.random() < 0.5:
        Image.fromarray(arr).save(buf, "WEBP", quality=int(rng.integers(80, 93)), method=4)
    else:
        Image.fromarray(arr).save(buf, "JPEG", quality=int(rng.integers(70, 96)))
    back = decode(buf.getvalue())
    return torch.from_numpy(back).to(x.device).permute(2, 0, 1)[None].float() / 255


def cloak(rgb, box, lm, strength, steps, device, seed=0, log=print):
    """Return rgb with a cloak over the face, and the region it may change (left, top, right, bottom)."""
    import lpips
    import torch
    import torch.nn.functional as F

    eps_smooth, eps_texture, lpips_weight = strength
    rng = np.random.default_rng(seed)
    torch.manual_seed(seed)
    H, W = rgb.shape[:2]
    d = float(np.linalg.norm(lm[1] - lm[0]))  # distance between the eyes, in pixels
    eyes, mouth = lm[:2].mean(0), lm[3:].mean(0)

    # The cloak covers a rounded rectangle over the face, hair, and chin, which holds every crop
    # the models take. All work happens in a region around it whose edges sit on the 16-pixel
    # block grid that JPEG and WebP use, so compressing the region matches compressing the photo.
    cx, cy = eyes[0], (eyes[1] - 2.0 * d + mouth[1] + 1.0 * d) / 2
    rx, ry = 2.0 * d, (mouth[1] - eyes[1] + 3.0 * d) / 2
    left, top = max(0, int((cx - rx - 0.5 * d) // 16 * 16)), max(0, int((cy - ry - 0.5 * d) // 16 * 16))
    right, bottom = min(W, int(-(-(cx + rx + 0.5 * d) // 16) * 16)), min(H, int(-(-(cy + ry + 0.5 * d) // 16) * 16))
    region = (slice(top, bottom), slice(left, right))
    x0 = torch.from_numpy(rgb[region].copy()).to(device).permute(2, 0, 1)[None].float() / 255
    h, w = x0.shape[-2:]
    lm_r = lm - [left, top]
    box_r = np.asarray(box, float) - [left, top, left, top]

    ys = torch.arange(h, device=device, dtype=torch.float32)[:, None] + top
    xs = torch.arange(w, device=device, dtype=torch.float32)[None, :] + left
    t = ((1 - (((xs - cx) / rx) ** 4 + ((ys - cy) / ry) ** 4) ** 0.25) / 0.3).clamp(0, 1)
    mask = (t * t * (3 - 2 * t))[None, None]  # 1 over the face, fading smoothly to 0 at the edge

    # How much each pixel may change: little on smooth skin, more where local texture (hair,
    # eyebrows, eyes, rock) hides it. Color changes get a smaller share than brightness changes.
    luma_weights = torch.tensor([0.299, 0.587, 0.114], device=device).view(1, 3, 1, 1)
    luma = (x0 * luma_weights).sum(1, keepdim=True)
    mean = F.avg_pool2d(F.pad(luma, (4, 4, 4, 4), mode="reflect"), 9, stride=1)
    std = (F.avg_pool2d(F.pad(luma**2, (4, 4, 4, 4), mode="reflect"), 9, stride=1) - mean**2).clamp_min(0).sqrt()
    texture = gaussian_blur(((std - 0.01) / 0.04).clamp(0, 1), 3.0)
    near_eyes = sum(torch.exp(-((xs - left - ex) ** 2 + (ys - top - ey) ** 2) / (2 * (0.25 * d) ** 2)) for ex, ey in lm_r[:2])
    budget = (eps_smooth + (eps_texture - eps_smooth) * texture) / 255 * mask * (1 - (1 - EYES) * near_eyes.clamp(max=1))
    channel_share = torch.tensor([1.0, CHROMA, CHROMA], device=device).view(1, 3, 1, 1)
    ycc_to_rgb = torch.tensor([[1.0, 0.0, 1.402], [1.0, -0.344136, -0.714136], [1.0, 1.772, 0.0]], device=device)

    # The change is stored at half resolution: smoother, so it survives resizing and compression.
    param = torch.zeros(1, 3, (h + 1) // 2, (w + 1) // 2, device=device, requires_grad=True)
    opt = torch.optim.Adam([param], lr=0.03)
    aligned = {
        "ArcFace R50": ArcFaceTorch(weight("w600k_r50.onnx"), device),
        "ArcFace R100": ArcFaceTorch(weight("glintr100.onnx"), device),
        "SFace": SFaceTorch(weight("face_recognition_sface_2021dec.onnx"), device),
    }
    facenet = FaceNetTorch("vggface2", device)
    names = [*aligned, "FaceNet"]
    perceptual = lpips.LPIPS(net="alex", verbose=False).to(device).requires_grad_(False)

    def cloaked():
        ycc = F.interpolate(torch.tanh(param), size=(h, w), mode="bilinear", align_corners=False) * channel_share * budget
        return (x0 + torch.einsum("ij,bjhw->bihw", ycc_to_rgb, ycc)).clamp(0, 1)

    def dssim(x):
        """Structural dissimilarity of x's brightness to the original's over the changed area."""
        a, b = (luma_weights * x).sum(1, keepdim=True), luma
        mu_a, mu_b = gaussian_blur(a, 1.5), gaussian_blur(b, 1.5)
        var_a, var_b = gaussian_blur(a * a, 1.5) - mu_a**2, gaussian_blur(b * b, 1.5) - mu_b**2
        cov = gaussian_blur(a * b, 1.5) - mu_a * mu_b
        ssim = ((2 * mu_a * mu_b + 1e-4) * (2 * cov + 9e-4)) / ((mu_a**2 + mu_b**2 + 1e-4) * (var_a + var_b + 9e-4))
        return ((1 - ssim) / 2 * mask).sum() / mask.sum()

    def looks(x):
        """Image-quality penalty: LPIPS up close and at the size the page shows, plus DSSIM."""
        half = lambda v: F.interpolate(v, scale_factor=0.5, mode="bilinear", antialias=True, align_corners=False)  # noqa: E731
        return perceptual(x * 2 - 1, x0 * 2 - 1).mean() + perceptual(half(x) * 2 - 1, half(x0) * 2 - 1).mean() + 5 * dssim(x)

    def views(x, scales, n, jitter=True):
        """Each model's embeddings of the face in x, seen at several sizes and alignments."""
        out = {name: [] for name in names}
        for s in scales:
            img = x if s > 0.99 else F.interpolate(x, scale_factor=s, mode="bilinear", antialias=True, align_corners=False)
            if jitter:
                img = augment(img, rng)
            smooth = bool(rng.random() < 0.5) if jitter else False  # InsightFace and OpenCV warp without smoothing
            crops = warp(img, arcface_mats(scale_points(lm_r, s), d * s, rng, n, jitter), 112, smooth)
            for name, model in aligned.items():
                out[name].append(model(crops))
            crops = warp(img, facenet_mats(scale_points(box_r.reshape(2, 2), s).ravel(), rng, n, jitter), 160, True)
            out["FaceNet"].append(facenet(crops))
        return [torch.cat(out[name]) for name in names]

    with torch.no_grad():  # what each model sees in the original face
        anchors = [F.normalize(e.mean(0), dim=0) for e in views(x0, [1.0, 0.7, 0.5, 0.35], 4)]

    start = time.time()
    for step in range(1, steps + 1):
        xc = cloaked()
        x = xc
        if rng.random() < 0.6:  # pass gradients straight through a real JPEG or WebP save
            x = xc + (codec_roundtrip(xc, rng) - xc).detach()
        sims = torch.stack([(e @ a).mean() for e, a in zip(views(x, [rng.uniform(0.6, 1.0), rng.uniform(0.3, 0.6)], 2), anchors)])
        excess = 0.05 * F.softplus((sims - TARGET) / 0.05)  # about max(similarity - TARGET, 0)
        quality_loss = looks(xc)
        loss = excess.max() + excess.mean() + lpips_weight * quality_loss
        opt.zero_grad()
        loss.backward()
        opt.step()
        if step == 1 or step % 50 == 0:
            shown = "  ".join(f"{name} {float(sim):.2f}" for name, sim in zip(names, sims))
            log(f"  step {step:3d}/{steps}: similarity to the original  {shown};  quality penalty {float(quality_loss):.3f}  ({time.time() - start:.0f} s)")

    with torch.no_grad():
        x = cloaked()
    out = rgb.copy()
    out[region] = (x[0].permute(1, 2, 0).cpu().numpy() * 255).round().clip(0, 255).astype(np.uint8)
    return out, (left, top, right, bottom)


# ---------------------------------------------------------------------------------------------
# Testing with off-the-shelf face-recognition pipelines


class Tester:
    """Face-recognition pipelines (detector, alignment, model) run the way their libraries run them."""

    # name, used to compute the cloak, score, threshold for "same person"
    MODELS = [
        ("ArcFace R50 (InsightFace buffalo_l)", True, "similarity", 0.25),
        ("ArcFace R100 (InsightFace antelopev2)", True, "similarity", 0.25),
        ("FaceNet (VGGFace2)", True, "similarity", 0.40),
        ("SFace (OpenCV)", True, "similarity", 0.363),
        ("FaceNet (CASIA-WebFace)", False, "similarity", 0.40),
        ("AuraFace R100 (fal.ai, 2024)", False, "similarity", 0.25),
        ("dlib ResNet (face_recognition)", False, "distance", 0.60),
    ]

    def __init__(self):
        import cv2
        import onnxruntime as ort
        from facenet_pytorch import MTCNN

        ort.set_default_logger_severity(3)
        self.cv2 = cv2
        self.yunet_path = str(weight("face_detection_yunet_2023mar.onnx"))
        self.sface = cv2.FaceRecognizerSF.create(str(weight("face_recognition_sface_2021dec.onnx")), "")
        self.mtcnn = MTCNN(image_size=160, margin=0, device="cpu")  # facenet-pytorch's standard setup
        session = lambda f: ort.InferenceSession(str(weight(f)), providers=["CPUExecutionProvider"])  # noqa: E731
        self.arcface = {
            "ArcFace R50 (InsightFace buffalo_l)": session("w600k_r50.onnx"),
            "ArcFace R100 (InsightFace antelopev2)": session("glintr100.onnx"),
            "AuraFace R100 (fal.ai, 2024)": session("auraface_glintr100.onnx"),
        }
        self.facenet = {"FaceNet (VGGFace2)": FaceNetTorch("vggface2", "cpu").net, "FaceNet (CASIA-WebFace)": FaceNetTorch("casia-webface", "cpu").net}
        try:
            import dlib

            self.dlib = (
                dlib.get_frontal_face_detector(),
                dlib.shape_predictor(str(weight("shape_predictor_5_face_landmarks.dat"))),
                dlib.face_recognition_model_v1(str(weight("dlib_face_recognition_resnet_model_v1.dat"))),
            )
        except ImportError:
            self.dlib = None

    def features(self, rgb):
        """{model name: {face detector: embedding}} for the largest face; {} if no face is found."""
        import torch

        rgb = np.ascontiguousarray(rgb)  # dlib rejects array views
        cv2, bgr = self.cv2, self.cv2.cvtColor(rgb, self.cv2.COLOR_RGB2BGR)
        h, w = rgb.shape[:2]
        _, faces = cv2.FaceDetectorYN.create(self.yunet_path, "", (w, h), 0.6, 0.3, 5000).detect(bgr)
        face = None if faces is None or len(faces) == 0 else faces[np.argmax(faces[:, 2] * faces[:, 3])]
        boxes, _, points = self.mtcnn.detect(Image.fromarray(rgb), landmarks=True)
        landmarks = {}
        if face is not None:
            landmarks["YuNet"] = face[4:14].reshape(5, 2)
        if boxes is not None:
            landmarks["MTCNN"] = points[np.argmax((boxes[:, 2] - boxes[:, 0]) * (boxes[:, 3] - boxes[:, 1]))]

        out = {}
        for name, session in self.arcface.items():
            out[name] = {}
            for detector, lm in landmarks.items():  # InsightFace's norm_crop, from each detector's landmarks
                crop = cv2.warpAffine(rgb, similarity_transform(lm, ARCFACE_TEMPLATE), (112, 112), borderValue=0.0)
                blob = ((crop.astype(np.float32) - 127.5) / 127.5).transpose(2, 0, 1)[None]
                e = session.run(None, {session.get_inputs()[0].name: blob})[0][0]
                out[name][detector] = e / np.linalg.norm(e)
        with torch.no_grad():
            crop = self.mtcnn(Image.fromarray(rgb))
            for name, net in self.facenet.items():
                out[name] = {} if crop is None else {"MTCNN": net(crop[None])[0].numpy()}
        out["SFace (OpenCV)"] = {}
        if face is not None:
            e = self.sface.feature(self.sface.alignCrop(bgr, face)).ravel()
            out["SFace (OpenCV)"]["YuNet"] = e / np.linalg.norm(e)
        if self.dlib:
            detect, shape, model = self.dlib
            found = detect(rgb, 1)
            biggest = max(found, key=lambda b: b.area()) if found else None
            out["dlib ResNet (face_recognition)"] = {"dlib": np.array(model.compute_face_descriptor(rgb, shape(rgb, biggest)))} if found else {}
        return out

    def compare(self, original, versions):
        """Per model: (closest match between the original and any version over every detector,
        whether a detector found no face in some version)."""
        ref = self.features(original)
        tested = [self.features(img) for img in versions]
        results = {}
        for name, _, kind, _ in self.MODELS:
            if name not in ref:
                continue
            scores, missed = [], False
            for feats in tested:
                for detector, a in ref[name].items():
                    b = feats[name].get(detector)
                    if b is None:
                        missed = True
                    else:
                        scores.append(float(a @ b) if kind == "similarity" else float(np.linalg.norm(a - b)))
            best = (max(scores) if kind == "similarity" else min(scores)) if scores else None
            results[name] = (best, missed)
        return results


def report(tester, clean, clean_published, published, log=print):
    """Print, for each model, how well the published photo matches the original. Returns how many
    models don't match it and how many were tested."""
    versions = lambda img: [img, resized(img, 480), jpeg(img, 75)]  # noqa: E731
    control = tester.compare(clean, versions(clean_published))
    test = tester.compare(clean, versions(published))
    log("\nHow closely each model matches the published photo to the original, taking the closest of")
    log("three versions (as published; scaled to 480 px wide; re-saved as JPEG quality 75) and, for")
    log("the ArcFace-style models, of two face detectors. Similarity is 1.0 for identical faces; dlib")
    log("gives a distance instead (0 for identical faces). 'Uncloaked' is the same crop without a cloak.")
    log("The thresholds are typical published values; real systems pick their own.\n")
    log(f"{'model':38s} {'in cloak':>8s} {'uncloaked':>9s} {'cloaked':>8s} {'same person if':>15s}  result")
    protected = 0
    for name, used, kind, thr in Tester.MODELS:
        if name not in test:
            continue
        (ctrl, _), (score, missed) = control[name], test[name]
        same = score is not None and (score >= thr if kind == "similarity" else score <= thr)
        rule = f"{'>=' if kind == 'similarity' else '<='} {thr}"
        fmt = lambda v: "no face" if v is None else f"{v:.2f}"  # noqa: E731
        verdict = ("MATCH" if same else "no match") + (" (no face found in some versions)" if missed else "")
        protected += not same
        log(f"{name:38s} {'yes' if used else 'no':>8s} {fmt(ctrl):>9s} {fmt(score):>8s} {rule:>15s}  {verdict}")
    return protected, len(test)


def psnr(a, b):
    mse = np.mean((a.astype(float) - b.astype(float)) ** 2)
    return float("inf") if mse == 0 else 10 * np.log10(255**2 / mse)


def comparison_image(clean, cloaked_img, box, path):
    """Side by side: both photos at the size the home page shows them, then the face up close."""
    left, top, right, bottom = box
    small = [Image.fromarray(i).resize((540, round(540 * i.shape[0] / i.shape[1])), Image.LANCZOS) for i in (clean, cloaked_img)]
    face = [Image.fromarray(i[top:bottom, left:right]) for i in (clean, cloaked_img)]
    gap = 16
    width = max(2 * 540, 2 * face[0].width) + gap
    canvas = Image.new("RGB", (width, small[0].height + face[0].height + gap), "white")
    canvas.paste(small[0], (0, 0))
    canvas.paste(small[1], (540 + gap, 0))
    canvas.paste(face[0], (0, small[0].height + gap))
    canvas.paste(face[1], (face[0].width + gap, small[0].height + gap))
    canvas.save(path, quality=92)


# ---------------------------------------------------------------------------------------------


def run(args):
    import torch

    device = args.device or ("mps" if torch.backends.mps.is_available() else "cpu")
    rgb = load_photo(args.photo)
    print(f"Read {args.photo.name}: {rgb.shape[1]}x{rgb.shape[0]}, converted to sRGB, metadata dropped.")
    box, points = find_face(rgb)
    left, top, right, bottom = args.crop or portrait_box(rgb.shape, box, points, args.face_fraction)
    rgb = np.ascontiguousarray(rgb[top:bottom, left:right])
    if rgb.shape[1] > args.max_width:
        rgb = resized(rgb, args.max_width)
    print(f"Cropped to {right - left}x{bottom - top} at ({left}, {top}); output {rgb.shape[1]}x{rgb.shape[0]}.")
    clean_published = decode(encode_webp(rgb, args.quality))  # the same crop and WebP settings, no cloak

    if args.test_only:
        published = decode(args.output.read_bytes())
        if published.shape != rgb.shape:
            sys.exit(f"{args.output} is {published.shape[1]}x{published.shape[0]}; use the crop options it was made with.")
        protected, tested = report(Tester(), rgb, clean_published, published)
        print(f"\n{protected} of {tested} models do not match {args.output} to the original.")
        return
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.no_cloak:
        data = encode_webp(rgb, args.quality)
        args.output.write_bytes(data)
        print(f"Wrote {args.output}: {rgb.shape[1]}x{rgb.shape[0]} WebP, {len(data) / 1024:.0f} KB, no cloak.")
        return

    box, points = find_face(rgb)
    print(f"Computing a {args.strength} cloak on {device}:")
    cloaked_img, region = cloak(rgb, box, points, STRENGTHS[args.strength], args.steps, device, args.seed)
    data = encode_webp(cloaked_img, args.quality)
    args.output.write_bytes(data)
    published = decode(data)
    left, top, right, bottom = region
    print(f"\nWrote {args.output}: {rgb.shape[1]}x{rgb.shape[0]} WebP, {len(data) / 1024:.0f} KB.")
    print(
        f"Change from the cloak (PSNR against the same photo without it): {psnr(clean_published, published):.1f} dB overall,"
        f" {psnr(clean_published[top:bottom, left:right], published[top:bottom, left:right]):.1f} dB around the face."
    )
    if args.compare:
        comparison_image(clean_published, published, region, args.compare)
        print(f"Before/after comparison: {args.compare}")
    protected, tested = report(Tester(), rgb, clean_published, published)
    print(f"\n{protected} of {tested} models do not match the published photo to the original.")


def main():
    global MODEL_DIR
    parts = __doc__.split("\n\n")
    parser = argparse.ArgumentParser(description=parts[0], epilog="\n\n".join(parts[1:]), formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("photo", type=Path, help="the original photo (HEIC, JPEG, PNG, ...)")
    parser.add_argument("output", type=Path, help="where to write the WebP, e.g. assets/img/profile/prof_pic.webp")
    parser.add_argument("--crop", type=int, nargs=4, metavar=("LEFT", "TOP", "RIGHT", "BOTTOM"), help="crop box in the original photo's pixels (default: a 4:5 portrait around the face)")
    parser.add_argument("--face-fraction", type=float, default=0.22, help="automatic crop: face width as a fraction of the crop width (default 0.22)")
    parser.add_argument("--max-width", type=int, default=1200, help="scale the crop down to at most this many pixels wide (default 1200)")
    parser.add_argument("--strength", choices=STRENGTHS, default="medium", help="cloak strength: stronger protects more but shows more (default medium)")
    parser.add_argument("--steps", type=int, default=300, help="optimization steps (default 300)")
    parser.add_argument("--quality", type=int, default=88, help="WebP quality, 0-100 (default 88)")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--device", help="torch device (default: mps if available, else cpu)")
    parser.add_argument("--compare", type=Path, help="also write a before/after JPEG for checking how the cloak looks")
    parser.add_argument("--no-cloak", action="store_true", help="only convert, crop, and drop the metadata (no cloak, no tests)")
    parser.add_argument("--test-only", action="store_true", help="write nothing; test the existing OUTPUT against the photo (use the same crop options)")
    parser.add_argument("--model-cache", type=Path, help="keep the model weights in this folder and reuse them (default: a temporary folder, deleted at the end)")
    args = parser.parse_args()
    if np is None:
        sys.exit("Missing packages: run this with bin/cloak_photo.sh, which installs them.")

    with tempfile.TemporaryDirectory(prefix="cloak-models-") as tmp:
        MODEL_DIR = (args.model_cache or Path(tmp)).resolve()
        os.environ["TORCH_HOME"] = str(MODEL_DIR / "torch")  # facenet-pytorch and LPIPS weights
        run(args)


if __name__ == "__main__":
    main()
