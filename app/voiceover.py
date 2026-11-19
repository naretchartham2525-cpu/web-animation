"""เสียงพากย์ของผู้ใช้ (ไฟล์เดียวทั้ง EP) → ตัดเป็นท่อนตามประโยคในบท
วิธี: หาช่วงที่มีเสียงพูด → แบ่งตามสัดส่วนความยาวข้อความ → ขยับจุดตัดไปที่ช่วงเงียบที่ใกล้ที่สุด
ผู้ใช้ควรอ่านตามลำดับบท และเว้นจังหวะเล็กน้อย (~0.3 วินาที) ระหว่างประโยค
"""
import re
import subprocess
import wave
from pathlib import Path

import numpy as np

SR = 16000
HOP = 0.02  # วิเคราะห์ทีละ 20 ms


def decode(path, sr=SR):
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "s16le", "-ac", "1", "-ar", str(sr), "-"],
                       capture_output=True)
    if r.returncode != 0 or not r.stdout:
        raise ValueError("อ่านไฟล์เสียงไม่ได้: " + r.stderr.decode(errors="replace")[-200:])
    return np.frombuffer(r.stdout, np.int16).astype(np.float32) / 32768.0


def _weight(text):
    t = re.sub(r"\s+", "", str(text or ""))
    return max(1.0, len(t) * 1.0)


def plan_cuts(a, texts, sr=SR):
    """คืน [(start, end)] เป็นวินาที ต่อ 1 ประโยค"""
    n = len(texts)
    hop = int(HOP * sr)
    frames = max(1, len(a) // hop)
    rms = np.sqrt(np.mean(a[:frames * hop].reshape(frames, hop) ** 2, axis=1) + 1e-12)
    loud = np.percentile(rms, 90) if frames > 5 else rms.max()
    thr = max(0.006, loud * 0.12)
    voiced = rms > thr
    idx = np.nonzero(voiced)[0]
    if not len(idx):
        raise ValueError("ไม่พบเสียงพูดในไฟล์ (เงียบเกินไป)")
    s0, s1 = idx[0] * HOP, (idx[-1] + 1) * HOP
    if n == 1:
        return [(max(0, s0 - 0.05), s1 + 0.1)]
    # ช่วงเงียบ (อย่างน้อย 80 ms) → จุดกึ่งกลางเป็นตัวเลือกจุดตัด
    sil = []
    k = idx[0]
    while k <= idx[-1]:
        if not voiced[k]:
            j = k
            while j <= idx[-1] and not voiced[j]:
                j += 1
            if (j - k) * HOP >= 0.08:
                sil.append(((k + j) / 2 * HOP, (j - k) * HOP))
            k = j
        else:
            k += 1
    w = np.array([_weight(t) for t in texts])
    cum = np.cumsum(w)[:-1] / w.sum()
    span = s1 - s0
    cuts, prev = [], s0
    for i, c in enumerate(cum):
        exp = s0 + c * span
        win = max(1.2, 0.35 * span * w[i] / w.sum() + 0.6)
        cand = [(abs(t - exp) / win - min(d, 0.6), t) for t, d in sil if prev + 0.25 < t < s1 - 0.25 and abs(t - exp) <= win]
        cut = min(cand)[1] if cand else max(prev + 0.3, exp)
        cuts.append(cut)
        prev = cut
    bounds = [s0] + cuts + [s1]
    return [(max(0, bounds[i] - (0.05 if i == 0 else 0)), bounds[i + 1] + (0.1 if i == n - 1 else 0)) for i in range(n)]


def _write_mp3(pcm, out, sr=SR):
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    wav = out.with_suffix(".tmp.wav")
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((np.clip(pcm, -1, 1) * 32767).astype(np.int16).tobytes())
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(wav), "-c:a", "libmp3lame", "-b:a", "128k", str(out)], check=True)
    wav.unlink(missing_ok=True)


def split(audio_path, texts, out_paths, sr=SR):
    """ตัดไฟล์เสียงเป็นท่อนตามประโยค แล้วเขียนเป็น mp3 ตาม out_paths (ลำดับเดียวกับ texts)"""
    a = decode(audio_path, sr)
    cuts = plan_cuts(a, texts, sr)
    for (t0, t1), out in zip(cuts, out_paths):
        seg = a[int(t0 * sr):int(t1 * sr)]
        if len(seg) < sr * 0.2:
            seg = np.concatenate([seg, np.zeros(int(sr * 0.2) - len(seg), np.float32)])
        _write_mp3(seg, out, sr)
    return cuts


def duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0
