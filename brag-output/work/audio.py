"""Original soundtrack + SFX for the SAAP brag video, written as one piece.

120 BPM, F major. Bar grid starts at t = -1.0 so the drop lands on 3.0 (the reveal).
Effects are pitched to the current chord and share the music's reverb.
"""
import numpy as np
from scipy.signal import butter, sosfilt, fftconvolve
import wave, sys

SR = 48000
DUR = 21.5
N = int(SR * DUR)
BEAT = 0.5
rng = np.random.default_rng(7)

def t_axis(n): return np.arange(n) / SR
def midi(m): return 440.0 * 2 ** ((m - 69) / 12)
def lp(x, f, o=2): return sosfilt(butter(o, f, "low", fs=SR, output="sos"), x)
def hp(x, f, o=2): return sosfilt(butter(o, f, "high", fs=SR, output="sos"), x)
def bp(x, lo, hi, o=2): return sosfilt(butter(o, [lo, hi], "band", fs=SR, output="sos"), x)

def place(buf, sig, at, gain=1.0):
    i = int(round(at * SR))
    if i >= len(buf): return
    j = min(len(buf), i + len(sig))
    if i < 0: sig, i = sig[-i:], 0; j = min(len(buf), len(sig))
    buf[i:j] += sig[: j - i] * gain

def saw(f, n, phase=0.0):
    ph = (np.arange(n) * f / SR + phase) % 1.0
    return 2 * ph - 1

def env_adsr(n, a=0.01, d=0.1, s=0.7, r=0.2):
    e = np.ones(n) * s
    na, nd, nr = int(a * SR), int(d * SR), int(r * SR)
    na = min(na, n); e[:na] = np.linspace(0, 1, na)
    nd = min(nd, n - na); e[na:na + nd] = np.linspace(1, s, nd)
    if nr < n: e[n - nr:] *= np.linspace(1, 0, nr)
    return e

# ---------------------------------------------------------------- harmony
# chord tones as MIDI; bars of 2 s starting at -1.0
F, C, Dm, Bb, Csus = [53, 57, 60, 65], [48, 55, 60, 64], [50, 57, 62, 65], [46, 53, 58, 62], [48, 53, 55, 60]
bars = [(-1.0, Dm), (1.0, Bb), (3.0, F), (5.0, C), (7.0, Dm), (9.0, Bb), (11.0, F), (13.0, C), (15.0, Dm), (17.0, Bb), (18.0, Csus), (19.0, F)]
def chord_at(t):
    cur = bars[0][1]
    for s, ch in bars:
        if t >= s: cur = ch
    return cur
def bar_end(i): return bars[i + 1][0] if i + 1 < len(bars) else DUR + 0.5

L = np.zeros(N); R = np.zeros(N)
send = np.zeros(N)   # shared reverb send (mono)

# sidechain envelope from kicks (applied to pad + bass)
kick_times = [3.0 + k * BEAT for k in range(int((18.0 - 3.0) / BEAT))]
duck = np.ones(N)
for kt in kick_times:
    i = int(kt * SR); n = int(0.28 * SR)
    seg = 1 - 0.55 * np.exp(-np.arange(n) / (0.09 * SR))
    duck[i:i + n] = np.minimum(duck[i:i + n], seg[: len(duck[i:i + n])])

# ---------------------------------------------------------------- pad (supersaw, filtered)
pad = np.zeros(N)
for bi, (s, ch) in enumerate(bars):
    e = bar_end(bi)
    st = max(0.0, s); n = int((e - st + 0.25) * SR)
    if n <= 0: continue
    sig = np.zeros(n)
    for m in ch + [ch[0] + 12]:
        for d in (-0.12, -0.05, 0.0, 0.05, 0.12):
            sig += saw(midi(m) * 2 ** (d / 12), n, rng.random())
    sig *= env_adsr(n, a=0.08 if s > 0 else 0.6, d=0.2, s=0.8, r=0.3) / 25
    place(pad, sig, st)
# filter: intro opens 500 -> 2400 Hz, then stays bright, outro mellows
cut_curve = np.interp(t_axis(N), [0, 2.9, 3.0, 17.9, 19.0, 21.5], [450, 1500, 2400, 2400, 1800, 900])
# time-varying LP via block processing
pad_f = np.zeros(N); blk = 1024
from scipy.signal import sosfilt_zi
for i in range(0, N, blk):
    sos = butter(2, cut_curve[i], "low", fs=SR, output="sos")
    if i == 0: zi = sosfilt_zi(sos) * 0
    pad_f[i:i + blk], zi = sosfilt(sos, pad[i:i + blk], zi=zi)
pad_f *= duck
L += pad_f * 0.9; R += pad_f * 0.9; send += pad_f * 0.25

# ---------------------------------------------------------------- pluck arpeggio (16ths), with stereo delay
pluck = np.zeros(N)
def pluck_note(f, dur=0.22, bright=5000):
    n = int(dur * SR); tt = t_axis(n)
    s = (saw(f, n) * 0.6 + np.sin(2 * np.pi * f * tt) * 0.6) * np.exp(-tt / 0.07)
    return lp(s, bright)
step = BEAT / 4
pattern = [0, 1, 2, 3, 2, 1, 3, 2]
k = 0; tt0 = 0.0
while tt0 < 18.0:
    ch = chord_at(tt0)
    notes = sorted(ch)[1:] + [sorted(ch)[1] + 12]
    m = notes[pattern[k % len(pattern)] % len(notes)] + 12
    vel = 0.55 if tt0 < 3.0 else 0.8
    if tt0 < 3.0 and k % 2: vel = 0.0       # intro: sparse 8ths
    if 6.5 <= tt0 < 10.5 and k % 4 == 3: vel *= 0.6
    if vel: place(pluck, pluck_note(midi(m), bright=2500 if tt0 < 3 else 5200) * vel, tt0)
    k += 1; tt0 = round(tt0 + step, 6)
pl = pluck * 0.42
dl = int(0.375 * SR)
pl_l = pl.copy(); pl_r = pl.copy()
pl_r[dl:] += pl[:-dl] * 0.35
pl_l[2 * dl:] += pl[:-2 * dl] * 0.2
L += pl_l; R += pl_r; send += pl * 0.5

# ---------------------------------------------------------------- bass (8ths, from the drop)
bass = np.zeros(N)
tb = 3.0
while tb < 18.0:
    root = sorted(chord_at(tb))[0] - 12
    n = int(0.22 * SR); tt = t_axis(n)
    f = midi(root)
    s = np.sin(2 * np.pi * f * tt) + 0.35 * lp(saw(f, n), 600)
    s *= env_adsr(n, a=0.004, d=0.08, s=0.75, r=0.06)
    place(bass, s, tb)
    tb = round(tb + BEAT / 2, 6)
bass = lp(bass, 900) * duck * 0.27
L += bass; R += bass

# ---------------------------------------------------------------- drums
def kick():
    n = int(0.38 * SR); tt = t_axis(n)
    f = 45 + 110 * np.exp(-tt / 0.035)
    ph = 2 * np.pi * np.cumsum(f) / SR
    s = np.sin(ph) * np.exp(-tt / 0.13)
    s[: int(0.003 * SR)] += rng.normal(0, 0.3, int(0.003 * SR))
    return lp(s, 3500)
def clap():
    n = int(0.25 * SR); tt = t_axis(n)
    nz = rng.normal(0, 1, n)
    e = np.exp(-tt / 0.06)
    for off in (0.0, 0.011, 0.022):
        e += 0.6 * np.exp(-np.maximum(tt - off, 0) / 0.006) * (tt >= off)
    return bp(nz, 900, 5000) * e * 0.5
def hat(dur=0.035):
    n = int(dur * SR); tt = t_axis(n)
    return hp(rng.normal(0, 1, n), 7500) * np.exp(-tt / (dur / 3))

dr = np.zeros(N)
for kt in kick_times: place(dr, kick(), kt, 0.75)
for kt in kick_times:
    beat_idx = int(round((kt - 3.0) / BEAT))
    if beat_idx % 2 == 1: place(dr, clap(), kt, 0.42); place(send, clap(), kt, 0.15)
    place(dr, hat(), kt + BEAT / 2, 0.16)
    if 10.5 <= kt < 14.5:   # a touch more drive under the early-warning scene
        place(dr, hat(0.02), kt + BEAT / 4, 0.07); place(dr, hat(0.02), kt + 3 * BEAT / 4, 0.07)
# intro: two soft heartbeat kicks under the hook
for kt in (0.0, 1.0, 2.0): place(dr, lp(kick(), 300), kt, 0.45)
# fill into the outro
for j, kt in enumerate(np.arange(17.5, 18.0, BEAT / 4)): place(dr, clap(), kt, 0.12 + 0.06 * j)
dr *= 0.36
L += dr; R += dr

# ---------------------------------------------------------------- risers / whooshes / hits
def whoosh(dur=0.5, lo=400, hi=6000, rise=True):
    n = int(dur * SR); tt = t_axis(n)
    nz = rng.normal(0, 1, n)
    out = np.zeros(n); blkn = 512; zi = None
    for i in range(0, n, blkn):
        k_ = i / n if rise else 1 - i / n
        fc = lo * (hi / lo) ** k_
        sos = butter(2, [fc * 0.7, min(fc * 1.4, SR / 2 - 100)], "band", fs=SR, output="sos")
        if zi is None: zi = np.zeros((sos.shape[0], 2))
        out[i:i + blkn], zi = sosfilt(sos, nz[i:i + blkn], zi=zi)
    e = np.sin(np.pi * np.clip(tt / dur, 0, 1)) ** 2
    return out * e

fx = np.zeros(N)
# riser into the drop
r = whoosh(1.0, 300, 7000); place(fx, r * np.linspace(0.2, 1, len(r)), 2.0, 0.22)
# sub drop at the reveal + at the final chord
def sub_hit(f=midi(29), dur=1.4):
    n = int(dur * SR); tt = t_axis(n)
    return np.sin(2 * np.pi * f * tt * (1 + 0.5 * np.exp(-tt / 0.05))) * np.exp(-tt / 0.45)
place(fx, sub_hit(), 3.0, 0.4)
place(fx, sub_hit(), 19.0, 0.38)
# scene-change whooshes (centred just before each cut)
for tcut in (6.5, 10.5, 14.5, 18.0): place(fx, whoosh(0.45, 500, 5000), tcut - 0.3, 0.12)

def bell(f, dur=1.2, bright=1.0):
    n = int(dur * SR); tt = t_axis(n)
    s = np.sin(2 * np.pi * f * tt) * np.exp(-tt / 0.5)
    s += 0.35 * bright * np.sin(2 * np.pi * f * 2.0 * tt) * np.exp(-tt / 0.25)
    s += 0.12 * bright * np.sin(2 * np.pi * f * 3.01 * tt) * np.exp(-tt / 0.12)
    s[: int(0.002 * SR)] *= np.linspace(0, 1, int(0.002 * SR))
    return s

def blip(f):
    n = int(0.12 * SR); tt = t_axis(n)
    s = np.sin(2 * np.pi * f * tt) * np.exp(-tt / 0.035)
    s += 0.25 * lp(rng.normal(0, 1, n), 3000) * np.exp(-tt / 0.004)
    return s

ui = np.zeros(N)
# reveal: brand mark pop (F major triad bell)
for j, m in enumerate((77, 81, 84)): place(ui, bell(midi(m), 1.0, 0.6), 3.0 + j * 0.06, 0.07)
# rubric clicks: rising Dm-chord blips (bar at 7.0 is Dm), score sparkle on the last
for j, (tc, m) in enumerate(zip((7.0, 7.5, 8.0, 8.5), (74, 77, 81, 86))): place(ui, blip(midi(m)), tc, 0.16)
for j, m in enumerate((86, 89)): place(ui, bell(midi(m), 0.9, 0.5), 8.55 + j * 0.07, 0.05)
# risk rows sliding in (bar at 11.0 is F): soft airy swishes
for j in range(4): place(ui, whoosh(0.18, 1500, 6000), 10.7 + j * 0.2, 0.06)
# warning ring on 97%: low soft knock on the chord's D? -> use C (bar at 11 is F, C is in chord)
place(ui, lp(bell(midi(60), 0.6, 0.2), 1800), 12.1, 0.13)
# highlighter swipe
place(ui, whoosh(0.55, 2000, 7000), 12.6, 0.05)
# attainment click + PDF rise + success chime (bar at 15.0 is Dm -> F A C D fits)
place(ui, blip(midi(84)), 15.5, 0.16)
place(ui, whoosh(0.6, 300, 4000), 15.62, 0.12)
for j, m in enumerate((77, 81, 84, 86)): place(ui, bell(midi(m), 1.0, 0.7), 16.15 + j * 0.08, 0.06)
# outro chord hit (F) rings out
for m in (65, 69, 72, 77): place(ui, bell(midi(m), 2.6, 0.5), 19.0, 0.05)

ui = lp(ui, 9000)
L += fx + ui; R += fx + ui
send += fx * 0.3 + ui * 0.7

# ---------------------------------------------------------------- shared reverb (synthetic plate)
ir_n = int(1.6 * SR); it = t_axis(ir_n)
ir_l = rng.normal(0, 1, ir_n) * np.exp(-it / 0.38); ir_r = rng.normal(0, 1, ir_n) * np.exp(-it / 0.38)
ir_l = lp(hp(ir_l, 250), 6000); ir_r = lp(hp(ir_r, 250), 6000)
ir_l /= np.sqrt(np.sum(ir_l ** 2)); ir_r /= np.sqrt(np.sum(ir_r ** 2))
pre = int(0.018 * SR)
send_d = np.concatenate([np.zeros(pre), send])[:N]
L += fftconvolve(send_d, ir_l)[:N] * 0.32
R += fftconvolve(send_d, ir_r)[:N] * 0.32

# ---------------------------------------------------------------- master: gentle glue, fades
mix = np.stack([L, R], 1)
mix = hp(mix.T, 30).T
fade_in = np.clip(t_axis(N) / 0.02, 0, 1)
fade_out = np.clip((DUR - t_axis(N)) / 1.0, 0, 1) ** 1.5
mix *= (fade_in * fade_out)[:, None]
# soft clip for glue
peak = np.max(np.abs(mix)); mix = mix / peak * 0.9
mix = np.tanh(mix * 1.05) / np.tanh(1.05)
out = (mix * 32767 * 0.95).astype(np.int16)
with wave.open(sys.argv[1] if len(sys.argv) > 1 else "audio.wav", "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(out.tobytes())
print("ok", out.shape)
