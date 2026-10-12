"""API-format graph builders for the models installed in the local ComfyUI.

Settings follow the official ComfyUI templates (comfyui_workflow_templates_json):
- Z-Image Turbo: 8 steps, cfg 1, res_multistep/simple, AuraFlow shift 3, Qwen3-4B text encoder (lumina2).
- Qwen-Image 2.1: 25 steps, cfg 1, euler/simple, Qwen3-VL text encoder, up to 16 reference images.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ZImageModels:
    """Default: the Q4 GGUF files on the Mac. `gguf=False` selects the bf16 files the Vast setup downloads."""

    unet: str = "z_image_turbo-Q4_K_M.gguf"
    clip: str = "Qwen3-4B-Q4_K_M.gguf"
    vae: str = "ae.safetensors"
    gguf: bool = True


ZIMAGE_CUDA = ZImageModels("z_image_turbo_bf16.safetensors", "qwen_3_4b.safetensors", "ae.safetensors", gguf=False)


@dataclass(frozen=True)
class WanI2VModels:
    high: str = "wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors"
    low: str = "wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors"
    lora_high: str = "wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors"
    lora_low: str = "wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors"
    clip: str = "umt5_xxl_fp8_e4m3fn_scaled.safetensors"
    vae: str = "wan_2.1_vae.safetensors"


# the standard Wan negative prompt, minus the "style / artwork / painting" terms that would fight a paper-craft look
WAN_NEGATIVE = (
    "色调艳丽，过曝，静态，细节模糊不清，字幕，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，"
    "画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走"
)


@dataclass(frozen=True)
class QwenImageModels:
    unet: str = "qwen_image_2.1_int8_convrot.safetensors"
    clip: str = "qwen3vl_8b_w4a8.safetensors"
    vae: str = "qwen_image_2.1_vae_bf16.safetensors"


def zimage(
    prompt: str,
    *,
    seed: int,
    width: int = 1024,
    height: int = 1024,
    steps: int = 8,
    init_image: str | None = None,
    denoise: float = 1.0,
    prefix: str = "tracktake/zimage",
    m: ZImageModels | None = None,
) -> dict:
    """Z-Image Turbo txt2img, or img2img when `init_image` (an uploaded input name) is given."""
    m = m or ZImageModels()
    if m.gguf:
        unet = {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": m.unet}}
        clip = {"class_type": "CLIPLoaderGGUF", "inputs": {"clip_name": m.clip, "type": "lumina2"}}
    else:
        unet = {"class_type": "UNETLoader", "inputs": {"unet_name": m.unet, "weight_dtype": "default"}}
        clip = {"class_type": "CLIPLoader", "inputs": {"clip_name": m.clip, "type": "lumina2", "device": "default"}}
    g = {
        "unet": unet,
        "clip": clip,
        "vae": {"class_type": "VAELoader", "inputs": {"vae_name": m.vae}},
        "shift": {"class_type": "ModelSamplingAuraFlow", "inputs": {"model": ["unet", 0], "shift": 3.0}},
        "pos": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["clip", 0], "text": prompt}},
        "neg": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["pos", 0]}},
        "sample": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["shift", 0], "positive": ["pos", 0], "negative": ["neg", 0], "latent_image": None,
                "seed": seed, "steps": steps, "cfg": 1.0, "sampler_name": "res_multistep",
                "scheduler": "simple", "denoise": denoise,
            },
        },
        "decode": {"class_type": "VAEDecode", "inputs": {"samples": ["sample", 0], "vae": ["vae", 0]}},
        "save": {"class_type": "SaveImage", "inputs": {"images": ["decode", 0], "filename_prefix": prefix}},
    }
    if init_image:
        g["load"] = {"class_type": "LoadImage", "inputs": {"image": init_image}}
        g["fit"] = {
            "class_type": "ImageScale",
            "inputs": {"image": ["load", 0], "upscale_method": "lanczos", "width": width, "height": height,
                       "crop": "center"},
        }
        g["encode"] = {"class_type": "VAEEncode", "inputs": {"pixels": ["fit", 0], "vae": ["vae", 0]}}
        g["sample"]["inputs"]["latent_image"] = ["encode", 0]
    else:
        g["latent"] = {"class_type": "EmptySD3LatentImage", "inputs": {"width": width, "height": height, "batch_size": 1}}
        g["sample"]["inputs"]["latent_image"] = ["latent", 0]
    return g


def qwen_edit(
    prompt: str,
    references: list[str],
    *,
    seed: int,
    resolution: int = 1024,
    steps: int = 25,
    negative: str = "",
    prefix: str = "tracktake/qwen",
    m: QwenImageModels | None = None,
) -> dict:
    """Qwen-Image 2.1 generation conditioned on up to 16 uploaded reference images (cover, character, previous frame)."""
    m = m or QwenImageModels()
    if not 1 <= len(references) <= 16:
        raise ValueError("Qwen-Image 2.1 takes 1..16 reference images")
    g: dict = {
        "unet": {"class_type": "UNETLoader", "inputs": {"unet_name": m.unet, "weight_dtype": "default"}},
        "clip": {"class_type": "CLIPLoader", "inputs": {"clip_name": m.clip, "type": "qwen_image", "device": "default"}},
        "vae": {"class_type": "VAELoader", "inputs": {"vae_name": m.vae}},
        "cache": {"class_type": "QwenImage21Cache", "inputs": {"model": ["unet", 0], "device": "auto", "dtype": "default"}},
    }
    encode_inputs: dict = {
        "clip": ["clip", 0], "prompt": prompt, "negative_prompt": negative, "vae": ["vae", 0], "resolution": resolution,
    }
    for i, ref in enumerate(references, start=1):
        g[f"ref{i}"] = {"class_type": "LoadImage", "inputs": {"image": ref}}
        encode_inputs[f"images.image_{i}"] = [f"ref{i}", 0]
    g["encode"] = {"class_type": "TextEncodeQwenImage21", "inputs": encode_inputs}
    g["sample"] = {
        "class_type": "KSampler",
        "inputs": {
            "model": ["cache", 0], "positive": ["encode", 0], "negative": ["encode", 1], "latent_image": ["encode", 2],
            "seed": seed, "steps": steps, "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0,
        },
    }
    g["decode"] = {"class_type": "VAEDecode", "inputs": {"samples": ["sample", 0], "vae": ["vae", 0]}}
    g["save"] = {"class_type": "SaveImage", "inputs": {"images": ["decode", 0], "filename_prefix": prefix}}
    return g


def wan_i2v(
    prompt: str,
    start_image: str,
    *,
    seed: int,
    width: int = 832,
    height: int = 480,
    length: int = 49,
    negative: str = WAN_NEGATIVE,
    prefix: str = "tracktake/wan",
    m: WanI2VModels | None = None,
    end_image: str | None = None,
) -> dict:
    """Wan 2.2 14B image-to-video, 4-step lightx2v LoRAs (high-noise steps 0-2, low-noise 2-4), 16 fps.

    With `end_image` the clip is anchored on both ends (first-last frame): it lands exactly on the next shot's
    keyframe, so a continuous shot flows into the next without a cut.
    Frames are saved as a PNG sequence: the renderer needs single frames, and it avoids the video container nodes.
    """
    m = m or WanI2VModels()
    if (length - 1) % 4:
        raise ValueError("Wan lengths must be 4k+1")
    g: dict = {"load": {"class_type": "LoadImage", "inputs": {"image": start_image}}}
    for tag, unet, lora in (("hi", m.high, m.lora_high), ("lo", m.low, m.lora_low)):
        g[f"unet_{tag}"] = {"class_type": "UNETLoader", "inputs": {"unet_name": unet, "weight_dtype": "default"}}
        g[f"lora_{tag}"] = {"class_type": "LoraLoaderModelOnly",
                            "inputs": {"model": [f"unet_{tag}", 0], "lora_name": lora, "strength_model": 1.0}}
        g[f"shift_{tag}"] = {"class_type": "ModelSamplingSD3", "inputs": {"model": [f"lora_{tag}", 0], "shift": 5.0}}
    g["clip"] = {"class_type": "CLIPLoader", "inputs": {"clip_name": m.clip, "type": "wan", "device": "default"}}
    g["vae"] = {"class_type": "VAELoader", "inputs": {"vae_name": m.vae}}
    g["pos"] = {"class_type": "CLIPTextEncode", "inputs": {"clip": ["clip", 0], "text": prompt}}
    g["neg"] = {"class_type": "CLIPTextEncode", "inputs": {"clip": ["clip", 0], "text": negative}}
    g["i2v"] = {
        "class_type": "WanImageToVideo",
        "inputs": {"positive": ["pos", 0], "negative": ["neg", 0], "vae": ["vae", 0], "width": width, "height": height,
                   "length": length, "batch_size": 1, "start_image": ["load", 0]},
    }
    if end_image:
        g["load_end"] = {"class_type": "LoadImage", "inputs": {"image": end_image}}
        g["i2v"]["class_type"] = "WanFirstLastFrameToVideo"
        g["i2v"]["inputs"]["end_image"] = ["load_end", 0]
    common = {"steps": 4, "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple",
              "positive": ["i2v", 0], "negative": ["i2v", 1]}
    g["s_hi"] = {"class_type": "KSamplerAdvanced", "inputs": {
        **common, "model": ["shift_hi", 0], "add_noise": "enable", "noise_seed": seed, "latent_image": ["i2v", 2],
        "start_at_step": 0, "end_at_step": 2, "return_with_leftover_noise": "enable"}}
    g["s_lo"] = {"class_type": "KSamplerAdvanced", "inputs": {
        **common, "model": ["shift_lo", 0], "add_noise": "disable", "noise_seed": 0, "latent_image": ["s_hi", 0],
        "start_at_step": 2, "end_at_step": 10000, "return_with_leftover_noise": "disable"}}
    g["decode"] = {"class_type": "VAEDecode", "inputs": {"samples": ["s_lo", 0], "vae": ["vae", 0]}}
    g["save"] = {"class_type": "SaveImage", "inputs": {"images": ["decode", 0], "filename_prefix": prefix}}
    return g
