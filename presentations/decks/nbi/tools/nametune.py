"""Cut the three "Name That Tune" clips for the degeneracy aside (page-12) and the
Bayes factor a listener accumulates while each one plays.

Run `python tools/nametune.py` from the deck folder.  Sources live in
`tools/audio/` (git-ignored); outputs:

    static/nametune/<clip>.mp3               what the slide plays
    static/nametune/nametune.json            clip list + log10 B(t) curves for the slide
    tools/audio/out/<clip>.wav, <clip>.png   lossless copies + labelled check spectrograms

THE CLIPS (slide order)
-----------------------
1_through_the_wall_*  (dropped from the slide; `through_the_wall()` is kept but not called.)
                      Grieg, In the Hall of the Mountain King, the opening theme (it sits in
                      the bassoons / low strings, so a 400 Hz low-pass leaves the tune intact).
                      Low-passed, a short room reverb, under a constant noise bed (pink + brown
                      + 50 Hz hum + crowd murmur).  One render per SNR in SNRS_DB; SNR is music
                      RMS over noise RMS *after* the wall, broadband.
2_another_room        "mr. brightside from another room" (YouTube 5OEa6NzTSOo), already muffled
                      by its maker; only cut and levelled.  The listener's template is the
                      original song (aligned by cross-correlation) through the room's transfer
                      function, fitted per mel band as data ~ g_k * original + N_k.
3_short_decisive      Beethoven 5, the opening ta-ta-ta-TAAA.  Loud, clean, ~3 s + pads.
4_impostor            Ice Ice Baby from its first note (the Under Pressure bass riff), long
                      enough that the moment the listener's B turns decisive lands ~2/3 in.
Recordings: Wikimedia Commons, public domain -- Beethoven 5/i (Musopen), Grieg Peer Gynt
Suite 1/iv (Musopen Symphony).  YouTube (yt-dlp, official uploads): Ice Ice Baby, Under
Pressure (competitor for clip 2), Mr. Brightside, and the "from another room" version.  Edit the CUT_* constants
to move a window.

THE BAYES FACTOR (a cartoon listener, but an honest one)
--------------------------------------------------------
The listener hears a log-power mel spectrogram y[t, k] (FPS frames/s) and holds each
candidate tune H in memory as a template: mu_H = log(P_H + N), with P_H the template's mel
power as it would arrive at the ear and N the expected noise power in that band.  Each frame
adds

    d ln B = sum_k [ (y - mu_0)^2 - (y - mu_1)^2 ] / (2 sigma_k^2),
    sigma_k^2 = Var(log noise power in band k) + SIGMA_MEM^2

The second term is the listener's memory blur.  SIGMA_MEM was set so the -10 dB wall clip
turned decisive (log10 B = 2) a few seconds in.  The muffled room clip carries no noise bed, so
with that blur it went decisive in 0.7 s and reached log10 B ~ 130; it gets its own, larger
ROOM_SIGMA_MEM (a muffled song is remembered less sharply), set so its B climbs across the whole
clip (decisive ~2 s, ~9 at 10 s).  Everything else is measured.
The competing hypotheses:
  clips 1-3   the right tune vs another well-known tune pushed through the same wall/room and
              matched in loudness frame by frame, so B is "which song", not "is there sound";
  clip 4      Ice Ice Baby vs "Under Pressure" = Ice Ice Baby's own first two bars, looped (bar
              length to the sample).  Ice Ice Baby samples the riff as a loop, so while only the riff
              plays both predict the same sound and B stays at 1: that is the degeneracy.
              (The real Under Pressure recording was tried as the template; different mix and
              percussion made B decisive within 0.2 s, which is not what a listener hears.)
"""
import json
import subprocess
from pathlib import Path

import numpy as np
from scipy.signal import fftconvolve, butter, sosfilt, stft

DECK = Path(__file__).resolve().parent.parent
SRC = DECK / 'tools' / 'audio'
OUT_STATIC = DECK / 'static' / 'nametune'
OUT_WAV = SRC / 'out'

SR = 48000
FADE = 0.03                      # s, raised-cosine fade at every cut
PAD = 0.5                        # s of silence either side of the short clip
LUFS_LOUD = -16.0                # short & impostor
LUFS_WALL = -26.0                # through the wall: quieter by design
LUFS_ROOM = -23.0                # another room
TRUE_PEAK = -1.0                 # dBFS ceiling after normalising

CUT_WALL = ('mountain_king.flac', 3.4, 13.4)            # theme from its first note, 10 s
WALL_LOWPASS = 400.0             # Hz, 4th order
WALL_RT60 = 0.35                 # s, synthetic room
WALL_WET = 0.35                  # reverb mix
SNRS_DB = (-6, -10, -14)
CHOSEN_SNR = -10                 # the one the slide plays by default
CUT_ROOM = ('brightside_another_room.mp3', 14.0, 24.0)  # steady level from ~14 s on
ROOM_ORIGINAL = 'brightside.mp3'
CUT_SHORT = ('beethoven5.ogg', 0.80, 4.12)              # ta-ta-ta-TAAA, to the fermata's release (onset 0.84 s)
IMP = 'ice_ice_baby.mp3'
IMP_SEARCH = 24.0                # look for the reveal up to here
REVEAL_FRAC = 2 / 3

FPS = 20                         # frames per second of the listener / of the curve
SIGMA_MEM = 4.0                  # memory blur, nats of log power (see docstring)
ROOM_SIGMA_MEM = 16.0            # the muffled song's own blur (see docstring)
SEED = 20261020


# --- io --------------------------------------------------------------------------------
def load(name, ss=0.0, t=None, ch=2, af=None):
    cmd = ['ffmpeg', '-v', 'error', '-ss', f'{ss}', '-i', str(SRC / name)]
    cmd += (['-t', f'{t}'] if t else []) + (['-af', af] if af else [])
    cmd += ['-ac', str(ch), '-ar', str(SR), '-f', 'f32le', '-']
    x = np.frombuffer(subprocess.run(cmd, capture_output=True, check=True).stdout, np.float32)
    return x.reshape(-1, ch).astype(np.float64)


def write(x, stem):
    x = np.atleast_2d(x.T).T
    OUT_WAV.mkdir(parents=True, exist_ok=True)
    OUT_STATIC.mkdir(parents=True, exist_ok=True)
    raw = np.clip(x, -1, 1).astype('<f4').tobytes()
    base = ['ffmpeg', '-v', 'error', '-y', '-f', 'f32le', '-ar', str(SR), '-ac', str(x.shape[1]), '-i', '-']
    subprocess.run(base + ['-c:a', 'pcm_s24le', str(OUT_WAV / f'{stem}.wav')], input=raw, check=True)
    subprocess.run(base + ['-c:a', 'libmp3lame', '-b:a', '192k', str(OUT_STATIC / f'{stem}.mp3')],
                   input=raw, check=True)


def lufs(x):
    """Integrated loudness (EBU R128) via ffmpeg's ebur128 filter."""
    x = np.atleast_2d(x.T).T
    cmd = ['ffmpeg', '-v', 'info', '-nostats', '-f', 'f32le', '-ar', str(SR), '-ac', str(x.shape[1]),
           '-i', '-', '-af', 'ebur128=peak=true', '-f', 'null', '-']
    err = subprocess.run(cmd, input=x.astype('<f4').tobytes(), capture_output=True).stderr.decode()
    summary = err[err.rindex('Summary:'):]
    return float(summary.split('I:')[1].split('LUFS')[0])


def normalise(x, target):
    g = 10 ** ((target - lufs(x)) / 20)
    peak = np.max(np.abs(x * g))
    ceiling = 10 ** (TRUE_PEAK / 20)
    if peak > ceiling:                      # sample peak; keeps -1 dBFS headroom
        g *= ceiling / peak
    return x * g


def fade(x, t=FADE):
    n = int(t * SR)
    w = 0.5 - 0.5 * np.cos(np.linspace(0, np.pi, n))
    x = x.copy()
    x[:n] *= w[:, None] if x.ndim == 2 else w
    x[-n:] *= w[::-1, None] if x.ndim == 2 else w[::-1]
    return x


def rms(x):
    return float(np.sqrt(np.mean(np.square(x))))


# --- the wall ----------------------------------------------------------------------------
def coloured(n, alpha, rng):
    """1/f^alpha noise (alpha=1 pink, 2 brown), unit RMS."""
    spec = np.fft.rfft(rng.standard_normal(n))
    f = np.fft.rfftfreq(n, 1 / SR)
    f[0] = f[1]
    spec /= f ** (alpha / 2)
    spec[f < 20] = 0
    y = np.fft.irfft(spec, n)
    return y / rms(y)


def murmur(n, rng, voices=14):
    """Crowd murmur: band-passed noise, each voice switched by a syllable-rate envelope."""
    sos = butter(4, [250, 1800], 'bandpass', fs=SR, output='sos')
    t = np.arange(n) / SR
    out = np.zeros(n)
    for _ in range(voices):
        v = sosfilt(sos, rng.standard_normal(n))
        rate = rng.uniform(3, 6)
        env = np.clip(np.sin(2 * np.pi * rate * t + rng.uniform(0, 6.3)) + rng.uniform(-.2, .6), 0, None)
        env *= 0.5 + 0.5 * np.clip(np.sin(2 * np.pi * rng.uniform(.1, .3) * t + rng.uniform(0, 6.3)), 0, None)
        out += v * env
    return out / rms(out)


def noise_bed(n, rng):
    t = np.arange(n) / SR
    hum = sum(a * np.sin(2 * np.pi * 50 * h * t) for h, a in ((1, 1), (2, .5), (3, .25)))
    bed = (1.0 * coloured(n, 1, rng) + 0.8 * coloured(n, 2, rng)
           + 0.25 * hum / rms(hum) + 0.45 * murmur(n, rng))
    return bed / rms(bed)


def wall(x, rng):
    """Mono, low-passed, a little room. Returns unit-RMS music as heard through the wall."""
    m = x.mean(1)
    m = sosfilt(butter(4, WALL_LOWPASS, 'lowpass', fs=SR, output='sos'), m)
    n = int(WALL_RT60 * SR)
    ir = rng.standard_normal(n) * np.exp(-6.9 * np.arange(n) / n)          # -60 dB at RT60
    ir = sosfilt(butter(2, 1500, 'lowpass', fs=SR, output='sos'), ir)
    wet = fftconvolve(m, ir)[:len(m)]
    y = (1 - WALL_WET) * m / rms(m) + WALL_WET * wet / rms(wet)
    return y / rms(y)


# --- alignment ---------------------------------------------------------------------------
def onset_env(x, hop=480, band=(40, 4000)):
    m = x.mean(1) if x.ndim == 2 else x
    f, _, Z = stft(m, SR, nperseg=4096, noverlap=4096 - hop, boundary=None, padded=False)
    L = np.log((np.abs(Z) ** 2)[(f > band[0]) & (f < band[1])] + 1e-12)
    o = np.clip(np.diff(L, axis=1), 0, None).sum(0)
    return o - o.mean()


def offset(x, y, hop=480, band=(40, 4000)):
    """Lag (s) of y behind x, i.e. x(t) ~ y(t - lag), by onset-envelope cross-correlation."""
    a, b = onset_env(x, hop, band), onset_env(y, hop, band)
    xc = fftconvolve(a, b[::-1], 'full')
    return (int(np.argmax(xc)) - (len(b) - 1)) * hop / SR


def bar_length(x, lo=1.8, hi=2.4, hop=120):
    o = onset_env(x, hop)
    ac = np.correlate(o, o, 'full')[len(o) - 1:]
    lag = np.arange(len(ac)) * hop / SR
    ok = np.nonzero((lag > lo) & (lag < hi))[0]
    i = ok[np.argmax(ac[ok])]
    a, b, c = ac[i - 1:i + 2]
    return (i + 0.5 * (a - c) / (a - 2 * b + c)) * hop / SR


# --- the listener ------------------------------------------------------------------------
def melbank(fmin, fmax, nb, freqs):
    mel = lambda f: 2595 * np.log10(1 + f / 700)
    imel = lambda m: 700 * (10 ** (m / 2595) - 1)
    edges = imel(np.linspace(mel(fmin), mel(fmax), nb + 2))
    W = np.zeros((nb, len(freqs)))
    for i in range(nb):
        lo, c, hi = edges[i:i + 3]
        W[i] = np.clip(np.minimum((freqs - lo) / (c - lo), (hi - freqs) / (hi - c)), 0, None)
    return W


def melpow(x, fmax, nb):
    m = x.mean(1) if x.ndim == 2 else x
    f, _, Z = stft(m, SR, nperseg=4096, noverlap=4096 - SR // FPS, boundary=None, padded=False)
    return melbank(40, fmax, nb, f) @ (np.abs(Z) ** 2)          # (nb, frames)


def log10_bayes(data, right, wrong, noise_power, noise_logvar, sigma_mem=None):
    """Cumulative log10 B(right:wrong), one value per frame boundary, starting at 0.

    The wrong tune is rescaled frame by frame to the right tune's loudness, so only *which
    notes* count as evidence, not how loud the competitor happened to be at that instant
    (otherwise the short clip's leading silence alone would be decisive).
    """
    n = min(data.shape[1], right.shape[1], wrong.shape[1])
    data, right, wrong = data[:, :n], right[:, :n], wrong[:, :n]
    wrong = wrong * (right.sum(0) / (wrong.sum(0) + 1e-30))[None, :]
    y = np.log(data + 1e-30)
    mu1 = np.log(right + noise_power[:, None] + 1e-30)
    mu0 = np.log(wrong + noise_power[:, None] + 1e-30)
    s2 = (noise_logvar + (SIGMA_MEM if sigma_mem is None else sigma_mem) ** 2)[:, None]
    d = (((y - mu0) ** 2 - (y - mu1) ** 2) / (2 * s2)).sum(0)
    return np.concatenate([[0.0], np.cumsum(d)]) / np.log(10)


def curve(values):
    return {'t': [round(i / FPS, 3) for i in range(len(values))], 'log10B': [round(float(v), 3) for v in values]}


def decisive_at(lb):
    hit = np.nonzero(np.asarray(lb) >= 2)[0]
    return hit[0] / FPS if len(hit) else None


# --- check spectrograms (not shown on the slide) -------------------------------------------
def spectrogram(x, stem, title, fmax, marks=()):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    m = x.mean(1) if x.ndim == 2 else x
    f, t, Z = stft(m, SR, nperseg=8192, noverlap=8192 - 480)
    S = 10 * np.log10(np.abs(Z) ** 2 + 1e-12)
    keep = f <= fmax
    vmax = np.percentile(S[keep], 99.5)
    fig, ax = plt.subplots(figsize=(9, 3.4), dpi=110)
    ax.pcolormesh(t, f[keep], S[keep], vmin=vmax - 70, vmax=vmax, cmap='magma', shading='auto', rasterized=True)
    ax.set_yscale('symlog', linthresh=200)
    ax.set_ylim(30, fmax)
    for tm, lab in marks:
        ax.axvline(tm, color='w', ls='--', lw=1)
        ax.text(tm, fmax * .7, f' {lab}', color='w', fontsize=8)
    ax.set(xlabel='time in clip [s]', ylabel='f [Hz]', title=title)
    fig.tight_layout()
    fig.savefig(OUT_WAV / f'{stem}.png')
    plt.close(fig)


# --- clips -------------------------------------------------------------------------------
def through_the_wall(rng):
    name, a, b = CUT_WALL
    n = int((b - a) * SR)
    music = wall(fade(load(name, a, b - a)), rng)[:n]
    bed = noise_bed(n, rng)
    alt = wall(fade(load(CUT_SHORT[0], 0.8, b - a)), np.random.default_rng(SEED + 1))[:n]
    # what the listener knows about the noise: its mean mel power and log-power scatter
    Pn = melpow(bed, 600, 16)
    noise_power, noise_logvar = Pn.mean(1), np.log(Pn).var(1)
    variants = []
    for snr in SNRS_DB:
        g = 10 ** (snr / 20)
        mix = fade(g * music + bed)
        k = 10 ** ((LUFS_WALL - lufs(mix)) / 20)
        mix *= k
        stem = f'1_through_the_wall_{snr}dB'
        write(mix, stem)
        spectrogram(mix, stem, f'through the wall: {name} {a}-{b} s, music {snr} dB re noise', 2000)
        lb = log10_bayes(melpow(mix, 600, 16) / k ** 2, melpow(g * music, 600, 16), melpow(g * alt, 600, 16),
                         noise_power, noise_logvar)
        inband = 10 * np.log10(melpow(g * music, 600, 16).sum() / Pn.sum())
        variants.append({'snr_db': snr, 'src': f'{stem}.mp3', **curve(lb),
                         'inband_snr_db': round(float(inband), 1), 'lufs': lufs(mix)})
    return {'id': 'through_the_wall', 'title': 'Through the wall', 'sub': 'a party next door',
            'answer': 'Grieg, In the Hall of the Mountain King', 'duration': n / SR,
            'chosen': CHOSEN_SNR, 'variants': variants,
            'settings': {'source': name, 'start': a, 'end': b, 'lowpass_hz': WALL_LOWPASS, 'rt60_s': WALL_RT60,
                         'wet': WALL_WET, 'lufs_target': LUFS_WALL}}


def another_room(rng):
    name, a, b = CUT_ROOM
    x = normalise(fade(load(name, a, b - a)), LUFS_ROOM)
    write(x, '2_another_room')
    spectrogram(x, '2_another_room', f'another room: {name} {a}-{b} s', 4000)
    # the original, aligned on the bass band (all the room lets through) over the first minute
    o0 = a + offset(load(name, 0, 60), load(ROOM_ORIGINAL, 0, 70), band=(40, 400)) * -1
    orig = load(ROOM_ORIGINAL, o0, b - a)
    P, Po = melpow(x, 4000, 40), melpow(orig, 4000, 40)
    n = min(P.shape[1], Po.shape[1])
    P, Po = P[:, :n], Po[:, :n]
    # the room, per band: P ~ g * Po + N (least squares, both non-negative)
    g, N = np.zeros(40), np.zeros(40)
    for k in range(40):
        A = np.vstack([Po[k], np.ones(n)]).T
        g[k], N[k] = np.clip(np.linalg.lstsq(A, P[k], rcond=None)[0], 1e-30, None)
    resid = np.log(P + 1e-30) - np.log(g[:, None] * Po + N[:, None])
    # competitor: Under Pressure through the same room, same loudness frame by frame
    alt = melpow(load('under_pressure.mp3', 40.0, b - a), 4000, 40)
    lb = log10_bayes(P, g[:, None] * Po, g[:, None] * alt, N, resid.var(1), ROOM_SIGMA_MEM)
    return {'id': 'another_room', 'title': 'In another room', 'sub': 'muffled, no noise',
            'answer': 'The Killers, Mr. Brightside', 'src': '2_another_room.mp3', 'duration': len(x) / SR,
            **curve(lb),
            'settings': {'source': name, 'start': a, 'end': b, 'original_at': round(o0, 3),
                         'room_fit_rms_nats': round(float(np.sqrt(np.mean(resid ** 2))), 2), 'lufs': lufs(x)}}


def short_decisive(rng):
    name, a, b = CUT_SHORT
    x = fade(load(name, a, b - a))
    pad = np.zeros((int(PAD * SR), 2))
    x = normalise(np.vstack([pad, x, pad]), LUFS_LOUD)
    write(x, '3_short_decisive')
    spectrogram(x, '3_short_decisive', f'short & decisive: {name} {a}-{b} s (+{PAD} s pads)', 4000)
    # vs Mountain King's loudest passage, matched in loudness
    alt = load(CUT_WALL[0], 110.0, len(x) / SR)
    P = melpow(x, 4000, 40)
    floor = 1e-3 * P.mean(1)                                   # a 30 dB listening room
    lb = log10_bayes(P, P, melpow(alt, 4000, 40), floor, np.full(40, 0.31))
    return {'id': 'short_decisive', 'title': 'Short but decisive', 'sub': 'loud, four notes',
            'answer': 'Beethoven, Symphony No. 5', 'src': '3_short_decisive.mp3', 'duration': len(x) / SR,
            **curve(lb), 'settings': {'source': name, 'start': a, 'end': b, 'pad_s': PAD, 'lufs': lufs(x)}}


def first_note(x):
    """First time the bass (<250 Hz) 20 ms RMS reaches 10% of its loud level (95th percentile);
    skips the official video's opening, which is near-silent apart from a hiss/click at 3.5 s."""
    m = sosfilt(butter(4, 250, 'lowpass', fs=SR, output='sos'), x.mean(1))
    w = int(0.02 * SR)
    e = np.sqrt(np.convolve(m ** 2, np.ones(w) / w, 'same'))
    return float(np.nonzero(e > 0.1 * np.percentile(e, 95))[0][0]) / SR


def exact_bar(x, guess):
    """Refine a bar length to the sample: the lag that best overlays bar 1 on bar 2."""
    n = int(guess * SR)
    one = x[:n].mean(1)
    lags = np.arange(int((guess - 0.03) * SR), int((guess + 0.03) * SR))
    two = x[lags[0]:lags[-1] + n].mean(1)
    xc = fftconvolve(two, one[::-1], 'valid')
    return lags[int(np.argmax(xc))] / SR


def impostor(rng):
    if not (SRC / IMP).exists():
        print(f'impostor skipped: put {IMP} in {SRC}')
        return None
    whole = load(IMP, 0, IMP_SEARCH)
    start = first_note(whole) - 0.05
    x = whole[int(start * SR):]
    bar = exact_bar(x, bar_length(x[:8 * SR]))
    # Under Pressure, as the listener holds it: the riff's two-bar phrase, carrying on. Ice Ice
    # Baby samples it as a loop, so until something new comes in (the vocals, ~12.8 s in this
    # upload) the two hypotheses predict the *same* sound. One bar is not enough: bar 2 varies
    # bar 1 slightly and B crept up from 10.8 s on.
    one = x[:int(round(2 * bar * SR))]
    up = np.tile(one, (int(np.ceil(len(x) / len(one))), 1))[:len(x)]
    P = melpow(x, 4000, 40)
    floor = 1e-3 * P.mean(1)
    lb = log10_bayes(P, P, melpow(up, 4000, 40), floor, np.full(40, 0.31))
    reveal = decisive_at(lb)
    if reveal is None:
        raise SystemExit(f'impostor: B never turns decisive by {IMP_SEARCH} s; widen IMP_SEARCH')
    length = min(len(x) / SR, max(reveal / REVEAL_FRAC, reveal + 2.0))
    clip = normalise(fade(x[:int(length * SR)]), LUFS_LOUD)
    write(clip, '4_impostor')
    spectrogram(clip, '4_impostor', f'impostor: {IMP} {start:.2f}-{start + length:.2f} s', 4000,
                marks=[(reveal, 'B decisive')] + [(k * bar, f'bar {k + 1}') for k in range(1, int(length / bar) + 1)])
    lb = lb[:int(length * FPS) + 1]
    return {'id': 'impostor', 'title': 'The impostor', 'sub': 'which song is it?',
            'answer': 'Vanilla Ice, Ice Ice Baby', 'alt_answer': 'Queen & Bowie, Under Pressure',
            'src': '4_impostor.mp3', 'duration': len(clip) / SR, 'reveal': round(reveal, 2), **curve(lb),
            'settings': {'source': IMP, 'start': round(start, 3), 'end': round(start + length, 3),
                         'reveal_in_song': round(start + reveal, 2), 'bar_s': round(bar, 4), 'lufs': lufs(clip)}}


def main():
    rng = np.random.default_rng(SEED)
    for old in list(OUT_STATIC.glob('*.mp3')) + list(OUT_STATIC.glob('*.png')) + list(OUT_WAV.glob('*')):
        old.unlink()
    clips = [c for c in (another_room(rng), short_decisive(rng), impostor(rng)) if c]
    meta = {'fps': FPS, 'sigma_mem': SIGMA_MEM, 'decisive': 2.0, 'clips': clips}
    (OUT_STATIC / 'nametune.json').write_text(json.dumps(meta, separators=(',', ':')))
    for c in clips:
        for v in c.get('variants', [c]):
            lb = v['log10B']
            tag = f"{c['id']} {v.get('snr_db', '')}".strip()
            d = decisive_at(lb)
            print(f"{tag:22s} final log10B {lb[-1]:7.1f}  decisive at {d if d is not None else float('nan'):5.2f} s  "
                  f"at 1/2/3 s: {', '.join(f'{lb[min(len(lb) - 1, s * FPS)]:.2f}' for s in (1, 2, 3))}"
                  + (f"  in-band SNR {v['inband_snr_db']} dB, {v['lufs']} LUFS" if 'inband_snr_db' in v else ''))
        print('   ', c['settings'])


if __name__ == '__main__':
    main()
