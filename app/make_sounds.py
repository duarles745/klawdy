#!/usr/bin/env python3
"""Synthesises Klawdy's sound effects (no external files)."""
import math
import os
import random
import struct
import wave

RATE = 44100
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sounds")
random.seed(7)


def silence(sec):
    return [0.0] * int(RATE * sec)


def tone(f0, f1, sec, vol=0.5, shape="sine", vib=0.0, attack=0.005, release=0.04):
    n = int(RATE * sec)
    out, ph = [], 0.0
    for i in range(n):
        t = i / n
        f = f0 + (f1 - f0) * t
        if vib:
            f *= 1 + 0.03 * math.sin(2 * math.pi * vib * i / RATE)
        ph += 2 * math.pi * f / RATE
        if shape == "square":
            v = 0.6 if math.sin(ph) > 0 else -0.6
            v = v * 0.6 + 0.4 * math.sin(ph)
        elif shape == "tri":
            v = 2 / math.pi * math.asin(math.sin(ph))
        else:
            v = math.sin(ph)
        env = min(1.0, i / (attack * RATE + 1)) * min(1.0, (n - i) / (release * RATE + 1))
        out.append(v * env * vol)
    return out


def clack(vol=0.8, pitch=2600):
    """Estalo de pinça: ruído curtinho + 'tic' agudo com decaimento rápido."""
    n = int(RATE * 0.045)
    out = []
    for i in range(n):
        d = math.exp(-i / (RATE * 0.006))
        noise = random.uniform(-1, 1) * math.exp(-i / (RATE * 0.002))
        tic = math.sin(2 * math.pi * pitch * i / RATE) * d
        body = math.sin(2 * math.pi * (pitch / 3.2) * i / RATE) * math.exp(-i / (RATE * 0.012))
        out.append((0.45 * noise + 0.4 * tic + 0.35 * body) * vol)
    return out


def bubble(f=500, vol=0.35):
    return tone(f, f * 2.1, 0.07, vol, attack=0.003, release=0.03)


def mix(*parts):
    out = []
    for p in parts:
        out.extend(p)
    return out


def overlay(base, add, at):
    i0 = int(at * RATE)
    if len(base) < i0 + len(add):
        base = base + [0.0] * (i0 + len(add) - len(base))
    for i, v in enumerate(add):
        base[i0 + i] += v
    return base


def save(name, data):
    os.makedirs(OUT, exist_ok=True)
    peak = max(1e-6, max(abs(v) for v in data))
    k = 0.85 / peak if peak > 0.85 else 1.0
    with wave.open(os.path.join(OUT, name), "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(b"".join(struct.pack("<h", int(max(-1, min(1, v * k)) * 32767)) for v in data))


def main():
    # 1) ouviu "claudinho": duas bolhinhas subindo
    save("ouvindo.wav", mix(bubble(420), silence(0.03), bubble(620), silence(0.05)))

    # 2) entendeu e vai executar: clac-clac-clac de caranguejo + piadinha feliz
    s = mix(clack(), silence(0.06), clack(0.7, 2900), silence(0.05), clack(0.9, 2400), silence(0.06))
    s = mix(s, tone(1100, 1500, 0.07, 0.25, "tri"), silence(0.02), tone(1500, 1900, 0.09, 0.25, "tri"))
    save("entendi.wav", s)

    # 3) trabalhando: bolhinhas suaves (caranguejo no fundo do mar)
    base = silence(1.0)
    for i in range(7):
        base = overlay(base, bubble(random.uniform(300, 650), 0.18), i * 0.13 + random.uniform(0, 0.05))
    save("trabalhando.wav", base)

    # 4) pronto / deu certo: arpejo alegre + dois estalos
    notes = [523.25, 659.25, 783.99, 1046.5]
    s = []
    for f in notes:
        s += tone(f, f, 0.09, 0.32, "square", release=0.03)
    s += tone(1046.5, 1046.5, 0.22, 0.28, "square", release=0.15)
    s = overlay(s, clack(0.6, 3000), 0.40)
    s = overlay(s, clack(0.6, 3200), 0.50)
    save("pronto.wav", s)

    # 5) erro: "uá-uá" descendo
    s = mix(tone(392, 370, 0.22, 0.4, "tri", vib=6), silence(0.04),
            tone(349, 262, 0.45, 0.4, "tri", vib=6, release=0.2))
    save("erro.wav", s)

    # 6) não entendi: "hã?" (sobe no fim) + um estalinho
    s = mix(tone(500, 470, 0.12, 0.35, "tri"), silence(0.03), tone(470, 760, 0.18, 0.35, "tri"), silence(0.05),
            clack(0.5, 2800))
    save("naoentendi.wav", s)

    # 7) precisa de você: estalos + "plim-plim"
    s = mix(clack(), silence(0.04), clack(0.8, 2900), silence(0.08),
            tone(880, 880, 0.12, 0.35, release=0.08), silence(0.03), tone(660, 660, 0.2, 0.35, release=0.15))
    save("atencao.wav", s)

    # 8) ocupado (já está fazendo outra coisa): dois estalos rápidos e graves
    save("ocupado.wav", mix(clack(0.7, 1800), silence(0.05), clack(0.7, 1600)))
    print("sounds written to", OUT)


if __name__ == "__main__":
    main()
